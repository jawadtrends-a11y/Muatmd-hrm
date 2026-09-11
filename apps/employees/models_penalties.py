"""
الجزاءات التأديبية (ق-119).

**لائحةٌ تُبذر وتُعدَّل**: تُبذر بلائحة وزارة الموارد النموذجية،
وتعدّلها الشركة كما تعدّل أنواع الإجازات (ق-9) — فلكل منشأة
لائحتها المعتمدة.

⚠️ **والتدرّج لبّها**: المخالفة الأولى إنذار، والثانية خصم يوم،
والثالثة يومان… فالنظام يتتبّع التكرار **خلال مدّة محدّدة**
ويقترح الدرجة. والمخالفة التي مضى على سابقتها أكثر من المدّة
تُعامَل معاملة الأولى — كما تقضي المادة (٦٦) من نظام العمل.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class PenaltyKind(models.TextChoices):
    WARNING = "warning", _("إنذار كتابي")
    WAGE_DEDUCTION = "wage_deduction", _("خصم من الأجر")
    SUSPENSION = "suspension", _("إيقاف عن العمل بلا أجر")
    BONUS_DEPRIVATION = "bonus_deprivation", _("حرمان من علاوة")
    PROMOTION_DELAY = "promotion_delay", _("تأجيل ترقية")
    DISMISSAL = "dismissal", _("الفصل")


class ViolationCategory(models.TextChoices):
    ATTENDANCE = "attendance", _("مخالفات المواعيد")
    WORK_ORG = "work_org", _("مخالفات تنظيم العمل")
    CONDUCT = "conduct", _("مخالفات السلوك")
    SAFETY = "safety", _("مخالفات السلامة")
    OTHER = "other", _("أخرى")


class PolicyVersion(CompanyScopedModel):
    """
    نسخةٌ من لائحة الجزاءات بتاريخ سريانها (ق-130).

    ⚠️ **اللائحة تُنقَّح، والماضي لا يتبدّل**: من وُقّع عليه
    بتدرّجٍ ثم عُدّلت الدرجات يبدو كأنه وُقّع بالجديد — ولا سجلّ
    يقول ما كان ساريًا يوم وقعت المخالفة.

    فمخالفةُ يناير تُقاس بلائحة يناير، ومخالفةُ مارس بالمعدَّلة.
    **والجزاء يحفظ رقم نسخته** فيُراجَع بما كان — وهو ما يصمد
    أمام هيئة تسوية الخلافات العمّالية.
    """
    number = models.PositiveSmallIntegerField(_("رقم النسخة"))
    effective_from = models.DateField(_("سريان من"), db_index=True)
    note = models.CharField(_("سبب التنقيح"), max_length=255, blank=True)

    is_active = models.BooleanField(
        _("سارية"), default=True,
        help_text=_("مطفأ = نسخةٌ سابقة تُحفظ للماضي"))
    created_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("نسخة لائحة الجزاءات")
        verbose_name_plural = _("نسخ لائحة الجزاءات")
        ordering = ["-effective_from", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["company", "number"],
                                    name="uq_polver_company_number"),
        ]

    def __str__(self):
        return f"لائحة v{self.number} من {self.effective_from}"


class ViolationType(CompanyScopedModel):
    """
    بند في لائحة الجزاءات — المخالفة ودرجاتها.

    والدرجات في `PenaltyDegree`: لكل تكرار جزاؤه.
    """
    # ق-130: البند يتبع نسخةً — فالتنقيح ينسخ البنود ولا يدوسها
    policy_version = models.ForeignKey(
        PolicyVersion, on_delete=models.CASCADE, null=True, blank=True,
        related_name="violations", verbose_name=_("نسخة اللائحة"))

    code = models.CharField(_("الرمز"), max_length=30)
    name_ar = models.CharField(_("المخالفة"), max_length=255)
    name_en = models.CharField(_("بالإنجليزية"), max_length=255, blank=True)
    category = models.CharField(
        _("التصنيف"), max_length=20, choices=ViolationCategory.choices,
        default=ViolationCategory.OTHER)
    # ⚠️ المادة (٦٦): ما مضى على سابقته أكثر من المدّة يُعدّ أولى
    reset_days = models.PositiveSmallIntegerField(
        _("مدّة سقوط التكرار (يومًا)"), default=365,
        help_text=_("المادة (٧٣): سنة كاملة من تاريخ الارتكاب"))
    # ق-119: بندٌ يُوثَّق ولا يُخصم عليه مهما كانت درجته —
    # فبعض المخالفات يُكتفى فيها بالتنبيه والإنذار.
    financial_effect = models.BooleanField(
        _("له أثر ماليّ"), default=True,
        help_text=_("مطفأ = يُوثَّق الجزاء ولا يُخصم"))

    is_active = models.BooleanField(_("مفعّلة"), default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("بند لائحة الجزاءات")
        verbose_name_plural = _("لائحة الجزاءات")
        ordering = ["category", "sort_order", "id"]
        constraints = [
            # ق-130: الرمز يتكرّر عبر النسخ — والتفرّد داخل النسخة
            models.UniqueConstraint(
                fields=["company", "policy_version", "code"],
                name="uq_violation_version_code"),
        ]

    def __str__(self):
        return self.name_ar


class PenaltyDegree(models.Model):
    """
    درجة الجزاء عند تكرارٍ بعينه.

    فالتكرار الأول إنذار، والثاني خصم يوم… والقيمة بالأيام أو
    بالنسبة حسب نوع الجزاء.
    """
    violation = models.ForeignKey(
        ViolationType, on_delete=models.CASCADE, related_name="degrees",
        verbose_name=_("المخالفة"))
    occurrence = models.PositiveSmallIntegerField(
        _("التكرار"), help_text=_("1 = المرّة الأولى"))
    kind = models.CharField(_("الجزاء"), max_length=25,
                            choices=PenaltyKind.choices)
    # الخصم بالأيام: 0.5 = نصف يوم أجر
    days = models.DecimalField(_("الأيام"), max_digits=5, decimal_places=2,
                               default=0)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("درجة جزاء")
        verbose_name_plural = _("درجات الجزاءات")
        ordering = ["occurrence"]
        constraints = [
            models.UniqueConstraint(fields=["violation", "occurrence"],
                                    name="uq_degree_violation_occurrence"),
        ]

    def __str__(self):
        return f"{self.violation.code} #{self.occurrence}"


class PenaltyStatus(models.TextChoices):
    DRAFT = "draft", _("مسودة")
    ISSUED = "issued", _("موقَّع")
    OBJECTED = "objected", _("متظلَّم منه")
    CANCELLED = "cancelled", _("ملغى")


class Penalty(CompanyScopedModel):
    """
    جزاء موقَّع على موظف.

    ⚠️ **والخصم يدخل المسير** ببند خصم — فالجزاء الورقيّ بلا أثر
    ماليّ لا معنى له، وحسابه يدويًّا يخطئ.
    """
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="penalties", verbose_name=_("الموظف"))
    violation = models.ForeignKey(
        ViolationType, on_delete=models.PROTECT, related_name="penalties",
        verbose_name=_("المخالفة"))

    # ⚠️ ق-130: **رقم النسخة السارية يوم الواقعة** — فمراجعةُ
    # جزاءٍ بعد سنتين تُقاس بلائحته لا بما صارت عليه.
    policy_version_no = models.PositiveSmallIntegerField(
        _("نسخة اللائحة"), null=True, blank=True)

    occurred_on = models.DateField(_("تاريخ المخالفة"), db_index=True)
    occurrence = models.PositiveSmallIntegerField(
        _("التكرار"), default=1,
        help_text=_("يُحتسب تلقائيًّا من سوابقه خلال مدّة السقوط"))

    kind = models.CharField(_("الجزاء"), max_length=25,
                            choices=PenaltyKind.choices)
    days = models.DecimalField(_("الأيام"), max_digits=5, decimal_places=2,
                               default=0)
    amount = models.DecimalField(_("المبلغ المخصوم"), max_digits=12,
                                 decimal_places=2, default=0)

    description = models.TextField(_("وصف الواقعة"), blank=True)
    employee_statement = models.TextField(_("إفادة الموظف"), blank=True)

    status = models.CharField(_("الحالة"), max_length=20,
                              choices=PenaltyStatus.choices,
                              default=PenaltyStatus.DRAFT, db_index=True)
    issued_by_person_id = models.BigIntegerField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)

    # ق-119: الخصم **اختياريّ** — المخالفة قد تُوثَّق بلا خصم،
    # والمسؤول يقرّر عند التوقيع. والمطفأ لا يدخل المسير.
    apply_deduction = models.BooleanField(
        _("طُبّق الخصم"), default=True)

    # ق-119: والتكرار **قرار إداريّ** كذلك — قد يُوثَّق الجزاء ولا
    # يُرفع تكراره، فيبقى الموظف على درجته. فالتوثيق حفظُ واقعة،
    # والتصعيد قرارٌ يُتَّخذ.
    count_occurrence = models.BooleanField(
        _("يُحتسب في التكرار"), default=True)

    # الخصم في المسير — لا يُخصم مرّتين
    deducted_in_run_id = models.BigIntegerField(null=True, blank=True)
    cancelled_reason = models.CharField(_("سبب الإلغاء"), max_length=255,
                                        blank=True)

    class Meta:
        verbose_name = _("جزاء")
        verbose_name_plural = _("الجزاءات")
        ordering = ["-occurred_on", "-id"]
        indexes = [
            models.Index(fields=["employment", "status"],
                         name="idx_penalty_emp_status"),
            models.Index(fields=["company", "occurred_on"],
                         name="idx_penalty_company_date"),
        ]

    def __str__(self):
        return f"جزاء {self.employment_id} — {self.violation_id}"
