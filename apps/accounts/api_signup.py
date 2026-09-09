"""
مسارات التسجيل الذاتيّ واستعادة كلمة المرور (ق-113).

كلّها **عامّة بلا توثيق**: من يسجّل لا حساب له، ومن نسي كلمته لا
يستطيع الدخول. والحماية بالرمز المجزَّأ والمهلة القصيرة.
"""
import logging

from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.services import signup as svc

logger = logging.getLogger(__name__)


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd
            else request.META.get("REMOTE_ADDR"))


def _base_url(request):
    from django.conf import settings
    return (getattr(settings, "APP_BASE_URL", "")
            or f"https://{request.get_host()}")


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def signup(request):
    """طلب تسجيل شركة — يُرسل رابط تأكيد للبريد."""
    from apps.notifications.services.sender import send_email

    d = request.data
    try:
        req, raw = svc.create_signup(
            company_name=d.get("company_name"),
            full_name=d.get("full_name"),
            email=d.get("email"),
            mobile=d.get("mobile"),
            password=d.get("password"),
            ip=_ip(request))
    except svc.SignupError as e:
        return Response({"detail": str(e)}, status=400)

    link = f"{_base_url(request)}/signup/verify/{raw}"
    send_email(
        to=req.email,
        subject="تأكيد التسجيل في معتمد HRM",
        text=(f"مرحبًا {req.full_name}،\n\n"
              f"لتفعيل حساب «{req.company_name}» افتح الرابط:\n{link}\n\n"
              f"الرابط صالح ٤٨ ساعة. وإن لم تطلب التسجيل فتجاهل هذه "
              f"الرسالة."),
        html=(f"<p>مرحبًا {req.full_name}،</p>"
              f"<p>لتفعيل حساب <b>{req.company_name}</b>:</p>"
              f'<p><a href="{link}">تأكيد التسجيل</a></p>'
              f"<p>الرابط صالح ٤٨ ساعة.</p>"))

    return Response({
        "sent": True,
        "email": req.email,
        "detail": "أرسلنا رابط التأكيد لبريدك",
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def signup_verify(request, token):
    """تأكيد البريد — يُنشئ الحساب ومالكه."""
    try:
        out = svc.verify_signup(token, ip=_ip(request))
    except svc.SignupError as e:
        return Response({"detail": str(e)}, status=400)
    return Response({"created": True, **out})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def password_forgot(request):
    """
    طلب استعادة — الردّ **واحد** سواء وُجد البريد أم لا.

    ⚠️ وإلا صار المسار أداةً لكشف من له حساب عندنا.
    """
    from apps.notifications.services.sender import send_email

    user, raw = svc.request_reset(request.data.get("email"), ip=_ip(request))
    if user and raw:
        link = f"{_base_url(request)}/password/reset/{raw}"
        send_email(
            to=user.email,
            subject="استعادة كلمة المرور — معتمد HRM",
            text=(f"لضبط كلمة مرور جديدة افتح الرابط:\n{link}\n\n"
                  f"الرابط صالح ساعة واحدة. وإن لم تطلب ذلك فتجاهل "
                  f"هذه الرسالة — ولم يتغيّر شيء في حسابك."),
            html=(f'<p><a href="{link}">ضبط كلمة مرور جديدة</a></p>'
                  f"<p>الرابط صالح ساعة واحدة.</p>"))

    return Response({
        "sent": True,
        "detail": "إن كان لهذا البريد حساب فستصلك رسالة الاستعادة",
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset(request, token):
    """ضبط كلمة مرور جديدة بالرمز."""
    try:
        svc.apply_reset(token, request.data.get("password"))
    except svc.SignupError as e:
        return Response({"detail": str(e)}, status=400)
    return Response({"done": True, "detail": "غُيّرت كلمة المرور — سجّل دخولك"})
