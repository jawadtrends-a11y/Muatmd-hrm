"""
حرّاس الفوترة والاشتراكات (ق-47، ق-48، ق-49، ق-50).

طبقة تمسّ أموال العميل — لا يُعتمد تغيير فيها قبل اجتيازها.
"""
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company, Plan
from apps.accounts.models_billing_v2 import (
    AccountSubscription, BillingCycle, Discount, DiscountKind, DiscountScope,
    Invoice, InvoiceStatus, SubscriptionPaymentMethod, SubscriptionState,
)
from apps.accounts.models_platform import get_settings
from apps.accounts.services.billing_v2 import (
    BillingError, account_peak_headcount, create_invoice, effective_end,
    evaluate_state, extend_grace, activate_manually, is_writable,
    issue_invoice, mark_paid, period_end_for, renewal_alert_due,
    resolve_discount, start_trial,
)
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope


@pytest.fixture
def env(db):
    # الباقات بذرة منصة — لا ينشئها provision_account
    from apps.accounts.services.plans import sync_default_plans
    sync_default_plans()

    r = provision_account(slug="blg-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        yield {"account_id": r.account_id, "acc": acc,
               "plan": Plan.objects.filter(code="premium").first()}


def _sub(env, **kw):
    sub = start_trial(env["acc"])
    for k, v in kw.items():
        setattr(sub, k, v)
    if kw:
        sub.save()
    return sub


# ══════════ التجربة المجانية (ق-47) ══════════

@pytest.mark.django_db(transaction=True)
def test_trial_starts_with_limits(env):
    """سبعة أيام وخمسة موظفين."""
    with account_scope(env["account_id"]):
        sub = start_trial(env["acc"])
        assert sub.state == SubscriptionState.TRIAL
        assert sub.employee_limit == 5
        assert (sub.trial_ends_at - sub.trial_started_at).days == 7
        assert is_writable(sub)


@pytest.mark.django_db(transaction=True)
def test_second_trial_blocked(env):
    with account_scope(env["account_id"]):
        start_trial(env["acc"])
        with pytest.raises(BillingError):
            start_trial(env["acc"])


@pytest.mark.django_db(transaction=True)
def test_trial_expires_to_read_only(env):
    """
    ق-47: بعد التجربة قراءة فقط بلا حد زمني — لا يُقفل ولا يُحذف.
    """
    with account_scope(env["account_id"]):
        sub = _sub(env, trial_ends_at=date.today() - timedelta(days=1))
        evaluate_state(sub)
        assert sub.state == SubscriptionState.READ_ONLY
        assert not is_writable(sub)
        assert sub.employee_limit is None


# ══════════ الخصومات الثلاثة (ق-47) ══════════

@pytest.mark.django_db(transaction=True)
def test_coupon_percent(env):
    with account_scope(env["account_id"]):
        Discount.objects.create(
            code="WELCOME20", name_ar="ترحيبي", scope=DiscountScope.COUPON,
            kind=DiscountKind.PERCENT, value=D("20"))
        res = resolve_discount(account=env["acc"],
                               cycle=BillingCycle.MONTHLY,
                               subtotal=D("1000"), coupon_code="welcome20")
        assert res.amount == D("200.00")


@pytest.mark.django_db(transaction=True)
def test_coupon_fixed_amount_capped(env):
    """الخصم الثابت لا يتجاوز المبلغ."""
    with account_scope(env["account_id"]):
        Discount.objects.create(
            code="FLAT", name_ar="مبلغ", scope=DiscountScope.COUPON,
            kind=DiscountKind.AMOUNT, value=D("5000"))
        res = resolve_discount(account=env["acc"],
                               cycle=BillingCycle.MONTHLY,
                               subtotal=D("1000"), coupon_code="FLAT")
        assert res.amount == D("1000")


@pytest.mark.django_db(transaction=True)
def test_expired_coupon_rejected(env):
    with account_scope(env["account_id"]):
        Discount.objects.create(
            code="OLD", name_ar="منتهٍ", scope=DiscountScope.COUPON,
            kind=DiscountKind.PERCENT, value=D("50"),
            valid_until=date.today() - timedelta(days=1))
        res = resolve_discount(account=env["acc"],
                               cycle=BillingCycle.MONTHLY,
                               subtotal=D("1000"), coupon_code="OLD")
        assert res.amount == D("0")
        assert "انتهى" in res.reason


