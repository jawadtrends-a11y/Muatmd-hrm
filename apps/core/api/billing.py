"""
API الاشتراكات والباقات.

الفواتير الضريبية تصدر من محاسبة معتمد وحده — هذه النقاط للعرض
والتقدير فقط. لا نموذج فاتورة في HRM.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models_billing import CompanySubscription, Plan
from apps.core.access.gate import Gate
from apps.core.features.catalog import FEATURES, FEATURES_BY_KEY
from apps.core.features.gate import Features


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def plan_catalog(request):
    """الباقات المعروضة بمزاياها وأسعارها."""
    Gate.require(request.user, "account.view")
    plans = (Plan.objects.filter(is_active=True, is_public=True)
             .prefetch_related("features", "price_tiers"))
    return Response([
        {
            "code": p.code, "name_ar": p.name_ar, "tier_order": p.tier_order,
            "trial_days": p.trial_days,
            "min_billable_employees": p.min_billable_employees,
            "base_fee_monthly": str(p.base_fee_monthly),
            "price_tiers": [
                {"from": t.from_employees, "to": t.to_employees,
                 "monthly": str(t.price_per_employee_monthly)}
                for t in p.price_tiers.all()
            ],
            "features": [
                {"key": f.feature_key,
                 "name_ar": (FEATURES_BY_KEY[f.feature_key].name_ar
                             if f.feature_key in FEATURES_BY_KEY else f.feature_key),
                 "value": f.value}
                for f in p.features.all()
            ],
        }
        for p in plans
    ])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    """اشتراك الشركة ومزاياها — المقفلة تُعرض لا تُخفى."""
    Gate.require(request.user, "account.view")
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    qs = Gate.filter_queryset(
        request.user, "account.view",
        CompanySubscription.objects.filter(company_id=company_id),
    )
    sub = qs.select_related("plan").first()
    bundle = Features.bundle(company_id)

    features = [
        {
            "key": s.key, "name_ar": s.name_ar, "module": s.module,
            "value_type": s.value_type, "is_core": s.is_core,
            "enabled": bundle.get(s.key) not in (None, False, "false", "0", 0),
            "value": bundle.get(s.key),
        }
        for s in FEATURES
    ]

    return Response({
        "subscription": None if sub is None else {
            "plan_code": sub.plan.code, "plan_name_ar": sub.plan.name_ar,
            "tier_order": sub.plan.tier_order, "status": sub.status,
            "billing_cycle": sub.billing_cycle,
            "period_start": sub.current_period_start,
            "period_end": sub.current_period_end,
            "trial_ends_on": sub.trial_ends_on,
            "allows_writes": sub.allows_writes,
            "allows_payroll": sub.allows_payroll,
            "exports_always_allowed": True,
        },
        "features": features,
        "locked_count": sum(1 for f in features if not f["enabled"]),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def billing_estimate(request):
    """
    تقدير مستحق الفترة — شفافية تمنع النزاعات.

    هذا تقدير لا فاتورة. الفاتورة الضريبية تصدر من محاسبة معتمد.
    """
    Gate.require(request.user, "account.manage")
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    from apps.accounts.services.invoicing import is_invoicing_ready
    from apps.accounts.services.subscriptions import compute_charge

    qs = Gate.filter_queryset(
        request.user, "account.manage",
        CompanySubscription.objects.filter(
            company_id=company_id,
            status__in=["trial", "active", "past_due", "grace"]),
    )
    sub = qs.select_related("plan").first()
    if sub is None:
        return Response({"detail": "لا اشتراك نشط"}, status=404)

    line = compute_charge(sub)
    return Response({
        "billed_headcount": line.billed_headcount,
        "unit_price": str(line.unit_price),
        "base_fee": str(line.base_fee),
        "subtotal": str(line.total),
        "currency": "SAR",
        "note": "المبلغ قبل الضريبة. الفاتورة الضريبية تصدر من محاسبة معتمد.",
        "tax_invoicing_ready": is_invoicing_ready(),
        "explanation": line.snapshot,
    })
