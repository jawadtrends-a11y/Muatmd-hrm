"""
التسجيل الذاتيّ واستعادة كلمة المرور (ق-113).

⚠️ **الرمز مجزَّأ في القاعدة** ويُرسل خامًا مرّةً واحدة بالبريد —
فمن قرأ القاعدة لا ينتحل أحدًا (كنمط ق-101).

⚠️ **ولا يُفشى وجود الحساب**: طلب الاستعادة يردّ الردّ نفسه سواء
وُجد البريد أم لا — وإلا صار أداةً لكشف عملائنا.
"""
import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from apps.accounts.models_signup import (
    PasswordReset, SignupRequest, SignupStatus)

logger = logging.getLogger(__name__)

SIGNUP_TTL_HOURS = 48
RESET_TTL_MINUTES = 60
# محاولات التسجيل من بريد واحد — يمنع إغراق المنصّة بطلبات وهمية
SIGNUP_MAX_PENDING = 3


class SignupError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_token():
    raw = secrets.token_urlsafe(32)
    return raw, _hash(raw)


# ══════════ التسجيل ══════════

@transaction.atomic
def create_signup(*, company_name, full_name, email, mobile, password,
                  ip=None):
    """
    ينشئ طلب تسجيل ويرجع (الطلب، الرمز الخام).

    ولا يُنشئ حسابًا: البريد يُؤكَّد أولًا (قرار جواد) — فالبريد
    غير المؤكَّد يملأ المنصّة بحسابات وهمية، ويحرم صاحبه من
    استعادة كلمة مروره حين ينساها.
    """
    email = (email or "").strip().lower()
    company_name = (company_name or "").strip()
    full_name = (full_name or "").strip()

    if not company_name or not full_name:
        raise SignupError("اسم الشركة واسم المسؤول مطلوبان")
    if "@" not in email:
        raise SignupError("بريد غير صحيح")
    if len(password or "") < 8:
        raise SignupError("كلمة المرور ثماني خانات فأكثر")

    if User.objects.filter(email__iexact=email).exists():
        raise SignupError("لهذا البريد حساب — سجّل الدخول أو استعد كلمتك")

    now = timezone.now()
    pending = SignupRequest.objects.filter(
        email__iexact=email, status=SignupStatus.PENDING,
        expires_at__gt=now)
    if pending.count() >= SIGNUP_MAX_PENDING:
        raise SignupError("طلبات كثيرة لهذا البريد — راجع بريدك")
    # طلبٌ جديد يُلغي سابقه: الرابط الأحدث وحده يعمل
    pending.update(status=SignupStatus.EXPIRED)

    raw, hashed = _new_token()
    req = SignupRequest.objects.create(
        company_name=company_name, full_name=full_name, email=email,
        mobile=(mobile or "").strip(),
        password_hash=make_password(password),
        token_hash=hashed,
        expires_at=now + timedelta(hours=SIGNUP_TTL_HOURS),
        ip=ip)
    return req, raw


def _slug_for(name, email):
    """معرّف حساب فريد — من البريد لا من الاسم العربيّ."""
    from apps.accounts.models import Account

    base = "".join(c for c in email.split("@")[0].lower()
                   if c.isalnum() or c == "-")[:40] or "co"
    if len(base) < 3:
        base = f"{base}-co"
    slug = base
    i = 1
    while Account.objects.filter(slug=slug).exists():
        i += 1
        slug = f"{base}-{i}"[:63]
    return slug


@transaction.atomic
def verify_signup(raw_token, ip=None):
    """
    يؤكّد البريد فيُنشئ الحساب ومالكه.

    والمنشئ **مالك الحساب** — والملكية تُنقل لاحقًا (ق-76).
    """
    from apps.accounts.models import Account, Company
    from apps.accounts.models_access import AccountMembership
    from apps.accounts.services.provisioning import provision_account

    req = SignupRequest.objects.filter(token_hash=_hash(raw_token)).first()
    if req is None:
        raise SignupError("رابط غير صالح")
    if req.status == SignupStatus.VERIFIED:
        raise SignupError("أُكّد هذا الطلب سابقًا — سجّل الدخول")
    if req.expires_at <= timezone.now():
        req.status = SignupStatus.EXPIRED
        req.save(update_fields=["status"])
        raise SignupError("انتهت صلاحية الرابط — سجّل من جديد")

    if User.objects.filter(email__iexact=req.email).exists():
        raise SignupError("لهذا البريد حساب — سجّل الدخول")

    result = provision_account(
        slug=_slug_for(req.company_name, req.email),
        display_name_ar=req.company_name,
        company_name_ar=req.company_name)

    user = User(username=req.email, email=req.email,
                first_name=req.full_name[:30])
    user.password = req.password_hash          # مجزَّأة سلفًا
    user.save()

    from apps.core.tenancy.context import account_scope

    with account_scope(result.account_id):
        AccountMembership.objects.create(
            user=user, account=Account.objects.get(id=result.account_id),
            active_company=Company.objects.get(id=result.company_id),
            is_account_owner=True)

    req.status = SignupStatus.VERIFIED
    req.verified_at = timezone.now()
    req.created_account_id = result.account_id
    req.save(update_fields=["status", "verified_at", "created_account_id"])

    logger.info("حساب جديد بالتسجيل الذاتيّ: %s", result.account_id)
    return {"account_id": result.account_id, "user_id": user.id,
            "username": user.username}


# ══════════ استعادة كلمة المرور ══════════

@transaction.atomic
def request_reset(email, ip=None):
    """
    يُنشئ طلب استعادة — ويرجع (المستخدم، الرمز) أو (None, None).

    ⚠️ لا يرفع خطأً إن لم يوجد البريد: الردّ واحد للمستخدم مهما
    كان، وإلا كُشف من له حساب عندنا.
    """
    email = (email or "").strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        return None, None

    now = timezone.now()
    # طلبٌ جديد يُبطل سابقه
    PasswordReset.objects.filter(
        user_id=user.id, used_at__isnull=True, expires_at__gt=now
    ).update(used_at=now)

    raw, hashed = _new_token()
    PasswordReset.objects.create(
        user_id=user.id, token_hash=hashed,
        expires_at=now + timedelta(minutes=RESET_TTL_MINUTES), ip=ip)
    return user, raw


@transaction.atomic
def apply_reset(raw_token, new_password):
    """يضبط كلمة المرور — والرمز يُستهلك فلا يُستعمل مرّتين."""
    if len(new_password or "") < 8:
        raise SignupError("كلمة المرور ثماني خانات فأكثر")

    pr = PasswordReset.objects.filter(token_hash=_hash(raw_token)).first()
    if pr is None:
        raise SignupError("رابط غير صالح")
    if pr.is_used:
        raise SignupError("استُعمل هذا الرابط — اطلب رابطًا جديدًا")
    if pr.expires_at <= timezone.now():
        raise SignupError("انتهت صلاحية الرابط — اطلب رابطًا جديدًا")

    user = User.objects.filter(id=pr.user_id).first()
    if user is None:
        raise SignupError("المستخدم غير موجود")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    pr.used_at = timezone.now()
    pr.save(update_fields=["used_at"])

    logger.info("أُعيد ضبط كلمة مرور %s", user.id)
    return user
