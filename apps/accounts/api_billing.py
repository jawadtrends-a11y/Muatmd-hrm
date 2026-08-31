"""
API الفوترة والاشتراك (ق-47، ق-48، ق-50).

للعميل: حالة اشتراكه، الباقات، الفواتير، الدفع.
"""
from datetime import date

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models_billing_v2 import (
    AccountSubscription, BillingCycle, Invoice, InvoiceStatus, Payment,
    SavedCard, SubscriptionState,
)
from apps.accounts.services import billing_v2 as billing
from apps.accounts.services.payments import service as pay
from apps.core.access.gate import Gate


def _account_id(request):
    return getattr(getattr(request, "account_ctx", None), "account_id", None)


def _subscription(request):
    acc_id = _account_id(request)
    if acc_id is None:
        return None
    return AccountSubscription.objects.filter(account_id=acc_id).first()


# ══════════ حالة الاشتراك ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscription_status(request):
    """
    حالة اشتراك الحساب — تُقرأ في كل شاشة لعرض التنبيهات.
    """
    sub = _subscription(request)
    if sub is None:
        return Response({"detail": "لا اشتراك لهذا الحساب"}, status=404)

    end = billing.effective_end(sub)
    days_left = (end - date.today()).days if end else None

    return Response({
        "state": sub.state,
        "state_label": sub.get_state_display(),
        "is_writable": billing.is_writable(sub),
        "plan": sub.plan.name_ar if sub.plan else None,
        "plan_code": sub.plan.code if sub.plan else None,
        "cycle": sub.cycle,
        "cycle_label": sub.get_cycle_display(),
        "payment_method": sub.payment_method,
        "auto_renew": sub.auto_renew,
        "period_start": sub.current_period_start,
        "period_end": sub.current_period_end,
        "grace_until": sub.grace_until,
        "effective_end": end,
        "days_left": days_left,
        "renewal_alert": billing.renewal_alert_due(sub),
        "trial": {
            "days_left": sub.trial_days_left,
            "ends_at": sub.trial_ends_at,
            "employee_limit": sub.employee_limit,
        } if sub.state == SubscriptionState.TRIAL else None,
        "saved_card": {
            "brand": sub.saved_card.brand,
            "last_four": sub.saved_card.last_four,
        } if sub.saved_card else None,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def available_plans(request):
    """
    الباقات وأسعارها — قبل الضريبة وشاملها (ق-50).

    السعر البارز قبل الضريبة، والشامل تحته بخط صغير.
    """
    from apps.accounts.models import Plan
    from apps.accounts.models_platform import get_settings

    vat = get_settings().vat_rate
    sub = _subscription(request)
    headcount = billing.account_peak_headcount(
        sub.account, date.today(), date.today()) if sub else 0

    out = []
    for plan in Plan.objects.filter(is_active=True).order_by("display_order"):
        entry = {"code": plan.code, "name_ar": plan.name_ar,
                 "description_ar": getattr(plan, "description_ar", ""),
                 "prices": {}}
        for cycle in (BillingCycle.MONTHLY, BillingCycle.ANNUAL):
            try:
                before, billable, tier = billing.price_for(
                    plan, headcount, cycle)
            except billing.BillingError:
                continue
            vat_amount = billing.r2(before * vat / 100)
            entry["prices"][cycle] = {
                "before_vat": str(before),
                "vat_amount": str(vat_amount),
                "total": str(billing.r2(before + vat_amount)),
                "billable_employees": billable,
            }
        entry["current"] = bool(sub and sub.plan_id == plan.id)
        out.append(entry)

    return Response({"vat_rate": str(vat), "headcount": headcount,
                     "plans": out})


# ══════════ الفواتير ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoices(request):
    """فواتير الحساب."""
    Gate.require(request.user, "account.view")
    acc_id = _account_id(request)
    qs = Invoice.objects.filter(account_id=acc_id)
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])

    return Response([
        {
            "id": i.id, "invoice_no": i.invoice_no,
            "period": f"{i.period_start} — {i.period_end}",
            "cycle": i.get_cycle_display(),
            "subtotal": str(i.subtotal),
            "setup_fee": str(i.setup_fee),
            "discount": str(i.discount_amount),
            "before_vat": str(i.total_before_vat),
            "vat_rate": str(i.vat_rate),
            "vat_amount": str(i.vat_amount),
            "total": str(i.total),
            "status": i.status, "status_label": i.get_status_display(),
            "due_date": i.due_date, "paid_at": i.paid_at,
            "is_overdue": i.is_overdue,
        }
        for i in qs.order_by("-period_start")[:50]
    ])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_detail(request, invoice_id):
    """تفاصيل فاتورة بسطورها."""
    Gate.require(request.user, "account.view")
    inv = Invoice.objects.filter(
        id=invoice_id, account_id=_account_id(request)).first()
    if inv is None:
        return Response({"detail": "الفاتورة غير موجودة"}, status=404)

    return Response({
        "invoice_no": inv.invoice_no,
        "period": f"{inv.period_start} — {inv.period_end}",
        "status": inv.status, "status_label": inv.get_status_display(),
        "lines": [
            {"description": l.description_ar, "amount": str(l.amount),
             "note": l.note_ar, "is_setup_fee": l.is_setup_fee}
            for l in inv.lines.order_by("display_order")
        ],
        "before_vat": str(inv.total_before_vat),
        "vat_rate": str(inv.vat_rate),
        "vat_amount": str(inv.vat_amount),
        "total": str(inv.total),
        "accounting_invoice_id": inv.accounting_invoice_id,
        "note": ("الفاتورة الضريبية تصدر من محاسبة معتمد"),
    })


