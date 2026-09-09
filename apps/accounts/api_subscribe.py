"""
الباقات والاشتراك — ما يراه العميل (ق-108).

يرى الباقات المعروضة بمزاياها، ويكتب عدد موظفيه فيرى السعر —
والضريبة ورسم الإعداد ظاهران قبل أن يدفع.
"""
from decimal import Decimal

from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes)
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models_billing import Feature, Plan
from apps.accounts.models_billing_v2 import BillingCycle
from apps.accounts.services import billing_v2 as billing
from apps.core.access.gate import Gate


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def public_plans(request):
    """
    الباقات المعروضة — بمزاياها التراكمية وسعر الموظف.

    والمزايا تُعرض تراكمية: الباقة الأعلى «تشمل ما قبلها بالإضافة
    إلى…» — فلا يقرأ العميل قائمةً مكرّرة ثلاث مرّات.
    """
    Gate.require(request.user, "account.view")

    feats = {f.feature_key: f for f in Feature.objects.all()}
    plans = list(Plan.objects.filter(is_public=True, is_active=True)
                 .order_by("tier_order", "id"))

    out = []
    seen = set()
    for p in plans:
        tier = p.price_tiers.order_by("from_employees").first()
        keys = set(p.features.values_list("feature_key", flat=True))
        new_keys = keys - seen
        rows = []
        for k in sorted(new_keys):
            f = feats.get(k)
            if f is None:
                continue
            rows.append({"key": k, "name_ar": f.name_ar,
                         "name_en": f.name_en,
                         "value": p.features.get(feature_key=k).value,
                         "value_type": f.value_type})
        seen |= keys
        out.append({
            "id": p.id, "code": p.code,
            "name_ar": p.name_ar, "name_en": p.name_en,
            "monthly": str(tier.price_per_employee_monthly) if tier else None,
            "annual": str(tier.price_per_employee_yearly) if tier else None,
            "setup_fee": str(p.setup_fee),
            "trial_days": p.trial_days,
            "min_employees": p.min_billable_employees,
            "features_new": rows,
            "inherits_from": (plans[plans.index(p) - 1].name_ar
                              if plans.index(p) > 0 else ""),
        })
    return Response({"plans": out})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def price_quote(request):
    """
    عرض سعر — {"plan_id", "employees", "cycle", "with_setup"}.

    يُحسب لحظيًّا وهو يكتب العدد، فلا مفاجأة عند الدفع.
    """
    Gate.require(request.user, "account.view")
    d = request.data
    plan = Plan.objects.filter(id=d.get("plan_id"), is_active=True).first()
    if plan is None:
        return Response({"detail": "الباقة غير متاحة"},
                        status=status.HTTP_404_NOT_FOUND)
    cycle = d.get("cycle") or BillingCycle.MONTHLY
    if cycle not in BillingCycle.values:
        return Response({"detail": "دورة غير معروفة"}, status=400)
    try:
        employees = int(d.get("employees") or 0)
    except (TypeError, ValueError):
        return Response({"detail": "عدد غير صحيح"}, status=400)

    try:
        q = billing.quote(plan=plan, employees=employees, cycle=cycle,
                          with_setup=bool(d.get("with_setup")))
    except billing.BillingError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(q)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    """
    اشتراكي — حالته وأيامه المتبقّية وعدده المشترَك به.

    ومن تجاوز عدده المشترَك به يرى الفرق المستحقّ بالأيام قبل أن
    يُطالَب به — فلا فاتورة تفاجئه.
    """
    from apps.accounts.models_billing_v2 import AccountSubscription
    from apps.employees.models import Employment, EmploymentStatus

    Gate.require(request.user, "account.view")
    ctx = getattr(request, "account_ctx", None)
    account_id = getattr(ctx, "account_id", None)

    sub = AccountSubscription.objects.filter(
        account_id=account_id).select_related("plan").first()
    active = Employment.objects.filter(
        account_id=account_id, status=EmploymentStatus.ACTIVE).count()

    if sub is None:
        return Response({"has_subscription": False,
                         "active_employees": active})

    out = {
        "has_subscription": True,
        "state": sub.state,
        "state_label": sub.get_state_display(),
        "plan": sub.plan.name_ar if sub.plan else None,
        "plan_id": sub.plan_id,
        "cycle": sub.cycle,
        "subscribed_employees": sub.subscribed_employees,
        "active_employees": active,
        "trial_ends_at": sub.trial_ends_at,
        "period_end": sub.current_period_end,
        "days_remaining": billing.days_remaining(sub),
        "auto_renew": sub.auto_renew,
    }

    over = active - (sub.subscribed_employees or 0)
    if over > 0 and sub.plan:
        try:
            out["overage"] = billing.prorated_addition(
                subscription=sub, added=over)
        except billing.BillingError as e:
            out["overage_error"] = str(e)
    return Response(out)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pay_overage(request):
    """
    دفع فرق الموظفين الزائدين (ق-108).

    من زاد موظفوه على عدده المشترَك به يدفع الفرق **بالأيام
    المتبقّية** — ثم يُرفع عدده المشترَك به، فلا يُطالَب به ثانيةً
    في نفس الفترة.

    والفاتورة تُنشأ بمبلغ الفرق وحده — لا بفاتورة فترة كاملة.
    """
    from django.conf import settings
    from django.db import transaction

    from apps.accounts.models_billing_v2 import (
        AccountSubscription, Invoice, InvoiceLine, InvoiceStatus)
    from apps.employees.models import Employment, EmploymentStatus

    Gate.require(request.user, "account.manage")
    ctx = getattr(request, "account_ctx", None)
    account_id = getattr(ctx, "account_id", None)

    sub = AccountSubscription.objects.filter(
        account_id=account_id).select_related("plan").first()
    if sub is None or sub.plan is None:
        return Response({"detail": "لا اشتراك فعّال"},
                        status=status.HTTP_404_NOT_FOUND)

    active = Employment.objects.filter(
        account_id=account_id, status=EmploymentStatus.ACTIVE).count()
    added = active - (sub.subscribed_employees or 0)
    if added <= 0:
        return Response({"detail": "لا زيادة تستوجب دفعًا"}, status=400)

    try:
        calc = billing.prorated_addition(subscription=sub, added=added)
    except billing.BillingError as e:
        return Response({"detail": str(e)}, status=400)

    amount = Decimal(calc["amount"])
    if amount <= 0:
        # عبَر لشريحة أرخص أو لا فرق — يُرفع عدده بلا مطالبة
        AccountSubscription.objects.filter(id=sub.id).update(
            subscribed_employees=active)
        return Response({"paid": False, "free": True,
                         "employees": active,
                         "detail": "لا مبلغ مستحقّ — رُفع عددك"})

    vat = billing.r2(amount * Decimal(str(billing.quote(
        plan=sub.plan, employees=1, cycle=sub.cycle)["vat_rate"])))

    with transaction.atomic():
        inv = Invoice.objects.create(
            account_id=account_id, invoice_no=billing._next_invoice_no(),
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            cycle=sub.cycle, subtotal=amount,
            headcount=added, status=InvoiceStatus.DRAFT,
            is_overage=True, overage_employees=added)
        InvoiceLine.objects.create(
            invoice=inv,
            description_ar=(f"إضافة {added} موظفًا — "
                            f"{calc['days_remaining']} يومًا متبقّية"),
            quantity=added, unit_price=billing.r2(amount / added),
            amount=amount)
        inv.total_before_vat = amount
        inv.vat_amount = vat
        inv.total = billing.r2(amount + vat)
        inv.save()
        billing.issue_invoice(inv)

    return Response({
        "invoice_id": inv.id,
        "invoice_no": inv.invoice_no,
        "added": added,
        "employees_after": active,
        "days_remaining": calc["days_remaining"],
        "before_vat": str(inv.total_before_vat),
        "vat_amount": str(inv.vat_amount),
        "total": str(inv.total),
        "publishable_key": settings.MOYASAR_PUBLISHABLE_KEY,
        "callback_url": settings.MOYASAR_CALLBACK_URL,
        "amount_halalas": int(inv.total * 100),
    }, status=status.HTTP_201_CREATED)


