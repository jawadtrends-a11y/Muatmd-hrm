"""
رموز مصادقة العملاء (ق-53).

رمز واحد يخدم الويب والجوال — فلا ازدواج حين يُبنى التطبيق
الأصلي. منفصل تمامًا عن جلسات لوحة المنصة (ق-51).
"""
import hashlib
import secrets

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class DeviceKind(models.TextChoices):
    WEB = "web", _("متصفح")
    IOS = "ios", _("آيفون")
    ANDROID = "android", _("أندرويد")


class AuthToken(TimeStampedModel):
    """
    رمز دخول لمستخدم عميل.

    يُحفظ مجزّأً لا نصًّا — تسريب قاعدة البيانات لا يعطي
    رموزًا صالحة.
    """

    WEB_DAYS = 1
    MOBILE_DAYS = 30

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="auth_tokens")
    token_hash = models.CharField(_("بصمة الرمز"), max_length=64,
                                  unique=True, db_index=True)
    prefix = models.CharField(
        _("البادئة"), max_length=12,
        help_text=_("أول ثمانية أحرف — للعرض والتمييز فقط"))

    device_kind = models.CharField(_("الجهاز"), max_length=12,
                                   choices=DeviceKind.choices,
                                   default=DeviceKind.WEB)
    device_name = models.CharField(_("اسم الجهاز"), max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(_("العنوان"), null=True,
                                              blank=True)

    expires_at = models.DateTimeField(_("ينتهي في"), db_index=True)
    last_used_at = models.DateTimeField(_("آخر استخدام"), null=True,
                                        blank=True)
    revoked_at = models.DateTimeField(_("أُبطل في"), null=True, blank=True)

    class Meta:
        verbose_name = _("رمز دخول")
        verbose_name_plural = _("رموز الدخول")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user_id} — {self.prefix}"

    @property
    def is_valid(self):
        return (self.revoked_at is None
                and self.expires_at > timezone.now()
                and self.user.is_active)


def generate_token():
    """يرجع (الخام، البصمة، البادئة). الخام يُعرض مرة واحدة."""
    raw = secrets.token_urlsafe(36)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), raw[:8]


def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()
