"""
الحسابات والشركات — حدّ العزل في النظام.

الحساب = مالك قد يملك أكثر من شركة. هو حدّ العزل المطلق ووحدة
الفوترة. الشركة تحته، ولكل شركة اشتراكها وباقتها.
راجع الوثيقتين المعماريتين (2) و(3).
"""
import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class AccountStatus(models.TextChoices):
    TRIAL     = "trial",     _("تجريبي")
    ACTIVE    = "active",    _("نشط")
    PAST_DUE  = "past_due",  _("متأخر السداد")
    GRACE     = "grace",     _("فترة سماح")
    SUSPENDED = "suspended", _("موقوف")
    ARCHIVED  = "archived",  _("مؤرشف")


class IsolationMode(models.TextChoices):
    SHARED   = "shared",   _("مشترك (RLS)")
    SCHEMA   = "schema",   _("سكيما مستقلة")
    DATABASE = "database", _("قاعدة بيانات مستقلة")


class UniquenessScope(models.TextChoices):
    COMPANY = "company", _("على مستوى الشركة")
    ACCOUNT = "account", _("على مستوى المجموعة")


slug_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$",
    _("المعرّف يقبل حروفًا إنجليزية صغيرة وأرقامًا وشرطات فقط"),
)


class Account(TimeStampedModel):
    """مالك الحساب — قد يملك شركة واحدة أو عدة شركات."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    slug = models.SlugField(
        _("المعرّف"), max_length=63, unique=True,
        validators=[slug_validator],
        help_text=_("يُستخدم في النطاق الفرعي، مثال: alfahd"),
    )
    display_name_ar = models.CharField(_("اسم المجموعة"), max_length=200)
    display_name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=200, blank=True)

    isolation_mode = models.CharField(
        _("نمط العزل"), max_length=20,
        choices=IsolationMode.choices, default=IsolationMode.SHARED,
    )
    status = models.CharField(
        _("الحالة"), max_length=20,
        choices=AccountStatus.choices, default=AccountStatus.TRIAL, db_index=True,
    )

    default_locale = models.CharField(
        _("اللغة الافتراضية"), max_length=5,
        choices=[("ar", "العربية"), ("en", "English"), ("ur", "اردو")], default="ar",
    )
    timezone = models.CharField(_("المنطقة الزمنية"), max_length=50, default="Asia/Riyadh")

    employee_no_scope = models.CharField(
        _("نطاق تفرد الرقم الوظيفي"), max_length=20,
        choices=UniquenessScope.choices, default=UniquenessScope.COMPANY,
    )
    allow_cross_company_employment = models.BooleanField(
        _("السماح بالعمل في أكثر من شركة"), default=True,
    )

    is_sandbox = models.BooleanField(
        _("حساب تجريبي"), default=False,
        help_text=_("الحسابات التجريبية وحدها قابلة للتصفير"),
    )
    suspended_at = models.DateTimeField(_("تاريخ الإيقاف"), null=True, blank=True)
    suspension_reason = models.TextField(_("سبب الإيقاف"), blank=True)

    class Meta:
        verbose_name = _("حساب")
        verbose_name_plural = _("الحسابات")
        ordering = ["display_name_ar"]

    def __str__(self):
        return self.display_name_ar

    @property
    def is_operational(self):
        """هل يُسمح بالكتابة؟ الإيقاف يمنع الكتابة لا القراءة والتصدير."""
        return self.status in {
            AccountStatus.TRIAL, AccountStatus.ACTIVE,
            AccountStatus.PAST_DUE, AccountStatus.GRACE,
        }


class Company(TimeStampedModel):
    """شركة داخل الحساب — لها سجلها التجاري واشتراكها وباقتها."""

    account = models.ForeignKey(
        Account, on_delete=models.CASCADE,
        verbose_name=_("الحساب"), related_name="companies",
    )
    code = models.CharField(_("الرمز"), max_length=30)
    legal_name_ar = models.CharField(_("الاسم النظامي"), max_length=255)
    legal_name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=255, blank=True)

    cr_number = models.CharField(_("السجل التجاري"), max_length=20, blank=True)
    cr_expiry_date = models.DateField(_("انتهاء السجل"), null=True, blank=True)
    unified_national_number = models.CharField(_("الرقم الموحّد"), max_length=20, blank=True)
    vat_number = models.CharField(_("الرقم الضريبي"), max_length=15, blank=True)

    gosi_establishment_no = models.CharField(_("رقم منشأة التأمينات"), max_length=20, blank=True)
    mol_establishment_no = models.CharField(_("رقم منشأة قوى"), max_length=20, blank=True)
    activity_code = models.CharField(_("رمز النشاط"), max_length=20, blank=True)
    entity_size = models.CharField(_("حجم المنشأة"), max_length=20, blank=True)

    fiscal_year_start_month = models.PositiveSmallIntegerField(
        _("بداية السنة المالية"), default=1,
    )
    is_active = models.BooleanField(_("نشطة"), default=True, db_index=True)

    class Meta:
        verbose_name = _("شركة")
        verbose_name_plural = _("الشركات")
        ordering = ["legal_name_ar"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "code"], name="uq_company_code_per_account",
            ),
        ]

    def __str__(self):
        return self.legal_name_ar
