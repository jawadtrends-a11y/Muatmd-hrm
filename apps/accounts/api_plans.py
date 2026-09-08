"""
إدارة الباقات من لوحة المنصّة (ق-108).

الأسماء والأسعار والمزايا يضبطها مالك المنصّة — فالباقة قرار
تجاريّ يتغيّر، ولا يُدفن في بذرة تحتاج نشرًا لتعديلها.

والمزايا كتالوجٌ ثابت في القاعدة (١٩ ميزة)، والخطة تُعلن أيّها
تشمل وبأي قيمة.
"""
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.api_admin import requires
from apps.accounts.models_billing import (
    Feature, Plan, PlanFeature, PlanPriceTier)


def _plan_json(p):
    return {
        "id": p.id, "code": p.code,
        "name_ar": p.name_ar, "name_en": p.name_en,
        "tier_order": p.tier_order,
        "base_fee_monthly": str(p.base_fee_monthly),
        "min_billable_employees": p.min_billable_employees,
        "max_employees": p.max_employees,
        "trial_days": p.trial_days,
        "is_public": p.is_public, "is_active": p.is_active,
        "tiers": [{
            "id": t.id,
            "from_employees": t.from_employees,
            "to_employees": t.to_employees,
            "monthly": str(t.price_per_employee_monthly),
            "yearly": str(t.price_per_employee_yearly),
        } for t in p.price_tiers.order_by("from_employees")],
        "features": {f.feature_key: f.value for f in p.features.all()},
    }


@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("accounts.view")
def plans(request):
    """
    قائمة الباقات مع كتالوج المزايا — وإنشاء باقة.

    القراءة بـaccounts.view، والإنشاء يفحص account.write فوقها:
    فالمطّلع يرى الأسعار ولا يغيّرها.
    """
    if request.method == "GET":
        return Response({
            "plans": [_plan_json(p) for p in
                      Plan.objects.order_by("tier_order", "id")],
            "features": [{
                "key": f.feature_key, "name_ar": f.name_ar,
                "name_en": f.name_en, "module": f.module,
                "value_type": f.value_type, "is_core": f.is_core,
            } for f in Feature.objects.order_by("module", "sort_order")],
        })

    if not request.platform_user.can("account.write"):
        return Response({"detail": "لا تملك تعديل الباقات"}, status=403)

    d = request.data
    code = str(d.get("code") or "").strip()
    if not code or not str(d.get("name_ar") or "").strip():
        return Response({"detail": "الرمز والاسم مطلوبان"}, status=400)
    if Plan.objects.filter(code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    p = Plan.objects.create(
        code=code,
        name_ar=d.get("name_ar", ""), name_en=d.get("name_en", ""),
        tier_order=int(d.get("tier_order") or 1),
        base_fee_monthly=Decimal(str(d.get("base_fee_monthly") or 0)),
        min_billable_employees=int(d.get("min_billable_employees") or 1),
        trial_days=int(d.get("trial_days") or 14),
        is_public=bool(d.get("is_public", True)),
        is_active=bool(d.get("is_active", True)),
    )
    return Response(_plan_json(p), status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("accounts.view")
def plan_detail(request, plan_id):
    p = Plan.objects.filter(id=plan_id).first()
    if p is None:
        return Response({"detail": "غير موجودة"},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(_plan_json(p))

    if not request.platform_user.can("account.write"):
        return Response({"detail": "لا تملك تعديل الباقات"}, status=403)

    if request.method == "DELETE":
        # الباقة المشترَك بها تُعطَّل ولا تُحذف: من اشترك بها لا
        # يفقد سجلّه، والفواتير الماضية تبقى مفهومة.
        from apps.accounts.models_billing_v2 import AccountSubscription
        if AccountSubscription.objects.filter(plan=p).exists():
            p.is_active = False
            p.is_public = False
            p.save(update_fields=["is_active", "is_public"])
            return Response({"deactivated": True,
                             "detail": "مشترَك بها — عُطّلت ولم تُحذف"})
        p.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "name_en"):
        if f in d:
            setattr(p, f, str(d[f] or "").strip())
    for f in ("tier_order", "min_billable_employees", "trial_days"):
        if f in d:
            try:
                setattr(p, f, int(d[f] or 0))
            except (TypeError, ValueError):
                pass
    if "max_employees" in d:
        p.max_employees = int(d["max_employees"]) if d["max_employees"] else None
    if "base_fee_monthly" in d:
        try:
            p.base_fee_monthly = Decimal(str(d["base_fee_monthly"] or 0))
        except InvalidOperation:
            pass
    for f in ("is_public", "is_active"):
        if f in d:
            setattr(p, f, bool(d[f]))
    p.save()

    # الشرائح تُستبدل كاملةً — أبسط من مطابقة صف بصف، والعدد صغير
    if isinstance(d.get("tiers"), list):
        p.price_tiers.all().delete()
        for t in d["tiers"]:
            try:
                PlanPriceTier.objects.create(
                    plan=p,
                    from_employees=int(t.get("from_employees") or 1),
                    to_employees=(int(t["to_employees"])
                                  if t.get("to_employees") else None),
                    price_per_employee_monthly=Decimal(
                        str(t.get("monthly") or 0)),
                    price_per_employee_yearly=Decimal(
                        str(t.get("yearly") or 0)),
                )
            except (TypeError, ValueError, InvalidOperation):
                continue

    # المزايا: ما أُرسل يُثبَّت، وما حُذف يُنزع
    if isinstance(d.get("features"), dict):
        valid = set(Feature.objects.values_list("feature_key", flat=True))
        sent = {k: str(v) for k, v in d["features"].items() if k in valid}
        p.features.exclude(feature_key__in=sent.keys()).delete()
        for k, v in sent.items():
            PlanFeature.objects.update_or_create(
                plan=p, feature_key=k, defaults={"value": v})

    return Response(_plan_json(p))
