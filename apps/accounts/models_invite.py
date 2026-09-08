"""
دعوة الانضمام — بقيّة ق-94.

حسابات الموظفين لا تُنشأ تلقائيًّا مع الموظف: تُنشأ بزرّ «دعوة
للانضمام»، فالشركة تقرّر من تريده في النظام، والموظف يضبط سرّه
بنفسه فلا يعرفه أحد سواه.

والرمز يُخزَّن مجزّأً (SHA-256) لا خامًا: من قرأ القاعدة لا يستطيع
انتحال دعوة — كما تفعل جانغو بكلمات المرور.
"""
import hashlib
import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel

VALID_DAYS = 7


def make_token() -> str:
    """رمز خام يظهر مرّة واحدة في الرابط — ولا يُخزَّن."""
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class InviteStatus(models.TextChoices):
    PENDING  = "pending",  _("بانتظار القبول")
    ACCEPTED = "accepted", _("قُبلت")
    REVOKED  = "revoked",  _("أُلغيت")


class JoinInvite(AccountScopedModel):
    """دعوة انضمام لشخص واحد."""

    company_id = models.BigIntegerField(_("الشركة"), db_index=True)
    person_id  = models.BigIntegerField(_("الشخص"), db_index=True)

    token_hash = models.CharField(_("بصمة الرمز"), max_length=64,
                                  unique=True, db_index=True)
    status = models.CharField(_("الحالة"), max_length=20,
                              choices=InviteStatus.choices,
                              default=InviteStatus.PENDING, db_index=True)
    expires_at = models.DateTimeField(_("تنتهي في"), db_index=True)

    # إلى أين أُرسلت — فارغ يعني أنها نُسخت يدويًّا ولم تُرسل.
    sent_to_email = models.EmailField(_("أُرسلت إلى"), blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    invited_by_person_id = models.BigIntegerField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    # الحساب المُنشأ عند القبول — للتتبّع لا للدخول.
    created_user_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("دعوة انضمام")
        verbose_name_plural = _("دعوات الانضمام")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["person_id", "status"],
                         name="idx_invite_person_status"),
        ]

    def __str__(self):
        return f"دعوة {self.person_id} ({self.status})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_usable(self):
        return self.status == InviteStatus.PENDING and not self.is_expired

    @classmethod
    def new_expiry(cls):
        return timezone.now() + timedelta(days=VALID_DAYS)