@pytest.mark.django_db(transaction=True)
def test_coupon_bound_to_other_account_rejected(env):
    with account_scope(env["account_id"]):
        other = provision_account(slug="blg-o", display_name_ar="آخر",
                                  company_name_ar="أخرى", is_sandbox=True)
        Discount.objects.create(
            code="PRIVATE", name_ar="خاص", scope=DiscountScope.COUPON,
            kind=DiscountKind.PERCENT, value=D("30"),
            account_id=other.account_id)
        res = resolve_discount(account=env["acc"],
                               cycle=BillingCycle.MONTHLY,
                               subtotal=D("1000"), coupon_code="PRIVATE")
        assert res.amount == D("0")


@pytest.mark.django_db(transaction=True)
def test_exhausted_coupon_rejected(env):
    with account_scope(env["account_id"]):
        Discount.objects.create(
            code="LIMITED", name_ar="محدود", scope=DiscountScope.COUPON,
            kind=DiscountKind.PERCENT, value=D("10"),
            max_uses=1, used_count=1)
        res = resolve_discount(account=env["acc"],
                               cycle=BillingCycle.MONTHLY,
                               subtotal=D("1000"), coupon_code="LIMITED")
        assert "استُنفد" in res.reason


@pytest.mark.django_db(transaction=True)
def test_recurring_discount_applies_without_code(env):
    """السعر الخاص المستمر يُطبَّق بلا إدخال كود."""
    with account_scope(env["account_id"]):
        d = Discount.objects.create(
            code="LOYAL", name_ar="عميل مميز",
            scope=DiscountScope.RECURRING, kind=DiscountKind.PERCENT,
            value=D("15"))
        sub = _sub(env, recurring_discount=d)
        res = resolve_discount(account=env["acc"],
                               cycle=BillingCycle.MONTHLY,
                               subtotal=D("1000"), subscription=sub)
        assert res.amount == D("150.00")


# ══════════ الفواتير ورسوم الإعداد (ق-47) ══════════

@pytest.mark.django_db(transaction=True)
def test_setup_fee_charged_once(env):
    """ق-47: رسوم الإعداد مرة واحدة في حياة الحساب."""
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], setup_fee_amount=D("2000"),
                   state=SubscriptionState.ACTIVE)
        inv1, _ = create_invoice(subscription=sub, headcount=10)
        assert inv1.setup_fee == D("2000.00")
        assert inv1.lines.filter(is_setup_fee=True).count() == 1

        issue_invoice(inv1)
        mark_paid(inv1)
        sub.refresh_from_db()
        assert sub.setup_fee_charged is True

        inv2, _ = create_invoice(subscription=sub,
                                 period_start=date.today() + timedelta(days=31),
                                 headcount=10)
        assert inv2.setup_fee == D("0")
        assert not inv2.lines.filter(is_setup_fee=True).exists()


@pytest.mark.django_db(transaction=True)
def test_setup_fee_is_separate_line(env):
    """سطر منفصل موضّح أنه لمرة واحدة."""
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], setup_fee_amount=D("2000"),
                   state=SubscriptionState.ACTIVE)
        inv, _ = create_invoice(subscription=sub, headcount=10)
        line = inv.lines.get(is_setup_fee=True)
        assert "مرة واحدة" in line.note_ar


@pytest.mark.django_db(transaction=True)
def test_annual_costs_twelve_months(env):
    with account_scope(env["account_id"]):
        monthly = _sub(env, plan=env["plan"], cycle=BillingCycle.MONTHLY,
                       state=SubscriptionState.ACTIVE)
        inv_m, _ = create_invoice(subscription=monthly, headcount=10)
        base_m = inv_m.total_before_vat

        monthly.cycle = BillingCycle.ANNUAL
        monthly.save()
        inv_a, _ = create_invoice(
            subscription=monthly,
            period_start=date.today() + timedelta(days=40), headcount=10)
        # السعر السنوي = الشهري × 12 بلا خصم مدفون — الخصم
        # السنوي يُضبط من لوحة السوبر أدمن (ق-47)
        assert inv_a.total_before_vat == base_m * 12


