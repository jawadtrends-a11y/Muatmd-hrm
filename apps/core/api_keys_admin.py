"""إدارة مفاتيح API من لوحة العميل (ق-151)."""
from datetime import date

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.core.models import ApiCallLog, ApiKey, ApiScope
from apps.core.services import api_keys as svc


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _json(k):
    return {
        "id": k.id, "name": k.name, "prefix": k.prefix,
        "scopes": k.scopes,
        "rate_limit_per_hour": k.rate_limit_per_hour,
        "is_active": k.is_active, "is_usable": k.is_usable,
        "expires_on": k.expires_on,
        "last_used_at": k.last_used_at,
        "last_used_ip": k.last_used_ip,
        "call_count": k.call_count,
        "revoked_at": k.revoked_at,
        "revoked_reason": k.revoked_reason,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def api_keys(request):
    """
    المفاتيح — عرضًا وإنشاءً.

    ⚠️ **والنصّ يُعرض مرّةً واحدة** عند الإنشاء.
    """
    Gate.require(request.user, "account.manage")
    Features.require(_company_id(request), "api_access")

    if request.method == "GET":
        qs = ApiKey.objects.filter(company_id=_company_id(request))
        return Response({
            "keys": [_json(k) for k in qs],
            "scopes": [{"value": v, "label": lbl}
                       for v, lbl in ApiScope.choices],
        })

    from apps.accounts.models import Company

    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    exp = None
    if d.get("expires_on"):
        try:
            exp = date.fromisoformat(str(d["expires_on"]))
        except ValueError:
            return Response({"detail": "تاريخ غير صالح"}, status=400)

    actor = getattr(request.user, "person", None)
    try:
        key, raw = svc.create_key(
            company=comp, name=d.get("name", ""),
            scopes=d.get("scopes") or [],
            rate_limit=d.get("rate_limit_per_hour") or 1000,
            expires_on=exp,
            by_person_id=actor.id if actor else None)
    except svc.ApiKeyError as e:
        return Response({"detail": str(e)}, status=400)

    out = _json(key)
    # ⚠️ **مرّةً واحدة** — ولا يُعاد بعدها
    out["key"] = raw
    out["warning"] = ("احفظ المفتاح الآن — لن يُعرض ثانيةً، "
                      "ومن فقده أنشأ غيره")
    return Response(out, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_key(request, key_id):
    """
    إيقاف مفتاح — ⚠️ **ولا يُحذف**: فسجلّ نداءاته حجّةٌ تبقى.
    """
    Gate.require(request.user, "account.manage")
    Features.require(_company_id(request), "api_access")

    k = ApiKey.objects.filter(
        id=key_id, company_id=_company_id(request)).first()
    if k is None:
        return Response({"detail": "غير موجود"}, status=404)

    try:
        svc.revoke(key=k, reason=request.data.get("reason", ""))
    except svc.ApiKeyError as e:
        return Response({"detail": str(e)}, status=409)
    return Response(_json(k))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def key_calls(request, key_id):
    """سجلّ نداءات مفتاح — للمراجعة."""
    Gate.require(request.user, "account.manage")
    Features.require(_company_id(request), "api_access")

    k = ApiKey.objects.filter(
        id=key_id, company_id=_company_id(request)).first()
    if k is None:
        return Response({"detail": "غير موجود"}, status=404)

    calls = ApiCallLog.objects.filter(api_key=k)[:200]
    return Response({
        "key": _json(k),
        "calls": [{
            "at": c.at, "path": c.path, "method": c.method,
            "status_code": c.status_code, "ip": c.ip,
        } for c in calls],
    })
