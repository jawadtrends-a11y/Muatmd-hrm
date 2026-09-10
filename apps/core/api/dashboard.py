"""
لوحة الرئيسية (ق-106).

ثلاثة مسارات:
  · GET  /api/me/dashboard/catalog/  — المتاح لدوره وما اختاره
  · PUT  /api/me/dashboard/          — يحفظ اختياره وترتيبه
  · GET  /api/me/dashboard/data/     — بيانات الودجتات المعروضة

والبيانات تُطلب بالمفاتيح المعروضة وحدها: من يرى ثلاث ودجتات لا
تُحسب له الثلاثون.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.models_dashboard import DashboardPreference
from apps.core.widgets import (
    GROUPS, WIDGETS_BY_KEY, allowed_widgets, default_keys)


def _locale(request):
    from apps.core.i18n import request_locale
    return request_locale(request)


def _scopes(user, perms):
    """نطاق كل صلاحية — به تُحجب ودجتات الفريق عمّن نطاقه own."""
    return {k: Gate.check(user, k).scope.value for k in perms}


def _my_layout(user, perms, scopes):
    """
    [(مفتاح، حجم أو None)] — اختياره إن خصّص، وإلا افتراضيّ دوره.

    والحجم None يعني «حجم الودجت الأصليّ» — فمن لم يسحب المقبض
    يبقى على ما صُمّمت له.
    """
    allowed = {w.key for w in allowed_widgets(perms, scopes)}
    # معزول ذاتيًا: مقيَّد بالمستخدم نفسه — لا يقرأ تفضيل غيره
    pref = DashboardPreference.objects.filter(user=user).first()
    if pref and pref.widget_keys:
        out = []
        for item in pref.widget_keys:
            k = item if isinstance(item, str) else (item or {}).get("key")
            sz = None if isinstance(item, str) else (item or {}).get("size")
            if k in allowed:
                out.append((k, sz))
        if out:
            return out
    return [(k, None) for k in default_keys(perms, scopes)]


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def dashboard_prefs(request):
    perms = Gate.accessible_permissions(request.user)
    scopes = _scopes(request.user, perms)
    loc = _locale(request)

    if request.method == "PUT":
        keys = request.data.get("widget_keys")
        if not isinstance(keys, list):
            return Response({"detail": "قائمة الودجتات مطلوبة"}, status=400)
        allowed = {w.key for w in allowed_widgets(perms, scopes)}
        sizes = {"sm", "md", "lg"}
        clean = []
        for item in keys[:20]:
            # يُقبل شكلان: "key" أو {"key": ..., "size": ...} — فالحجم
            # يختاره المستخدم بسحب المقبض، ويُحفظ مع ترتيبه.
            if isinstance(item, str):
                k, sz = item, None
            elif isinstance(item, dict):
                k, sz = item.get("key"), item.get("size")
            else:
                continue
            if k not in allowed:
                continue
            clean.append({"key": k, "size": sz if sz in sizes else None})
        m = getattr(request.user, "account_membership", None)
        DashboardPreference.objects.update_or_create(
            user=request.user,
            defaults={"widget_keys": clean,
                      "account_id": getattr(m, "account_id", None)})
        return Response({"widget_keys": clean})

    layout = _my_layout(request.user, perms, scopes)
    mine = [k for k, _ in layout]
    return Response({
        "selected": mine,
        "layout": [{"key": k, "size": sz} for k, sz in layout],
        "groups": [
            {"key": g, "name": (GROUPS[g][1] if loc == "en" else GROUPS[g][0])}
            for g in GROUPS
        ],
        "available": [
            {"key": w.key,
             "name": w.name_en if loc == "en" else w.name_ar,
             "size": w.size, "group": w.group,
             "selected": w.key in mine}
            for w in allowed_widgets(perms, scopes)
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_data(request):
    """بيانات الودجتات المعروضة — لا الثلاثين."""
    # ق-123: لوحات القيادة المخصّصة ميزةٌ تُشترى.
    from apps.core.features.gate import Features

    ctx = getattr(request, "account_ctx", None)
    Features.require(getattr(ctx, "active_company_id", None),
                     "custom_dashboards")
    from apps.core.services.widget_data import build

    perms = Gate.accessible_permissions(request.user)
    scopes = _scopes(request.user, perms)
    keys = request.GET.get("keys")
    if keys:
        allowed = {w.key for w in allowed_widgets(perms, scopes)}
        wanted = [k for k in keys.split(",") if k in allowed]
    else:
        wanted = [k for k, _ in _my_layout(request.user, perms, scopes)]

    loc = _locale(request)
    saved = {k: sz for k, sz in _my_layout(request.user, perms, scopes) if sz}
    out = {}
    for k in wanted:
        spec = WIDGETS_BY_KEY.get(k)
        if spec is None:
            continue
        try:
            out[k] = {
                "name": spec.name_en if loc == "en" else spec.name_ar,
                "size": saved.get(k, spec.size),
                **(build(k, request) or {}),
            }
        except Exception as e:                              # noqa: BLE001
            # ودجت تعطّلت لا تُسقط اللوحة: البقية تُعرض، وهي
            # تقول «تعذّر» بدل شاشة بيضاء.
            out[k] = {"name": spec.name_ar,
                      "size": saved.get(k, spec.size),
                      "error": str(e)[:120]}
    return Response(out)
