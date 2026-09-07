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



#: هل يُقبل الدخول باسم المستخدم؟ يبقى True للحسابات القائمة
#: وللاختبارات — ويُجعل False حين تُستغنى عنه (ق-94)
ALLOW_USERNAME_LOGIN = True


def _normalize_mobile(raw):
    """
    الجوال بصيغه الثلاث → صيغة واحدة للمطابقة (ق-94).

    05xxxxxxxx و+9665xxxxxxxx و9665xxxxxxxx رقم واحد — فمن يكتبه
    بصيغة يدخل، ولا يُردّ لاختلاف كتابة.
    """
    d = "".join(ch for ch in raw if ch.isdigit())
    if d.startswith("00966"):
        d = d[5:]
    elif d.startswith("966"):
        d = d[3:]
    elif d.startswith("0"):
        d = d[1:]
    return "+966" + d if d else ""


def _resolve_identifier(raw):
    """
    اسم المستخدم من البريد أو الهوية أو الجوال (ق-94).

    الموظف يدخل بما يعرفه لا باسم يُخترع له. والمعرّف غير حسّاس
    للحالة، وكلمة المرور حسّاسة.

    وعند التعارض يُمنع الدخول: الدخول لحساب غيرك خطأ لا يُغتفر.
    """
    from django.contrib.auth.models import User

    from apps.employees.models import Person

    ident = (raw or "").strip()
    if not ident:
        return None, ""

    # اسم مستخدم صريح — الحسابات القائمة تُكمل بأسمائها.
    #
    # ويُوقَف بجعل ALLOW_USERNAME_LOGIN = False: الاسم يُولَّد
    # داخليًّا ولا يُعرض، فمن لا يعرفه لا يفقد شيئًا (ق-94).
    if ALLOW_USERNAME_LOGIN:
        u = User.objects.filter(username__iexact=ident).first()
        if u:
            return u.username, ""

    # البحث بدالة تتجاوز العزل: جدول الأشخاص محميّ بـRLS الذي
    # يتطلب سياق حساب — والسياق لا يُضبط إلا بعد أن نعرف من هو.
    # والدالة تُرجع اسم المستخدم وحده لا بيانات عمل (ق-94).
    from django.db import connection

    names = set()
    candidates = [ident]

    mob = _normalize_mobile(ident)
    if mob and mob != ident:
        candidates.append(mob)

    with connection.cursor() as cur:
        for value in candidates:
            cur.execute(
                "SELECT username FROM app_lookup_login_identifier(%s)",
                [value])
            for row in cur.fetchall():
                names.add(row[0])

    # والبريد قد يكون على حساب المستخدم نفسه لا على ملف الموظف
    if "@" in ident:
        names.update(User.objects.filter(
            email__iexact=ident).values_list("username", flat=True))

    if len(names) > 1:
        return None, "هذا المعرّف يخصّ أكثر من حساب — استخدم بريدك"
    if names:
        return names.pop(), ""
    return None, ""


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """دخول العميل — يرجع الرمز مرة واحدة."""
    # المعرّف: بريد أو هوية أو جوال أو اسم مستخدم (ق-94)
    ident = (request.data.get("identifier")
             or request.data.get("username") or "").strip()
    password = request.data.get("password") or ""

    if not ident or not password:
        return Response({"detail": "المعرّف وكلمة المرور مطلوبان"},
                        status=400)

    username, conflict = _resolve_identifier(ident)
    if conflict:
        return Response({"detail": conflict, "code": "ambiguous"},
                        status=409)
    if username is None:
        # لا نُفصح أيّهما خطأ: المعرّف أم كلمة المرور
        return Response({"detail": "المعرّف أو كلمة المرور غير صحيحة",
                         "code": "auth_failed"}, status=401)

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