# ══════════ الدفع ══════════

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_checkout(request):
    """
    يبدأ اشتراكًا: ينشئ الفاتورة ويعيد بيانات الدفع.

    الواجهة تنشئ الرمز مع ميسر مباشرةً — بيانات البطاقة لا تمر
    بخادمنا (ق-47).
    """
    from django.conf import settings
    from apps.accounts.models import Plan

    Gate.require(request.user, "account.manage")
    sub = _subscription(request)
    if sub is None:
        return Response({"detail": "لا اشتراك لهذا الحساب"}, status=404)

    plan = Plan.objects.filter(
        code=request.data.get("plan_code", ""), is_active=True).first()
    if plan is None:
        return Response({"detail": "باقة غير معروفة"}, status=400)

    cycle = request.data.get("cycle", BillingCycle.MONTHLY)
    if cycle not in (BillingCycle.MONTHLY, BillingCycle.ANNUAL):
        return Response({"detail": "دورة غير صحيحة"}, status=400)

    sub.plan = plan
    sub.cycle = cycle
    sub.save(update_fields=["plan", "cycle", "updated_at"])

    try:
        invoice, disc = billing.create_invoice(
            subscription=sub, coupon_code=request.data.get("coupon_code"))
        billing.issue_invoice(invoice)
    except billing.BillingError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({
        "invoice_id": invoice.id,
        "invoice_no": invoice.invoice_no,
        "before_vat": str(invoice.total_before_vat),
        "vat_amount": str(invoice.vat_amount),
        "total": str(invoice.total),
        "setup_fee": str(invoice.setup_fee),
        "discount": {"amount": str(disc.amount),
                     "name": disc.discount.name_ar if disc.discount else None,
                     "reason": disc.reason},
        "publishable_key": settings.MOYASAR_PUBLISHABLE_KEY,
        "callback_url": settings.MOYASAR_CALLBACK_URL,
        "amount_halalas": int(invoice.total * 100),
    }, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pay_invoice(request, invoice_id):
    """
    ينشئ عملية دفع لفاتورة — بمصدر من الواجهة.
    """
    Gate.require(request.user, "account.manage")
    inv = Invoice.objects.filter(
        id=invoice_id, account_id=_account_id(request)).first()
    if inv is None:
        return Response({"detail": "الفاتورة غير موجودة"}, status=404)

    source = request.data.get("source")
    if not isinstance(source, dict) or "type" not in source:
        return Response({"detail": "مصدر الدفع مطلوب"}, status=400)

    try:
        payment, url = pay.start_payment(
            invoice=inv, source=source,
            save_card=bool(request.data.get("save_card")))
    except pay.PaymentThrottled as e:
        return Response({"detail": str(e), "code": "throttled",
                         "minutes_left": e.minutes_left}, status=429)
    except pay.PaymentError as e:
        return Response({"detail": str(e), "code": "payment_failed"},
                        status=400)

    return Response({
        "payment_id": payment.id,
        "moyasar_id": payment.moyasar_payment_id,
        "status": payment.status,
        "transaction_url": url,
        "needs_action": bool(url),
    })


@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def payment_callback(request):
    """
    عودة العميل من ميسر.

    ⚠️ لا نثق بمعطيات الرابط — نسأل ميسر مباشرةً عن الحالة
    الفعلية، فالرابط قابل للتزوير.
    """
    payment_id = (request.GET.get("id") or request.data.get("id") or "")
    if not payment_id:
        return Response({"detail": "معرّف العملية مفقود"}, status=400)

    try:
        payment = pay.confirm_payment(payment_id)
    except pay.PaymentError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({
        "status": payment.status,
        "status_label": payment.get_status_display(),
        "invoice_no": payment.invoice.invoice_no,
        "amount": str(payment.amount),
        "paid": payment.status == "paid",
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def toggle_auto_renew(request):
    """
    تفعيل التجديد التلقائي أو إيقافه — خيار العميل (ق-48).
    """
    Gate.require(request.user, "account.manage")
    sub = _subscription(request)
    if sub is None:
        return Response({"detail": "لا اشتراك"}, status=404)

    enable = bool(request.data.get("auto_renew"))
    if enable and sub.saved_card is None:
        return Response({
            "detail": "لا بطاقة محفوظة — ادفع مرة مع حفظ البطاقة أولًا",
            "code": "no_saved_card"}, status=400)

    sub.auto_renew = enable
    sub.save(update_fields=["auto_renew", "updated_at"])
    return Response({"auto_renew": sub.auto_renew})


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def saved_cards(request):
    """البطاقات المحفوظة — بلا رقم بطاقة."""
    Gate.require(request.user, "account.manage")
    acc_id = _account_id(request)

    if request.method == "DELETE":
        card_id = request.GET.get("id")
        card = SavedCard.objects.filter(id=card_id,
                                        account_id=acc_id).first()
        if card is None:
            return Response({"detail": "البطاقة غير موجودة"}, status=404)
        AccountSubscription.objects.filter(
            saved_card=card).update(saved_card=None, auto_renew=False)
        card.delete()
        return Response({"deleted": True})

    return Response([
        {"id": c.id, "brand": c.brand, "last_four": c.last_four,
         "is_default": c.is_default, "last_used_at": c.last_used_at}
        for c in SavedCard.objects.filter(account_id=acc_id, is_active=True)
    ])
