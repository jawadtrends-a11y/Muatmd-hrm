"""
النماذج الأساسية — الأساس الذي يرث منه كل نموذج في النظام.

قاعدة حاكمة: كل جدول عمل يحمل account_id، وتفرضه قاعدة البيانات
عبر RLS لا كود التطبيق. راجع الوثيقة المعمارية (2) القسم 2.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """طوابع زمنية لكل سجل — أساس التدقيق."""

    created_at = models.DateTimeField(_("تاريخ الإنشاء"), auto_now_add=True)
    updated_at = models.DateTimeField(_("تاريخ التحديث"), auto_now=True)

    class Meta:
        abstract = True


class AccountScopedModel(TimeStampedModel):
    """
    كل نموذج يخص حسابًا يرث من هذا.

    الحقل account مطلوب دائمًا — لا استثناء. غيابه يعني صفًا
    خارج نطاق العزل، وهو تسريب محتمل.
    """

    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        verbose_name=_("الحساب"),
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    class Meta:
        abstract = True


class CompanyScopedModel(AccountScopedModel):
    """
    نموذج يخص شركة بعينها داخل الحساب.

    العزل على مستويين: الحساب (مطلق) والشركة (ضمن المصرّح به).
    """

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.PROTECT,
        verbose_name=_("الشركة"),
        related_name="%(app_label)s_%(class)s_set",
        db_index=True,
    )

    class Meta:
        abstract = True


# سجل عمليات المنشأة (ق-44)
from apps.core.models_audit import AuditAction, AuditEntry  # noqa: E402,F401


# التخزين الموحّد للملفات (ق-61)
from apps.core.models_files import (  # noqa: E402,F401
    BLOCKED_EXTENSIONS, KIND_RULES, FileKind, StoredFile,
)
