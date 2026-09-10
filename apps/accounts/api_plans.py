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

from apps.accounts.api_admin import _log, requires
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


# ══════════ إدارة المزايا (ق-125) ══════════
#
# **التحكّم الكامل**: تُضاف الميزة وتُعدَّل وتُفعَّل من اللوحة بلا
# نشر. ⚠️ **إلا الحراسة** — فهي حقيقةٌ تقنية لا تفضيل مشغّل:
# ميزةٌ بلا حارس في الكود لا تصير محروسة بضغطة زرّ.

@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("accounts.view")
def admin_features(request):
    """سجل المزايا — عرضًا وإضافة."""
    if request.method == "GET":
        rows = []
        for f in Feature.objects.order_by("module", "sort_order", "id"):
            rows.append({
                "id": f.id,
                "feature_key": f.feature_key,
                "module": f.module,
                "name_ar": f.name_ar,
                "name_en": f.name_en,
                "description_ar": f.description_ar,
                "value_type": f.value_type,
                "sort_order": f.sort_order,
                "is_active": f.is_active,
                "is_implemented": f.is_implemented,
                "guarded_at": f.guarded_at,
                "plans": list(
                    Plan.objects.filter(
                        features__feature_key=f.feature_key
                    ).values_list("code", flat=True)),
            })
        return Response({
            "features": rows,
            "modules": sorted({f["module"] for f in rows}),
            "implemented": sum(1 for f in rows if f["is_implemented"]),
            "total": len(rows),
        })

    d = request.data
    key = str(d.get("feature_key") or "").strip()
    if not key or not str(d.get("name_ar") or "").strip():
        return Response({"detail": "المفتاح والاسم مطلوبان"}, status=400)
    if Feature.objects.filter(feature_key=key).exists():
        return Response({"detail": "المفتاح مستعمل"}, status=409)

    f = Feature.objects.create(
        feature_key=key,
        module=d.get("module") or "other",
        name_ar=d.get("name_ar", ""),
        name_en=d.get("name_en", ""),
        description_ar=d.get("description_ar", ""),
        value_type=d.get("value_type") or "bool",
        sort_order=int(d.get("sort_order") or 999),
        # ⚠️ الجديدة **غير محروسة** حتى يُكتب لها كود — فلا تُباع
        is_implemented=False, guarded_at="")
    _log(request, "feature.create", detail={"key": key})
    return Response({"id": f.id, "feature_key": f.feature_key},
                    status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("accounts.view")
def admin_feature_detail(request, feature_id):
    """تعديل ميزة أو حذفها — والمربوطة بباقة لا تُحذف."""
    f = Feature.objects.filter(id=feature_id).first()
    if f is None:
        return Response({"detail": "غير موجودة"},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        used = PlanFeature.objects.filter(feature_key=f.feature_key).count()
        if used:
            return Response(
                {"detail": f"مربوطة بـ{used} باقة — افصلها أوّلًا",
                 "code": "feature_in_use"}, status=409)
        if f.is_implemented:
            return Response(
                {"detail": "محروسة في الكود — حذفها يترك حارسًا بلا ميزة",
                 "code": "feature_guarded"}, status=409)
        _log(request, "feature.delete", detail={"key": f.feature_key})
        f.delete()
        return Response({"deleted": True})

    d = request.data
    for fld in ("module", "name_ar", "name_en", "description_ar"):
        if fld in d:
            setattr(f, fld, str(d[fld] or ""))
    if "value_type" in d and d["value_type"] in ("bool", "int", "text"):
        f.value_type = d["value_type"]
    if "sort_order" in d:
        f.sort_order = int(d["sort_order"] or 0)
    if "is_active" in d:
        f.is_active = bool(d["is_active"])
    # ⚠️ is_implemented و guarded_at لا يُعدَّلان من اللوحة —
    # فالحراسة من الكود، وادّعاؤها بضغطة زرّ يبيع وهمًا.
    f.save()
    _log(request, "feature.update", detail={"key": f.feature_key})
    return Response({"id": f.id, "feature_key": f.feature_key})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("accounts.view")
def admin_features_sync(request):
    """
    إعادة زرع الكتالوج — تُحدّث الحراسة ولا تدوس تعديلاتك.

    فبعد نشرٍ يضيف حارسًا جديدًا، تُشغَّل مرّةً فتُعلَّم الميزة
    محروسةً.
    """
    from apps.accounts.services.plans import sync_feature_registry

    out = sync_feature_registry()
    _log(request, "feature.sync", detail=out)
    return Response(out)