# ══════════ الأسعار للعامّة (ق-116) ══════════
#
# صفحة الأسعار تُفتح **قبل التسجيل** ويُربط إليها من الموقع
# الرئيسيّ — فلا توثيق لها. ولا تكشف شيئًا: الباقات المعروضة
# وأسعارها معلنة بطبيعتها.

@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def public_pricing(request):
    """الباقات المعروضة بمزاياها التراكمية — بلا توثيق."""
    from apps.accounts.models_platform import get_settings

    feats = {f.feature_key: f for f in Feature.objects.all()}
    plans = list(Plan.objects.filter(is_public=True, is_active=True)
                 .order_by("tier_order", "id"))

    out = []
    seen = set()
    for p in plans:
        tier = p.price_tiers.order_by("from_employees").first()
        keys = set(p.features.values_list("feature_key", flat=True))
        rows = []
        for k in sorted(keys - seen):
            f = feats.get(k)
            if f is None:
                continue
            rows.append({"key": k, "name_ar": f.name_ar,
                         "name_en": f.name_en,
                         "value": p.features.get(feature_key=k).value,
                         "value_type": f.value_type})
        seen |= keys
        out.append({
            "id": p.id, "code": p.code,
            "name_ar": p.name_ar, "name_en": p.name_en,
            "monthly": str(tier.price_per_employee_monthly) if tier else None,
            "annual": str(tier.price_per_employee_yearly) if tier else None,
            "setup_fee": str(p.setup_fee),
            "min_employees": p.min_billable_employees,
            "features_new": rows,
            "inherits_from": (plans[plans.index(p) - 1].name_ar
                              if plans.index(p) > 0 else ""),
        })

    st = get_settings()
    return Response({
        "plans": out,
        "vat_rate": str(getattr(st, "vat_rate", 15)),
        "trial_days": 7,
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def public_quote(request):
    """
    عرض سعر للزائر — بمعاملات الرابط لا بجسم الطلب.

    والحساب في الخادم كما في صفحة المشترك: الضريبة ورسم الإعداد
    قرارات نظامية، وحسابها مرّتين يفتح باب اختلافهما.
    """
    plan = Plan.objects.filter(id=request.GET.get("plan_id"),
                               is_public=True, is_active=True).first()
    if plan is None:
        return Response({"detail": "الباقة غير متاحة"},
                        status=status.HTTP_404_NOT_FOUND)

    cycle = request.GET.get("cycle") or BillingCycle.MONTHLY
    if cycle not in BillingCycle.values:
        return Response({"detail": "دورة غير معروفة"}, status=400)
    try:
        employees = int(request.GET.get("employees") or 0)
    except (TypeError, ValueError):
        return Response({"detail": "عدد غير صحيح"}, status=400)
    if employees > 100000:
        return Response({"detail": "عدد كبير — تواصل معنا"}, status=400)

    try:
        return Response(billing.quote(
            plan=plan, employees=employees, cycle=cycle,
            with_setup=request.GET.get("with_setup") == "1"))
    except billing.BillingError as e:
        return Response({"detail": str(e)}, status=400)
