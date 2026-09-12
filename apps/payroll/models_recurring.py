"""
الإضافات والحسومات المكرّرة (ق-135).

**بندٌ يتكرّر شهريًّا بلا إدخال** — بدل سكنٍ إضافيّ، حسم قرضٍ
شخصيّ، اشتراك نادٍ. فالموارد تُدخله مرّةً ويتكرّر في كل مسير.

⚠️ **وله نهايةٌ دائمًا**: بتاريخٍ أو بعدد مرّات. فبندٌ بلا نهاية
يُحسم من الموظف سنين — ومن أدخله نسيه.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class RecurringKind(models.TextChoices):
    EARNING = "earning", _("إضافة")
    DEDUCTION = "deduction", _("حسم")


class RecurringAdjustment(CompanyScopedModel):
    """
    بندٌ يتكرّر في كل مسير ضمن مداه.

    ⚠️ **والمبلغ يُجمَّد عند الإنشاء**: تعديله لاحقًا لا يغيّر
    قسائم صدرت — فمن راجع بعد سنة يرى ما صُرف فعلًا.
    """
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="recurring_adjustments", verbose_name=_("الموظف"))
    component = models.ForeignKey(
        "payroll.PayComponent", on_delete=models.PROTECT,
        related_name="recurring_adjustments", verbose_name=_("البند"))

    kind = models.CharField(_("النوع"), max_length=12,
                            choices=RecurringKind.choices)
    amount = models.DecimalField(
        _("المبلغ الشهري"), max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)])

    start_year = models.PositiveSmallIntegerField(_("من سنة"))
    start_month = models.PositiveSmallIntegerField(_("من شهر"))

    #: ⚠️ نهايةٌ بأحدهما: تاريخ أو عدد مرّات — ولا بدّ من واحدة
    end_year = models.PositiveSmallIntegerField(null=True, blank=True)
    end_month = models.PositiveSmallIntegerField(null=True, blank=True)
    max_occurrences = models.PositiveSmallIntegerField(
        _("عدد المرّات"), null=True, blank=True,
        help_text=_("كقسطٍ ينتهي — فارغ إن كانت النهاية بتاريخ"))

    applied_count = models.PositiveSmallIntegerField(
        _("طُبّق مرّات"), default=0)

    reason = models.CharField(_("السبب"), max_length=255, blank=True)
    is_active = models.BooleanField(_("سارٍ"), default=True, db_index=True)
    created_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("بند مكرّر")
        verbose_name_plural = _("البنود المكرّرة")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["company", "is_active"],
                         name="idx_recur_company_active"),
            models.Index(fields=["employment", "is_active"],
                         name="idx_recur_emp_active"),
        ]

    def __str__(self):
        return f"{self.component_id} — {self.amount}"

    def applies_to(self, year, month):
        """أيسري هذا البند في مسير هذا الشهر؟"""
        if not self.is_active:
            return False

        period = year * 12 + month
        if period < self.start_year * 12 + self.start_month:
            return False
        if self.end_year and period > self.end_year * 12 + self.end_month:
            return False
        if (self.max_occurrences
                and self.applied_count >= self.max_occurrences):
            return False
        return True

    @property
    def remaining(self):
        """كم بقي — أو None إن كانت النهاية بتاريخ."""
        if self.max_occurrences is None:
            return None
        return max(0, self.max_occurrences - self.applied_count)
