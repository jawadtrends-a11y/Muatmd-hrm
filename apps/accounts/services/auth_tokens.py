"""
مصادقة العملاء بالرموز (ق-53).

رمز واحد للويب والجوال. منفصل عن جلسات لوحة المنصة (ق-51).
"""
import logging
from datetime import timedelta

from django.contrib.auth import authenticate as django_auth
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models_tokens import (
    AuthToken, DeviceKind, generate_token, hash_token,
)

logger = logging.getLogger("muatmd.auth")

MAX_FAILED = 6
LOCK_MINUTES = 15


class LoginError(Exception):
    pass


def _lifetime(device_kind):
    days = (AuthToken.WEB_DAYS if device_kind == DeviceKind.WEB
            else AuthToken.MOBILE_DAYS)
    return timezone.now() + timedelta(days=days)


def login(*, username, password, device_kind=DeviceKind.WEB,
          device_name="", ip=None):
    """
    يتحقق ويصدر رمزًا.

    الرمز الخام يُرجع مرة واحدة — لا يُحفظ نصًّا في القاعدة.
    """
    user = django_auth(username=username, password=password)
    if user is None:
        # المحاولة بالبريد إن لم ينجح باسم المستخدم
        by_email = User.objects.filter(email__iexact=username).first()
        if by_email:
            user = django_auth(username=by_email.username, password=password)

    if user is None:
        logger.warning("login_failed", extra={"username": username, "ip": ip})
        raise LoginError("بيانات الدخول غير صحيحة")

    if not user.is_active:
        raise LoginError("الحساب معطّل")

    raw, digest, prefix = generate_token()
    token = AuthToken.objects.create(
        user=user, token_hash=digest, prefix=prefix,
        device_kind=device_kind, device_name=device_name[:150],
        ip_address=ip, expires_at=_lifetime(device_kind))

    logger.info("login_ok", extra={"user_id": user.id, "ip": ip})
    return user, raw, token


def resolve(raw_token):
    """يحوّل الرمز الخام لمستخدم — أو None."""
    if not raw_token:
        return None
    token = AuthToken.objects.filter(
        token_hash=hash_token(raw_token)).select_related("user").first()
    if token is None or not token.is_valid:
        return None

    # تحديث آخر استخدام مرة كل ساعة فقط — لا كتابة بكل طلب
    now = timezone.now()
    if token.last_used_at is None or (now - token.last_used_at).seconds > 3600:
        AuthToken.objects.filter(id=token.id).update(last_used_at=now)

    return token.user


def logout(raw_token):
    if not raw_token:
        return False
    return AuthToken.objects.filter(
        token_hash=hash_token(raw_token), revoked_at__isnull=True
    ).update(revoked_at=timezone.now()) > 0


def revoke_all(user, except_token=None):
    """إبطال كل رموز المستخدم — عند تغيير كلمة المرور مثلًا."""
    qs = AuthToken.objects.filter(user=user, revoked_at__isnull=True)
    if except_token:
        qs = qs.exclude(token_hash=hash_token(except_token))
    return qs.update(revoked_at=timezone.now())


class TokenAuthentication(BaseAuthentication):
    """
    مصادقة DRF بترويسة Authorization: Bearer <token>.

    تعمل مع مصادقة الجلسة جنبًا إلى جنب — فلوحة الإدارة
    ولوحة Django تبقيان تعملان.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith(f"{self.keyword} "):
            return None

        raw = header[len(self.keyword) + 1:].strip()
        user = resolve(raw)
        if user is None:
            raise AuthenticationFailed("رمز الدخول غير صالح أو منتهٍ")

        request.auth_token_raw = raw
        return (user, raw)

    def authenticate_header(self, request):
        return self.keyword
