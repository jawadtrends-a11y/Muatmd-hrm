"""
مكوّنات الأجر والإعدادات المالية — أساس كل حسابات الرواتب.

قرارات المالك (السبرنت 6):
  • الأجر الخاضع للتأمينات: الأساسي + بدل السكن فقط (افتراض)
  • أجر نهاية الخدمة: حسب العقد — الشركة تحدد بلا افتراض مفروض
  • العمل الإضافي: أجر ساعة الأجر الكامل + 50% من ساعة الأساسي

المبدأ الحاكم (ق-19/1): لا رقم تشريعي داخل الكود. كل نسبة وحد في
جدول بتاريخ سريان، ويُقرأ بتاريخ الاستحقاق لا تاريخ اليوم.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ComponentType(models.TextChoices):
    EARNING   = "earning",   _("استحقاق")
    DEDUCTION = "deduction", _("استقطاع")


class CalculationType(models.TextChoices):
    FIXED      = "fixed",      _("مبلغ ثابت")
    PERCENT_OF = "percent_of", _("نسبة من مكوّن آخر")
    FORMULA    = "formula",    _("معادلة")


class PayComponent(CompanyScopedModel):
    """
    مكوّن أجر — بدل أو استقطاع.

    الأعلام الأربعة هي جوهر النظام: كل خلاف عمّالي في السعودية
    تقريبًا ينشأ من سؤال «هل هذا البدل يدخل في نهاية الخدمة؟».
    نجعلها إعدادًا صريحًا يراه العميل ويوقّع عليه، لا افتراضًا مخفيًا.
    """

    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("الاسم"), max_length=150)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=150, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=150, blank=True)

    component_type = models.CharField(
        _("النوع"), max_length=20, choices=ComponentType.choices)
    calculation_type = models.CharField(
        _("طريقة الاحتساب"), max_length=20,
        choices=CalculationType.choices, default=CalculationType.FIXED)
    percent_of_code = models.CharField(
        _("نسبة من"), max_length=40, blank=True,
        help_text=_("رمز المكوّن الأساس عند النسبة — غالبًا BASIC"))
    percent_value = models.DecimalField(
        _("النسبة"), max_digits=7, decimal_places=4, null=True, blank=True)

    # ══ الأعلام النظامية الأربعة ══
    is_gosi_subject = models.BooleanField(
        _("خاضع للتأمينات"), default=False,
        help_text=_("يدخل في الأجر الخاضع لاشتراك التأمينات"))
    is_eosb_subject = models.BooleanField(
        _("يدخل في نهاية الخدمة"), default=False,
        help_text=_("حسب العقد — الشركة تحدد ما يدخل"))
    is_overtime_base = models.BooleanField(
        _("يدخل أساس الإضافي"), default=False)
    is_wps_subject = models.BooleanField(
        _("يظهر في حماية الأجور"), default=True)

    is_taxable = models.BooleanField(_("خاضع للضريبة"), default=False)
    display_order = models.IntegerField(_("الترتيب"), default=0)
    is_active = models.BooleanField(_("نشط"), default=True, db_index=True)
    is_system = models.BooleanField(
        _("مكوّن نظامي"), default=False,
        help_text=_("لا يُحذف — مثل الراتب الأساسي"))

    class Meta:
        verbose_name = _("مكوّن أجر")
        verbose_name_plural = _("مكوّنات الأجر")
        ordering = ["display_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_paycomponent_code_per_company"),
        ]

    def __str__(self):
        return self.name_ar


class OvertimeBasis(models.TextChoices):
    """
    المادة 107 تحتمل قراءتين والسوق منقسم. الافتراض قرار المالك:
    أجر ساعة الأجر الكامل + 50% من ساعة الأساسي.
    """
    FULL_PLUS_HALF_BASIC = "full_plus_half_basic", _(
        "أجر ساعة الأجر الكامل + 50% من ساعة الأساسي")
    BASIC_TIMES_1_5 = "basic_x1_5", _("أجر ساعة الأساسي × 1.5")
    FULL_TIMES_1_5 = "full_x1_5", _("أجر ساعة الأجر الكامل × 1.5")


class PayrollSettings(CompanyScopedModel):
    """إعدادات الرواتب لكل شركة — تُقرأ منها كل الحسابات."""

    payroll_days_per_month = models.PositiveSmallIntegerField(
        _("أيام الشهر للاحتساب"), default=30,
        validators=[MinValueValidator(28), MaxValueValidator(31)],
        help_text=_("القاعدة المعتمدة في السوق السعودي: 30 يومًا"))
    working_hours_per_day = models.DecimalField(
        _("ساعات العمل اليومية"), max_digits=4, decimal_places=2, default=8)
    ramadan_hours_per_day = models.DecimalField(
        _("ساعات رمضان للمسلمين"), max_digits=4, decimal_places=2, default=6)

    overtime_basis = models.CharField(
        _("أساس العمل الإضافي"), max_length=30,
        choices=OvertimeBasis.choices,
        default=OvertimeBasis.FULL_PLUS_HALF_BASIC)

    # نهاية الخدمة: الشركة تحدد ما يدخل عبر أعلام المكوّنات
    eosb_note = models.TextField(
        _("ملاحظة نهاية الخدمة"), blank=True,
        help_text=_("ما يدخل في أجر المكافأة يحدده علم is_eosb_subject "
                    "على كل مكوّن، حسب العقد"))

    negative_net_policy = models.CharField(
        _("سياسة الصافي السالب"), max_length=20,
        choices=[("block", _("رفض المسير")),
                 ("carry", _("ترحيل الفرق للشهر التالي"))],
        default="block")
    variance_threshold_percent = models.DecimalField(
        _("عتبة الفروقات %"), max_digits=5, decimal_places=2, default=10,
        help_text=_("تغيّر الصافي بأكثر من هذه النسبة يظهر في شاشة المراجعة"))

    class Meta:
        verbose_name = _("إعدادات رواتب")
        verbose_name_plural = _("إعدادات الرواتب")
        constraints = [
            models.UniqueConstraint(fields=["company"],
                                    name="uq_payroll_settings_per_company"),
        ]

    def __str__(self):
        return f"إعدادات رواتب — {self.company.legal_name_ar}"


# ══════════ جداول التأمينات: بيانات منصة بتواريخ سريان ══════════

class GosiScheme(models.Model):
    """
    النظام التأميني. بعد إصلاح يوليو 2024 صار نظامان يعملان بالتوازي:
    القدامى على النسب التقليدية، والمنضمّون الجدد على تدرّج تصاعدي.
    """

    code = models.CharField(max_length=30, unique=True)
    name_ar = models.CharField(max_length=150)
    description_ar = models.TextField(blank=True)

    class Meta:
        verbose_name = _("نظام تأميني")
        verbose_name_plural = _("الأنظمة التأمينية")

    def __str__(self):
        return self.name_ar


class GosiRate(models.Model):
    """
    نسب الاشتراك بتاريخ سريان.

    تُقرأ بتاريخ استحقاق المسير لا تاريخ اليوم — فإعادة احتساب مسير
    قديم تعطي نفس الأرقام دائمًا. شرط للتدقيق لا تفاوض عليه.
    """

    scheme = models.ForeignKey(GosiScheme, on_delete=models.PROTECT,
                               related_name="rates")
    effective_from = models.DateField(_("سريان من"), db_index=True)
    effective_to = models.DateField(_("سريان إلى"), null=True, blank=True)

    employee_pension_rate = models.DecimalField(
        _("معاشات — الموظف"), max_digits=6, decimal_places=4, default=0)
    employer_pension_rate = models.DecimalField(
        _("معاشات — صاحب العمل"), max_digits=6, decimal_places=4, default=0)
    employee_saned_rate = models.DecimalField(
        _("ساند — الموظف"), max_digits=6, decimal_places=4, default=0)
    employer_saned_rate = models.DecimalField(
        _("ساند — صاحب العمل"), max_digits=6, decimal_places=4, default=0)
    employer_hazards_rate = models.DecimalField(
        _("الأخطار المهنية — صاحب العمل"),
        max_digits=6, decimal_places=4, default=0)

    min_subject_wage = models.DecimalField(
        _("الحد الأدنى للأجر الخاضع"), max_digits=12, decimal_places=2)
    max_subject_wage = models.DecimalField(
        _("الحد الأعلى للأجر الخاضع"), max_digits=12, decimal_places=2)

    source_note = models.CharField(
        _("مرجع"), max_length=255, blank=True,
        help_text=_("مصدر النسبة — للتدقيق"))

    class Meta:
        verbose_name = _("نسبة تأمينات")
        verbose_name_plural = _("نسب التأمينات")
        ordering = ["scheme", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "effective_from"],
                                    name="uq_gosi_rate_per_date"),
        ]

    def __str__(self):
        return f"{self.scheme.code} من {self.effective_from}"

    @property
    def employee_total_rate(self):
        return self.employee_pension_rate + self.employee_saned_rate

    @property
    def employer_total_rate(self):
        return (self.employer_pension_rate + self.employer_saned_rate
                + self.employer_hazards_rate)
