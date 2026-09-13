"""
مفاتيح API — إنشاءً ومصادقةً وحدًّا (ق-151).

⚠️ **والمفتاح يُعرض مرّةً ويُخزَّن مجزّأً**.
"""
import hashlib
import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

PREFIX_LEN = 8
#: ⚠️ **بادئةٌ تُميّز مفاتيحنا** في سجلّات العميل
KEY_PREFIX = "mua_"


class ApiKeyError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def _hash(raw):
    """
    ⚠️ **تجزئةٌ سريعة لا بطيئة**: فالمفتاح عشوائيٌّ طويل لا كلمة
    مرور — والبطء يُثقل كل نداء.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


@transaction.atomic
def create_key(*, company, name, scopes, rate_limit=1000,
               expires_on=None, by_person_id=None):
    """
    يُنشئ مفتاحًا — **ويعيد نصّه مرّةً واحدة**.

    ⚠️ **فلا سبيل لقراءته بعدها**: من فقده أنشأ غيره.
    """
    from apps.core.models import ApiKey, ApiScope

    if not (name or "").strip():
        raise ApiKeyError("اسم المفتاح مطلوب — لأيّ تكاملٍ هو")

    scopes = [s for s in (scopes or []) if s in ApiScope.values]
    if not scopes:
        raise ApiKeyError(
            "حدّد نطاقًا واحدًا على الأقلّ — فمفتاحٌ بلا نطاق لا يقرأ شيئًا")

    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey.objects.create(
        account_id=company.account_id, company=company,
        name=name.strip()[:120],
        prefix=raw[:PREFIX_LEN],
        key_hash=_hash(raw),
        scopes=scopes,
        rate_limit_per_hour=int(rate_limit or 1000),
        expires_on=expires_on,
        created_by_person_id=by_person_id)

    logger.info("أُنشئ مفتاح API %s للشركة %s", key.prefix,
                company.id)
    return key, raw


def authenticate(raw_key):
    """
    يتحقّق من المفتاح — **ويعيد المفتاح أو سبب الرفض**.

    ⚠️ **والبحث بالبادئة ثم المقارنة بالتجزئة**: فمسحُ الجدول كلّه
    لكل نداءٍ يُثقل الخادم.
    """
    from django.db import connection

    from apps.core.models import ApiKey

    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        return None, "مفتاح غير صالح"

    prefix = raw_key[:PREFIX_LEN]
    digest = _hash(raw_key)

    # ⚠️ **فوق العزل**: المفتاح يصل قبل معرفة حسابه — فلا سياق بعد.
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id FROM core_apikey WHERE prefix = %s "
            "AND key_hash = %s LIMIT 1", [prefix, digest])
        row = cur.fetchone()

    if row is None:
        return None, "مفتاح غير معروف"

    from apps.core.tenancy.context import account_scope

    with connection.cursor() as cur:
        cur.execute("SELECT account_id FROM core_apikey WHERE id = %s",
                    [row[0]])
        acc_id = cur.fetchone()[0]

    with account_scope(acc_id):
        key = ApiKey.objects.filter(id=row[0]).select_related(
            "company").first()
        if key is None:
            return None, "مفتاح غير معروف"
        if not key.is_usable:
            return None, ("المفتاح منتهٍ" if key.expires_on
                          else "المفتاح موقوف")
        return key, ""


def within_rate_limit(key):
    """
    ⚠️ **السقف بالساعة** — فمفتاحٌ بلا حدّ يُسقط الخادم.
    """
    from apps.core.models import ApiCallLog

    since = timezone.now() - timedelta(hours=1)
    used = ApiCallLog.objects.filter(api_key=key, at__gte=since).count()
    return used < key.rate_limit_per_hour, used


@transaction.atomic
def log_call(*, key, path, method, status_code, ip=""):
    """
    يسجّل النداء — ⚠️ **بلا جسم الطلب**.

    فبياناتُ الموظفين لا تُنسخ في سجلّ.
    """
    from apps.core.models import ApiCallLog

    ApiCallLog.objects.create(
        account_id=key.account_id, company_id=key.company_id,
        api_key=key, path=path[:200], method=method[:10],
        status_code=status_code, ip=(ip or "")[:45])

    key.last_used_at = timezone.now()
    key.last_used_ip = (ip or "")[:45]
    key.call_count = (key.call_count or 0) + 1
    key.save(update_fields=["last_used_at", "last_used_ip",
                            "call_count", "updated_at"])


@transaction.atomic
def revoke(*, key, reason=""):
    """
    يوقف مفتاحًا — **ولا يُحذف**.

    ⚠️ فسجلّ نداءاته حجّةٌ تبقى، وحذفُه يمحو أثر ما قرأ.
    """
    if key.revoked_at:
        raise ApiKeyError("موقوفٌ بالفعل")

    key.is_active = False
    key.revoked_at = timezone.now()
    key.revoked_reason = (reason or "")[:255]
    key.save(update_fields=["is_active", "revoked_at",
                            "revoked_reason", "updated_at"])
    return key


def purge_old_logs(days=90):
    """⚠️ وسجلّ النداءات يُقلَّم — فلا ينمو بلا حدّ."""
    from apps.core.models import ApiCallLog

    cutoff = timezone.now() - timedelta(days=days)
    n, _ = ApiCallLog.objects.filter(at__lt=cutoff).delete()
    return n