@pytest.mark.django_db(transaction=True)
def test_custom_price_overrides_plan(env):
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], custom_price=D("999"),
                   state=SubscriptionState.ACTIVE)
        inv, _ = create_invoice(subscription=sub, headcount=100)
        assert inv.subtotal == D("999.00")


@pytest.mark.django_db(transaction=True)
def test_invoice_requires_plan_or_price(env):
    with account_scope(env["account_id"]):
        sub = _sub(env, state=SubscriptionState.ACTIVE)
        with pytest.raises(BillingError):
            create_invoice(subscription=sub, headcount=10)


# ══════════ الضريبة (ق-50) ══════════

@pytest.mark.django_db(transaction=True)
def test_vat_stored_not_derived(env):
    """ق-50: الثلاثة تُحفظ فلا يُحتسب أي منها وقت العرض."""
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], state=SubscriptionState.ACTIVE)
        inv, _ = create_invoice(subscription=sub, headcount=10)
        assert inv.vat_rate == D("15.00")
        assert inv.vat_amount == (inv.total_before_vat * D("15")
                                  / D("100")).quantize(D("0.01"))
        assert inv.total == inv.total_before_vat + inv.vat_amount


@pytest.mark.django_db(transaction=True)
def test_vat_rate_from_platform_settings(env):
    """النسبة إعداد لا رقم في الكود."""
    with account_scope(env["account_id"]):
        ps = get_settings()
        ps.vat_rate = D("5")
        ps.save()
        sub = _sub(env, plan=env["plan"], state=SubscriptionState.ACTIVE)
        inv, _ = create_invoice(subscription=sub, headcount=10)
        assert inv.vat_rate == D("5.00")
        ps.vat_rate = D("15")
        ps.save()


# ══════════ التفعيل الإداري (ق-48) ══════════

@pytest.mark.django_db(transaction=True)
def test_manual_activation_without_gateway(env):
    """ق-48: الشركات الكبيرة تفضّل التحويل البنكي."""
    with account_scope(env["account_id"]):
        sub = _sub(env)
        sub = activate_manually(
            subscription=sub, plan=env["plan"], cycle=BillingCycle.ANNUAL,
            period_start=date(2026, 9, 1), activated_by=None,
            note="تحويل بنكي TR-123")
        assert sub.state == SubscriptionState.ACTIVE
        assert sub.payment_method == SubscriptionPaymentMethod.BANK_TRANSFER
        assert sub.current_period_end == date(2027, 8, 31)
        assert "TR-123" in sub.activation_note


@pytest.mark.django_db(transaction=True)
def test_manual_extension_unlimited(env):
    """ق-48: التمديد اليدوي بلا حد."""
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"],
                   state=SubscriptionState.READ_ONLY,
                   current_period_end=date.today() - timedelta(days=10))
        far = date.today() + timedelta(days=180)
        extend_grace(subscription=sub, until=far, extended_by=None,
                     note="بانتظار التحويل")
        assert sub.grace_until == far
        assert is_writable(sub)
        assert effective_end(sub) == far


@pytest.mark.django_db(transaction=True)
def test_past_extension_rejected(env):
    with account_scope(env["account_id"]):
        sub = _sub(env)
        with pytest.raises(BillingError):
            extend_grace(subscription=sub,
                         until=date.today() - timedelta(days=1),
                         extended_by=None)


# ══════════ المهلة والحالات (ق-48) ══════════

@pytest.mark.django_db(transaction=True)
def test_grace_then_read_only(env):
    """ثلاثة أيام يعمل، ثم قراءة فقط."""
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], state=SubscriptionState.ACTIVE,
                   current_period_end=date.today() - timedelta(days=1))
        evaluate_state(sub)
        assert sub.state == SubscriptionState.GRACE
        assert is_writable(sub)

        sub.current_period_end = date.today() - timedelta(days=5)
        sub.save()
        evaluate_state(sub)
        assert sub.state == SubscriptionState.READ_ONLY
        assert not is_writable(sub)


