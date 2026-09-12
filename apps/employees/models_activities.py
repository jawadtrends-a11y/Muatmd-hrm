"""
أنشطة العمل اليومية (ق-143).

**المدير يُسند نشاطًا يوميًّا** — مهمّةً موصوفة أو عددًا مستهدَفًا:
«راجع ملفّات القسم» أو «٢٠ معاملة». **ويُسجَّل سلفًا لمدًى** —
شهرًا أو أكثر — فلا يُعاد إدخاله كل صباح.

⚠️ **وآخر اليوم يُقرّ الموظف**: أُنجز، أو أُنجز جزئيًّا، أو لم
يُنجَز — **ويُحدَّد ما أُنجز وما لم يُنجَز** لا سببٌ عامّ (قرار
جواد). فالمدير يعرف العائق لا الرقم وحده.

⚠️⚠️ **وله أثرٌ ماليّ اختياريّ**: مكافأةً أو حسمًا، بمبلغٍ للنشاط
أو لكل وحدة — **ولا يقع بإقرار الموظف وحده**، بل بمراجعةٍ يعتمدها
المدير.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ActivityStatus(models.TextChoices):
    PENDING = "pending", _("بانتظار الإقرار")
    DONE = "done", _("أُنجز")
    PARTIAL = "partial", _("أُنجز جزئيًّا")
    NOT_DONE = "not_done", _("لم يُنجَز")


class PayEffect(models.TextChoices):
    NONE = "none", _("بلا أثر ماليّ")
    BONUS = "bonus", _("مكافأة على التحقيق")
    DEDUCTION = "deduction", _("حسم على التقصير")
    BOTH = "both", _("مكافأةٌ وحسم")


class PayBasis(models.TextChoices):
    PER_ACTIVITY = "per_activity", _("مبلغ للنشاط كاملًا")
    PER_UNIT = "per_unit", _("مبلغ لكل وحدة")


class WorkActivity(CompanyScopedModel):
    """
    نشاطُ يومٍ مُسنَدٌ لموظف.

    ⚠️ **والهدف العدديّ اختياريّ**: فنشاطٌ كتابيّ لا يُقاس برقم،
    وإلزامُه يُفرغ الوصف من معناه.
    """
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="work_activities", verbose_name=_("الموظف"))

    work_date = models.DateField(_("اليوم"), db_index=True)
    title = models.CharField(_("النشاط"), max_length=200)
    description = models.TextField(_("التفاصيل"), blank=True)

    #: هدفٌ عدديّ — فارغ لنشاطٍ موصوف
    target_count = models.PositiveIntegerField(
        _("العدد المستهدَف"), null=True, blank=True)
    unit = models.CharField(_("الوحدة"), max_length=40, blank=True,
                            help_text=_("معاملة · تقرير · زيارة"))

    # ── الأثر الماليّ (اختياريّ) ──
    pay_effect = models.CharField(
        _("الأثر الماليّ"), max_length=12, choices=PayEffect.choices,
        default=PayEffect.NONE)
    pay_basis = models.CharField(
        _("أساس الاحتساب"), max_length=15, choices=PayBasis.choices,
        default=PayBasis.PER_ACTIVITY)
    bonus_amount = models.DecimalField(
        _("مبلغ المكافأة"), max_digits=10, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)])
    deduction_amount = models.DecimalField(
        _("مبلغ الحسم"), max_digits=10, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)])

    # ── الإقرار ──
    status = models.CharField(_("الحالة"), max_length=12,
                              choices=ActivityStatus.choices,
                              default=ActivityStatus.PENDING,
                              db_index=True)
    done_count = models.PositiveIntegerField(
        _("المنجَز"), null=True, blank=True)

    #: ⚠️ **ما أُنجز وما لم يُنجَز** — لا سببٌ عامّ
    done_note = models.TextField(_("ما أُنجز"), blank=True)
    pending_note = models.TextField(_("ما لم يُنجَز"), blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)

    # ── مراجعة المدير ──
    #
    # ⚠️ **فالأثر لا يقع بإقرار الموظف وحده**: مالٌ يُصرف أو
    # يُحسم بقول صاحبه — والمراجعة هي الضابط.
    is_reviewed = models.BooleanField(_("رُوجع"), default=False,
                                      db_index=True)
    reviewed_by_person_id = models.BigIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(_("ملاحظة المراجعة"), max_length=255,
                                   blank=True)
    #: المبلغ المعتمَد بعد المراجعة — موجبٌ مكافأةً وسالبٌ حسمًا
    settled_amount = models.DecimalField(
        _("المبلغ المعتمَد"), max_digits=10, decimal_places=2,
        null=True, blank=True)
    payroll_year = models.PositiveSmallIntegerField(null=True, blank=True)
    payroll_month = models.PositiveSmallIntegerField(null=True, blank=True)
    is_paid = models.BooleanField(_("دخل المسير"), default=False,
                                  db_index=True)

    assigned_by_employment_id = models.BigIntegerField(
        null=True, blank=True)
    #: ⚠️ مجموعة الإسناد الواحد — فمدًى يُنشأ معًا يُلغى معًا
    batch_key = models.CharField(max_length=40, blank=True, db_index=True)

    class Meta:
        verbose_name = _("نشاط عمل")
        verbose_name_plural = _("أنشطة العمل")
        ordering = ["-work_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "work_date", "title"],
                name="uq_activity_emp_date_title"),
        ]
        indexes = [
            models.Index(fields=["employment", "work_date"],
                         name="idx_activity_emp_date"),
            models.Index(fields=["company", "status"],
                         name="idx_activity_company_status"),
            models.Index(fields=["company", "is_reviewed", "is_paid"],
                         name="idx_activity_review_paid"),
        ]

    def __str__(self):
        return f"{self.work_date} — {self.title}"

    @property
    def is_measurable(self):
        return self.target_count is not None

    @property
    def achievement(self):
        """نسبة التحقيق — أو None لنشاطٍ موصوف."""
        if not self.is_measurable or not self.target_count:
            return None
        return round((self.done_count or 0) * 100 / self.target_count)
