"""
مسارات مصادقة العملاء (ق-53).

الرمز يخدم الويب والجوال معًا.
"""
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models_tokens import AuthToken, DeviceKind
from apps.accounts.services import auth_tokens as auth


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return (fwd.split(",")[0].strip() if fwd
            else request.META.get("REMOTE_ADDR"))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """دخول العميل — يرجع الرمز مرة واحدة."""
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""

    if not username or not password:
        return Response({"detail": "اسم المستخدم وكلمة المرور مطلوبان"},
                        status=400)

    device = request.data.get("device_kind", DeviceKind.WEB)
    if device not in DeviceKind.values:
        device = DeviceKind.WEB

    try:
        user, raw, token = auth.login(
            username=username, password=password, device_kind=device,
            device_name=request.data.get("device_name", "")
            or request.META.get("HTTP_USER_AGENT", "")[:150],
            ip=_ip(request))
    except auth.LoginError as e:
        return Response({"detail": str(e), "code": "auth_failed"},
                        status=401)

    person = getattr(user, "person", None)
    return Response({
        "token": raw,
        "expires_at": token.expires_at,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": (person.display_name if person
                             else (user.get_full_name() or user.username)),
            "email": user.email,
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """خروج — يُبطل الرمز الحالي وحده."""
    auth.logout(getattr(request, "auth_token_raw", None) or request.auth)
    return Response({"logged_out": True})


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def sessions_view(request):
    """
    أجهزتي — يرى المستخدم رموزه النشطة ويُبطل ما يشاء.

    مهم أمنيًا: من فقد جهازه يُبطل رمزه بلا تغيير كلمة المرور.
    """
    if request.method == "DELETE":
        token_id = request.GET.get("id")
        if token_id == "all":
            n = auth.revoke_all(
                request.user,
                except_token=getattr(request, "auth_token_raw", None))
            return Response({"revoked": n})

        from django.utils import timezone
        n = AuthToken.objects.filter(
            id=token_id, user=request.user, revoked_at__isnull=True
        ).update(revoked_at=timezone.now())
        return Response({"revoked": n})

    current = getattr(request, "auth_token_raw", None)
    current_hash = auth.hash_token(current) if current else ""

    return Response([
        {
            "id": t.id,
            "prefix": t.prefix,
            "device_kind": t.device_kind,
            "device_label": t.get_device_kind_display(),
            "device_name": t.device_name[:80],
            "ip": t.ip_address,
            "created_at": t.created_at,
            "last_used_at": t.last_used_at,
            "expires_at": t.expires_at,
            "is_current": t.token_hash == current_hash,
        }
        for t in AuthToken.objects.filter(
            user=request.user, revoked_at__isnull=True
        ).order_by("-created_at")[:20]
    ])
