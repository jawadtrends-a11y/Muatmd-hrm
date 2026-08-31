"""
مصادقة لوحة المنصة (ق-51).

معزولة تمامًا عن مصادقة العملاء: جلسة منفصلة، وكوكي منفصل،
وتحقق ثنائي إلزامي.
"""
import base64
import hashlib
import hmac
import logging
import secrets
import struct
import time
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models_admin import (
    PlatformAuditLog, PlatformSession, PlatformUser,
)

logger = logging.getLogger("muatmd.platform")

SESSION_HOURS = 8
MAX_FAILED = 5
LOCK_MINUTES = 30
COOKIE_NAME = "muatmd_platform_session"


class AuthError(Exception):
    pass


class TotpRequired(AuthError):
    """كلمة المرور صحيحة — ينقص التحقق الثنائي."""

    def __init__(self, challenge_token):
        self.challenge_token = challenge_token
        super().__init__("يلزم رمز التحقق الثنائي")


# ══════════ التحقق الثنائي ══════════

def generate_totp_secret():
    """سرّ جديد بصيغة base32 — يُعرض مرة واحدة عند التفعيل."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def totp_uri(user, issuer="Muatmd HRM"):
    """رابط يُحوَّل لرمز QR في تطبيق المصادقة."""
    return (f"otpauth://totp/{issuer}:{user.email}"
            f"?secret={user.totp_secret}&issuer={issuer}&digits=6&period=30")


def verify_totp(secret, code, window=1):
    """
    يتحقق من رمز TOTP.

    window=1 يقبل الرمز السابق والتالي — تسامحًا مع فرق التوقيت.
    """
    if not secret or not code:
        return False
    code = str(code).strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False

    try:
        key = base64.b32decode(secret, casefold=True)
    except Exception:  # noqa: BLE001
        return False

    counter = int(time.time()) // 30
    for offset in range(-window, window + 1):
        if _hotp(key, counter + offset) == code:
            return True
    return False


def _hotp(key, counter):
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    idx = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[idx:idx + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


# ══════════ الدخول ══════════

def _log(user, action, *, success=True, ip=None, detail=None,
         user_name=None):
    PlatformAuditLog.objects.create(
        user=user, user_name=(user_name or (user.full_name if user else "?")),
        action=action, success=success, ip_address=ip, detail=detail or {})


def authenticate(*, username, password, totp_code=None, ip=None,
                 user_agent=""):
    """
    دخول لوحة المنصة.

    التحقق الثنائي إلزامي لمن فعّله — والحساب يفتح بيانات كل
    العملاء فلا استثناء منه (ق-51).
    """
    user = PlatformUser.objects.filter(username__iexact=username).first()

    if user is None:
        _log(None, "login", success=False, ip=ip,
             user_name=username, detail={"reason": "مستخدم غير موجود"})
        raise AuthError("بيانات الدخول غير صحيحة")

    if not user.is_active:
        _log(user, "login", success=False, ip=ip,
             detail={"reason": "حساب معطّل"})
        raise AuthError("الحساب معطّل")

    if user.is_locked:
        mins = int((user.locked_until - timezone.now()).total_seconds() / 60)
        _log(user, "login", success=False, ip=ip,
             detail={"reason": "مقفل"})
        raise AuthError(f"الحساب مقفل — أعد المحاولة بعد {mins} دقيقة")

    if ip and not user.ip_allowed(ip):
        _log(user, "login", success=False, ip=ip,
             detail={"reason": "عنوان غير مسموح"})
        raise AuthError("الدخول من هذا العنوان غير مسموح")

    if not user.check_password(password):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED:
            user.locked_until = timezone.now() + timedelta(
                minutes=LOCK_MINUTES)
            user.failed_attempts = 0
        user.save(update_fields=["failed_attempts", "locked_until",
                                 "updated_at"])
        _log(user, "login", success=False, ip=ip,
             detail={"reason": "كلمة مرور خاطئة"})
        raise AuthError("بيانات الدخول غير صحيحة")

    if user.totp_enabled:
        if not totp_code:
            raise TotpRequired(challenge_token=_challenge(user))
        if not verify_totp(user.totp_secret, totp_code):
            user.failed_attempts += 1
            user.save(update_fields=["failed_attempts", "updated_at"])
            _log(user, "login", success=False, ip=ip,
                 detail={"reason": "رمز تحقق خاطئ"})
            raise AuthError("رمز التحقق غير صحيح")

    # ── نجح الدخول ──
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = timezone.now()
    user.last_login_ip = ip
    user.save(update_fields=["failed_attempts", "locked_until",
                             "last_login_at", "last_login_ip", "updated_at"])

    session = PlatformSession.objects.create(
        user=user, token=secrets.token_urlsafe(48),
        ip_address=ip, user_agent=user_agent[:300],
        expires_at=timezone.now() + timedelta(hours=SESSION_HOURS))

    _log(user, "login", ip=ip, detail={"session": session.id})
    return user, session


def _challenge(user):
    """رمز مؤقت يربط خطوتي الدخول."""
    raw = f"{user.id}:{int(time.time())}:{secrets.token_hex(8)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def resolve_session(token):
    """يحوّل رمز الجلسة لمستخدم — أو None."""
    if not token:
        return None
    session = PlatformSession.objects.filter(
        token=token).select_related("user").first()
    if session is None or not session.is_valid:
        return None
    return session.user


def logout(token):
    PlatformSession.objects.filter(token=token, revoked_at__isnull=True
                                   ).update(revoked_at=timezone.now())


def revoke_all_sessions(user):
    PlatformSession.objects.filter(
        user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now())


# ══════════ إدارة المستخدمين ══════════

def create_platform_user(*, username, email, full_name, password, role,
                         mobile="", created_by=None):
    """
    ينشئ مستخدم لوحة — التحقق الثنائي يُفعَّل في أول دخول.
    """
    if PlatformUser.objects.filter(username__iexact=username).exists():
        raise AuthError(f"اسم المستخدم مستخدم: {username}")
    if PlatformUser.objects.filter(email__iexact=email).exists():
        raise AuthError(f"البريد مستخدم: {email}")

    user = PlatformUser(username=username, email=email, full_name=full_name,
                        role=role, mobile_e164=mobile,
                        totp_secret=generate_totp_secret())
    user.set_password(password)
    user.save()

    _log(created_by, "platform_user.create",
         detail={"created": username, "role": role},
         user_name=(created_by.full_name if created_by else "النظام"))
    return user


def enable_totp(user, code):
    """يفعّل التحقق الثنائي بعد تأكيد رمز صحيح."""
    if not verify_totp(user.totp_secret, code):
        raise AuthError("رمز التحقق غير صحيح")
    user.totp_enabled = True
    user.save(update_fields=["totp_enabled", "updated_at"])
    _log(user, "totp.enable")
    return user