@pytest.mark.django_db(transaction=True)
def test_payment_reactivates(env):
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"],
                   state=SubscriptionState.READ_ONLY)
        inv, _ = create_invoice(subscription=sub, headcount=10)
        issue_invoice(inv)
        mark_paid(inv)
        sub.refresh_from_db()
        assert sub.state == SubscriptionState.ACTIVE
        assert is_writable(sub)


# ══════════ التنبيهات (ق-48) ══════════

@pytest.mark.django_db(transaction=True)
def test_monthly_alert_five_days(env):
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], state=SubscriptionState.ACTIVE,
                   cycle=BillingCycle.MONTHLY,
                   current_period_end=date.today() + timedelta(days=4))
        assert renewal_alert_due(sub) is True

        sub.current_period_end = date.today() + timedelta(days=10)
        sub.save()
        assert renewal_alert_due(sub) is False


@pytest.mark.django_db(transaction=True)
def test_annual_alert_fifteen_days(env):
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], state=SubscriptionState.ACTIVE,
                   cycle=BillingCycle.ANNUAL,
                   current_period_end=date.today() + timedelta(days=10))
        assert renewal_alert_due(sub) is True

        sub.current_period_end = date.today() + timedelta(days=20)
        sub.save()
        assert renewal_alert_due(sub) is False


# ══════════ الفوترة على مستوى الحساب (ق-49) ══════════

@pytest.mark.django_db(transaction=True)
def test_headcount_sums_all_companies(env):
    """ق-49: الذروة تُجمع من كل شركات الحساب."""
    from apps.accounts.models import CompanyHeadcountDaily

    with account_scope(env["account_id"]):
        c1 = Company.objects.filter(account=env["acc"]).first()
        c2 = Company.objects.create(account=env["acc"], code="C2",
                                    legal_name_ar="شركة ثانية")
        today = date.today()
        CompanyHeadcountDaily.objects.create(
            account=env["acc"], company=c1, snapshot_date=today,
            billable_employments=10)
        CompanyHeadcountDaily.objects.create(
            account=env["acc"], company=c2, snapshot_date=today,
            billable_employments=7)

        total = account_peak_headcount(env["acc"], today, today)
        assert total == 17


@pytest.mark.django_db(transaction=True)
def test_peak_not_current_count(env):
    """الذروة لا العدد الأخير — فلا يتحايل أحد بإيقاف موظفين."""
    from apps.accounts.models import CompanyHeadcountDaily

    with account_scope(env["account_id"]):
        c1 = Company.objects.filter(account=env["acc"]).first()
        start = date.today() - timedelta(days=10)
        for i, n in enumerate([5, 22, 8, 6]):
            CompanyHeadcountDaily.objects.create(
                account=env["acc"], company=c1,
                snapshot_date=start + timedelta(days=i),
                billable_employments=n)
        assert account_peak_headcount(env["acc"], start,
                                      date.today()) == 22


# ══════════ الفترات ══════════

def test_monthly_period():
    assert period_end_for(date(2026, 1, 15),
                          BillingCycle.MONTHLY) == date(2026, 2, 14)


def test_annual_period():
    assert period_end_for(date(2026, 9, 1),
                          BillingCycle.ANNUAL) == date(2027, 8, 31)


def test_month_end_edge():
    """31 يناير + شهر = 28 فبراير لا خطأ."""
    end = period_end_for(date(2026, 1, 31), BillingCycle.MONTHLY)
    assert end.month == 2


# ══════════ العزل ══════════

@pytest.mark.django_db(transaction=True)
def test_invoices_isolated(env, rls_enforced_late):
    other = provision_account(slug="blg-iso", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(env["account_id"]):
        sub = _sub(env, plan=env["plan"], state=SubscriptionState.ACTIVE)
        create_invoice(subscription=sub, headcount=10)

    rls_enforced_late()
    with account_scope(other.account_id):
        assert Invoice.objects.count() == 0
        assert AccountSubscription.objects.count() == 0
