"""
التسويات الرجعية (ق-69).

طلب اعتُمد بعد إغلاق مسير شهره يترك فرقًا. والفرق يُحتسب بإعادة
حساب الشهر بالبيانات المصححة — لا بردّ الخصم كاملًا.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class RetroStatus(models.TextChoices):
    PENDING = "pending", _("بانتظار الإدراج")
    MERGED = "merged", _("مُدرجة في مسير")
    DEFERRED = "deferred", _("مؤجَّلة")
    CANCELLED = "cancelled", _("ملغاة")


class RetroSource(models.TextChoices):
    ATTENDANCE_FIX = "attendance_fix", _("تصحيح بصمة")
    LEAVE = "leave", _("إجازة بأثر رجعي")
    OVERTIME = "overtime", _("عمل إضافي متأخر")
    OTHER = "other", _("تعديل آخر")


class RetroAdjustment(CompanyScopedModel):
    """
    فرق مستحق عن شهر أُغلق مسيره.

    ويحمل القيمتين — قبل التصحيح وبعده — لا الفرق وحده: من يراجع
    بعد سنة يحتاج معرفة كيف حُسب (ق-80).
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="retro_adjustments", verbose_name=_("الموظف"))

    period_year = models.PositiveSmallIntegerField(_("سنة الاستحقاق"))
    period_month = models.PositiveSmallIntegerField(_("شهر الاستحقاق"))

    source = models.CharField(
        _("المصدر"), max_length=20, choices=RetroSource.choices)
    source_request = models.ForeignKey(
        "leaves.Request", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="retro_adjustments", verbose_name=_("الطلب"))

    amount_before = models.DecimalField(
        _("المحتسب سابقًا"), max_digits=12, decimal_places=2, default=0)
    amount_after = models.DecimalField(
        _("المحتسب بالبيانات المصححة"), max_digits=12,
        decimal_places=2, default=0)
    amount = models.DecimalField(
        _("الفرق"), max_digits=12, decimal_places=2, default=0,
        help_text=_("موجب: يُضاف للموظف · سالب: يُخصم منه"))

    reason_ar = models.CharField(_("البيان"), max_length=200, blank=True)

    status = models.CharField(
        _("الحالة"), max_length=20, choices=RetroStatus.choices,
        default=RetroStatus.PENDING, db_index=True)
    merged_run = models.ForeignKey(
        "payroll.PayrollRun", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="retro_adjustments",
        verbose_name=_("المسير المُدرجة فيه"))

    decided_by_person_id = models.BigIntegerField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(_("ملاحظة"), max_length=300, blank=True)

    class Meta:
        verbose_name = _("تسوية رجعية")
        verbose_name_plural = _("التسويات الرجعية")
        ordering = ["-period_year", "-period_month", "-id"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["employment", "period_year",
                                 "period_month"]),
        ]

    def __str__(self):
        return (f"{self.employment.employee_no} — "
                f"{self.period_year}/{self.period_month:02d}: {self.amount}")
