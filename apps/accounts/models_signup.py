"""
التسجيل الذاتيّ واستعادة كلمة المرور (ق-113).

**خارج العزل**: الطلبان يقعان قبل وجود حساب أو خارج جلسته — فلا
`account_id` لهما، والحماية بالرمز المجزَّأ والمهلة القصيرة.

⚠️ **الرمز مجزَّأ لا مخزَّن**: من قرأ القاعدة لا يستطيع انتحال
أحد، كما في دعوة الانضمام (ق-101).
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class SignupStatus(models.TextChoices):
    PENDING = "pending", _("بانتظار تأكيد البريد")
    VERIFIED = "verified", _("مؤكَّد — أُنشئ الحساب")
    EXPIRED = "expired", _("منتهٍ")


class SignupRequest(TimeStampedModel):
    """
    طلب تسجيل شركة — لا يُنشأ الحساب إلا بعد تأكيد البريد.

    فالبريد غير المؤكَّد يملأ المنصّة بحسابات وهمية، ويحرم صاحبه
    من استعادة كلمة مروره حين ينساها.
    """
    company_name = models.CharField(_("اسم الشركة"), max_length=150)
    full_name = models.CharField(_("اسم المسؤول"), max_length=150)
    email = models.EmailField(_("البريد"), db_index=True)
    mobile = models.CharField(_("الجوال"), max_length=20, blank=True)
    password_hash = models.CharField(_("كلمة المرور"), max_length=256)

    token_hash = models.CharField(_("بصمة الرمز"), max_length=64,
                                  unique=True, db_index=True)
    status = models.CharField(_("الحالة"), max_length=20,
                              choices=SignupStatus.choices,
                              default=SignupStatus.PENDING, db_index=True)
    expires_at = models.DateTimeField(_("ينتهي في"), db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    created_account_id = models.BigIntegerField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = _("طلب تسجيل")
        verbose_name_plural = _("طلبات التسجيل")
        ordering = ["-created_at"]

    def __str__(self):
        return f"تسجيل {self.company_name}"


class PasswordReset(TimeStampedModel):
    """
    طلب استعادة كلمة مرور.

    ⚠️ **لا يُفشي وجود الحساب**: الردّ واحد سواء وُجد البريد أم لا
    — وإلا صار المسار أداةً لكشف من له حساب عندنا.
    """
    user_id = models.BigIntegerField(_("المستخدم"), db_index=True)
    token_hash = models.CharField(_("بصمة الرمز"), max_length=64,
                                  unique=True, db_index=True)
    expires_at = models.DateTimeField(_("ينتهي في"), db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = _("استعادة كلمة مرور")
        verbose_name_plural = _("طلبات الاستعادة")
        ordering = ["-created_at"]

    @property
    def is_used(self):
        return self.used_at is not None
