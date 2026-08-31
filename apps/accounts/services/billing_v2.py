"""
خدمة الفوترة والاشتراكات (ق-47، ق-48).

الفاتورة الضريبية من «محاسبة معتمد» (ق-12) — هذه تحتسب وتقبض
وتُبلغ المحاسبي.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models_billing_v2 import (
    AccountSubscription, BillingCycle, Discount, DiscountKind, DiscountScope,
    Invoice, InvoiceLine, InvoiceStatus, SubscriptionPaymentMethod,
    SubscriptionState,
)

ZERO = Decimal("0")
GRACE_DAYS = 3
RENEWAL_ALERT = {BillingCycle.MONTHLY: 5, BillingCycle.ANNUAL: 15}


def r2(v):
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class BillingError(Exception):
    pass


# ══════════ التجربة المجانية (ق-47) ══════════

@transaction.atomic
def start_trial(account):
    """سبعة أيام وخمسة موظفين."""
    if AccountSubscription.objects.filter(account=account).exists():
        raise BillingError("للحساب اشتراك قائم")
    today = date.today()
    return AccountSubscription.objects.create(
        account=account, state=SubscriptionState.TRIAL,
        trial_started_at=today,
        trial_ends_at=today + timedelta(days=AccountSubscription.TRIAL_DAYS))


# ══════════ الخصومات (ق-47) ══════════

@dataclass
class DiscountResult:
    amount: Decimal = ZERO
    discount: object = None
    reason: str = ""


def _apply(discount, subtotal):
    if discount.kind == DiscountKind.PERCENT:
        return r2(subtotal * discount.value / Decimal("100"))
    return min(r2(discount.value), subtotal)


def resolve_discount(*, account, cycle, subtotal, coupon_code=None,
                     subscription=None, as_of=None):
    """الكود المُدخل يسبق الخصم المستمر."""
    day = as_of or date.today()

    if coupon_code:
        d = Discount.objects.filter(
            code__iexact=coupon_code.strip(),
            scope=DiscountScope.COUPON).first()
        if d is None:
            return DiscountResult(reason="كود خصم غير موجود")
        ok, why = d.is_valid_on(day)
        if not ok:
            return DiscountResult(reason=why)
        if d.account_id and d.account_id != account.id:
            return DiscountResult(reason="الكود مخصص لحساب آخر")
        if d.applies_to_cycle and d.applies_to_cycle != cycle:
            return DiscountResult(reason="الكود لا يسري على هذه الدورة")
        return DiscountResult(amount=_apply(d, subtotal), discount=d)

    if subscription and subscription.recurring_discount_id:
        d = subscription.recurring_discount
        ok, _why = d.is_valid_on(day)
        if ok:
            return DiscountResult(amount=_apply(d, subtotal), discount=d)

    return DiscountResult()


# ══════════ الفواتير ══════════

def _next_invoice_no():
    year = date.today().year
    n = Invoice.objects.filter(invoice_no__startswith=f"INV-{year}").count()
    return f"INV-{year}-{n + 1:06d}"


def period_end_for(start, cycle):
    from calendar import monthrange
    if cycle == BillingCycle.ANNUAL:
        try:
            return start.replace(year=start.year + 1) - timedelta(days=1)
        except ValueError:
            return date(start.year + 1, 2, 28)
    month = start.month + 1
    year = start.year + (1 if month > 12 else 0)
    month = 1 if month > 12 else month
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day) - timedelta(days=1)


def account_peak_headcount(account, start, end):
    """
    ذروة موظفي الحساب — مجموع ذروات شركاته (ق-49).

    الذروة لا العدد يوم الفاتورة: فلا يتحايل أحد بإيقاف موظفين
    قبل الفوترة وإعادتهم بعدها.
    """
    from apps.accounts.models import Company, CompanyHeadcountDaily

    total = 0
    for cid in Company.objects.filter(
            account=account).values_list("id", flat=True):
        snaps = CompanyHeadcountDaily.objects.filter(
            company_id=cid, snapshot_date__gte=start,
            snapshot_date__lte=end).values_list(
            "billable_employments", flat=True)
        total += max(snaps) if snaps else 0

    if total == 0:      # لا لقطات بعد — نأخذ العدد الحالي
        from apps.employees.models import Employment, EmploymentStatus
        total = Employment.objects.filter(
            account=account, status=EmploymentStatus.ACTIVE).count()
    return total


def price_for(plan, headcount, cycle):
    """سعر الباقة لعدد موظفين — بشريحة السعر المناسبة."""
    billable = max(headcount, plan.min_billable_employees)
    tier = (plan.price_tiers.filter(from_employees__lte=billable)
            .order_by("-from_employees").first())
    if tier is None:
        raise BillingError(f"لا شريحة سعر تغطي {billable} موظفًا")

    unit = (tier.price_per_employee_monthly
            if cycle == BillingCycle.MONTHLY
            else (tier.price_per_employee_yearly
                  or tier.price_per_employee_monthly * 12))
    base_fee = (plan.base_fee_monthly
                if cycle == BillingCycle.MONTHLY
                else plan.base_fee_monthly * 12)
    return r2(unit * billable + base_fee), billable, tier


def _covers_setup(coupon_code):
    if not coupon_code:
        return False
    d = Discount.objects.filter(code__iexact=coupon_code.strip()).first()
    return bool(d and d.covers_setup_fee)


@transaction.atomic
def create_invoice(*, subscription, period_start=None, headcount=None,
                   coupon_code=None):
    """
    ينشئ فاتورة اشتراك — رسوم الإعداد بسطر منفصل مرة واحدة (ق-47).
    """
    account = subscription.account
    start = period_start or date.today()
    end = period_end_for(start, subscription.cycle)

    n = (headcount if headcount is not None
         else account_peak_headcount(account, start, end))

    if subscription.custom_price is not None:
        base = r2(subscription.custom_price)
        if subscription.cycle == BillingCycle.ANNUAL:
            base = r2(base * Decimal("12"))
        note = "سعر خاص متفق عليه"
    elif subscription.plan is not None:
        base, billable, tier = price_for(
            subscription.plan, n, subscription.cycle)
        note = (f"{billable} موظفًا — شريحة "
                f"{tier.from_employees}–{tier.to_employees or '∞'}")
    else:
        raise BillingError("لا باقة ولا سعر خاص للاشتراك")

    inv = Invoice.objects.create(
        account=account, invoice_no=_next_invoice_no(),
        period_start=start, period_end=end, cycle=subscription.cycle,
        subtotal=base, headcount=n, status=InvoiceStatus.DRAFT)

    lines = [InvoiceLine(
        invoice=inv,
        description_ar=("اشتراك " + subscription.get_cycle_display()
                        + (f" — {subscription.plan.name_ar}"
                           if subscription.plan else "")),
        quantity=1, unit_price=base, amount=base,
        note_ar=note, display_order=10)]

    setup = ZERO
    if (subscription.setup_fee_amount > 0
            and not subscription.setup_fee_charged):
        setup = r2(subscription.setup_fee_amount)
        lines.append(InvoiceLine(
            invoice=inv, description_ar="رسوم الإعداد الأولي",
            quantity=1, unit_price=setup, amount=setup, is_setup_fee=True,
            note_ar="تُدفع مرة واحدة فقط عند بداية الاشتراك",
            display_order=20))

    disc = resolve_discount(
        account=account, cycle=subscription.cycle,
        subtotal=base + (setup if _covers_setup(coupon_code) else ZERO),
        coupon_code=coupon_code, subscription=subscription)

    if disc.amount > 0:
        lines.append(InvoiceLine(
            invoice=inv,
            description_ar=f"خصم — {disc.discount.name_ar}",
            quantity=1, unit_price=-disc.amount, amount=-disc.amount,
            display_order=30))

    InvoiceLine.objects.bulk_create(lines)

    # ── الضريبة (ق-50): تُحفظ الثلاثة فلا يُحتسب أي منها لاحقًا ──
    from apps.accounts.models_platform import get_settings
    ps = get_settings()

    before_vat = r2(base + setup - disc.amount)
    vat = r2(before_vat * ps.vat_rate / Decimal("100"))

    inv.setup_fee = setup
    inv.discount_amount = disc.amount
    inv.discount = disc.discount
    inv.vat_rate = ps.vat_rate
    inv.total_before_vat = before_vat
    inv.vat_amount = vat
    inv.total = r2(before_vat + vat)
    inv.save()
    return inv, disc


@transaction.atomic
def issue_invoice(invoice, due_days=7):
    if invoice.status != InvoiceStatus.DRAFT:
        raise BillingError(
            f"الفاتورة {invoice.get_status_display()} — لا تُصدر")
    invoice.status = InvoiceStatus.ISSUED
    invoice.issued_at = timezone.now()
    invoice.due_date = date.today() + timedelta(days=due_days)
    invoice.save()
    if invoice.discount_id:
        Discount.objects.filter(id=invoice.discount_id).update(
            used_count=F("used_count") + 1)
    return invoice


@transaction.atomic
def mark_paid(invoice, actor=None, note=""):
    """يعلّم الفاتورة مدفوعة ويجدد فترة الاشتراك."""
    if invoice.status == InvoiceStatus.PAID:
        return invoice

    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = timezone.now()
    if note:
        invoice.note = note
    invoice.save()

    sub = AccountSubscription.objects.filter(
        account_id=invoice.account_id).first()
    if sub:
        sub.state = SubscriptionState.ACTIVE
        sub.current_period_start = invoice.period_start
        sub.current_period_end = invoice.period_end
        sub.next_billing_date = invoice.period_end + timedelta(days=1)
        sub.grace_until = None
        if invoice.setup_fee > 0:
            sub.setup_fee_charged = True
        sub.save()

        from apps.core.services.audit import log_action
        log_action(instance=sub, action="update", actor=actor,
                   label=invoice.invoice_no,
                   summary=(f"سداد فاتورة {invoice.total} — الاشتراك "
                            f"حتى {invoice.period_end}"))
    return invoice


# ══════════ التفعيل الإداري (ق-48) ══════════

@transaction.atomic
def activate_manually(*, subscription, plan, cycle, period_start,
                      activated_by, payment_method=None, note="",
                      custom_price=None, setup_fee=None):
    """
    يسند باقة بلا مرور بالبوابة (ق-48).

    الشركات الكبيرة تفضّل التحويل البنكي، وتُصدر لها فاتورة ضريبية
    يدويًا من «معتمد المحاسبي».
    """
    subscription.plan = plan
    subscription.cycle = cycle
    subscription.state = SubscriptionState.ACTIVE
    subscription.payment_method = (
        payment_method or SubscriptionPaymentMethod.BANK_TRANSFER)
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end_for(period_start, cycle)
    subscription.next_billing_date = (
        subscription.current_period_end + timedelta(days=1))
    subscription.activated_by_person = activated_by
    subscription.activation_note = note
    subscription.grace_until = None
    if custom_price is not None:
        subscription.custom_price = custom_price
    if setup_fee is not None:
        subscription.setup_fee_amount = setup_fee
    subscription.save()

    from apps.core.services.audit import log_action
    log_action(instance=subscription, action="approve", actor=activated_by,
               label=f"اشتراك {subscription.account_id}",
               summary=(f"تفعيل إداري — {plan.name_ar if plan else ''} "
                        f"حتى {subscription.current_period_end}"
                        + (f" — {note}" if note else "")))
    return subscription


@transaction.atomic
def extend_grace(*, subscription, until, extended_by, note=""):
    """
    تمديد يدوي بلا حد (ق-48) — لحالات التحويل البنكي.
    """
    if until <= date.today():
        raise BillingError("تاريخ التمديد يجب أن يكون مستقبليًا")

    subscription.grace_until = until
    if subscription.state == SubscriptionState.READ_ONLY:
        subscription.state = SubscriptionState.GRACE
    subscription.save(update_fields=["grace_until", "state", "updated_at"])

    from apps.core.services.audit import log_action
    log_action(instance=subscription, action="update", actor=extended_by,
               label=f"اشتراك {subscription.account_id}",
               summary=f"تمديد يدوي حتى {until}" + (f" — {note}" if note else ""))
    return subscription


# ══════════ الحالة والتنبيهات (ق-48) ══════════

def renewal_alert_due(subscription, as_of=None):
    """التنبيه قبل 5 أيام للشهري و15 للسنوي."""
    if subscription.state != SubscriptionState.ACTIVE:
        return False
    if not subscription.current_period_end:
        return False
    days_left = (subscription.current_period_end - (as_of or date.today())).days
    return 0 <= days_left <= RENEWAL_ALERT.get(subscription.cycle, 5)


def effective_end(subscription):
    """نهاية الصلاحية شاملة التمديد اليدوي."""
    end = subscription.current_period_end
    if subscription.grace_until and (not end
                                     or subscription.grace_until > end):
        return subscription.grace_until
    return end


def evaluate_state(subscription, as_of=None):
    """
    يحدّث الحالة حسب التواريخ (ق-48).

    التجربة تنتهي لقراءة فقط، والاشتراك يمر بمهلة ثلاثة أيام
    ثم يصير للقراءة.
    """
    day = as_of or date.today()

    if subscription.state == SubscriptionState.TRIAL:
        if subscription.trial_ends_at and day > subscription.trial_ends_at:
            subscription.state = SubscriptionState.READ_ONLY
            subscription.save(update_fields=["state", "updated_at"])
            return "انتهت التجربة — قراءة فقط"
        return None

    if subscription.state == SubscriptionState.CANCELLED:
        return None

    end = effective_end(subscription)
    if end is None:
        return None

    if day <= end:
        if subscription.state in (SubscriptionState.GRACE,
                                  SubscriptionState.READ_ONLY):
            subscription.state = SubscriptionState.ACTIVE
            subscription.save(update_fields=["state", "updated_at"])
            return "استُؤنف الاشتراك"
        return None

    if day <= end + timedelta(days=GRACE_DAYS):
        if subscription.state != SubscriptionState.GRACE:
            subscription.state = SubscriptionState.GRACE
            subscription.save(update_fields=["state", "updated_at"])
            return "انتهى الاشتراك — مهلة ثلاثة أيام"
        return None

    if subscription.state != SubscriptionState.READ_ONLY:
        subscription.state = SubscriptionState.READ_ONLY
        subscription.save(update_fields=["state", "updated_at"])
        return "انتهت المهلة — قراءة فقط"
    return None


def is_writable(subscription):
    """هل يُسمح بالكتابة؟ المهلة تسمح، والقراءة فقط لا."""
    return subscription.state in (
        SubscriptionState.TRIAL, SubscriptionState.ACTIVE,
        SubscriptionState.GRACE, SubscriptionState.PAST_DUE)
