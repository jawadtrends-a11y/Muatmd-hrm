"""
تأجيل بنود القسيمة (ق-136).

**قرار جواد:** الراتب الشهريّ **لا يُؤجَّل أصلًا** — وتأجيله
مخالفةٌ نظامية. وإنما يُؤجَّل بندٌ منه: قسط سلفة لظرفٍ طارئ، أو
حسمٌ بقرار، أو إضافةٌ تنتظر مستندًا.

⚠️ **وقبل الاعتماد فقط**: المسير المعتمد سجلٌّ ماليّ نهائيّ
يُصرف عليه ويُرحَّل للمحاسبة — فلا يُمسّ.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class DeferralStatus(models.TextChoices):
    PENDING = "pending", _("مؤجَّل")
    APPLIED = "applied", _("طُبّق")
    CANCELLED = "cancelled", _("أُلغي")


class PayslipDeferral(CompanyScopedModel):
    """
    بندٌ أُجِّل من مسيرٍ إلى شهرٍ يُحدَّد.

    ⚠️ **ولا يُؤجَّل مرّتين بلا أثر**: كل تأجيل يُسجَّل، فمن راجع
    يرى لماذا تأخّر البند وإلى متى.
    """
    # ⚠️ **ولا يُحذف بحذف القسيمة**: إعادة احتساب المسير تبني
    # القسائم من جديد — وبـCASCADE يضيع التأجيل عند أول إعادة
    # حساب، فيعود البند كأن شيئًا لم يكن.
    payslip = models.ForeignKey(
        "payroll.Payslip", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="deferrals", verbose_name=_("القسيمة"))
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="deferrals")

    component_code = models.CharField(_("رمز البند"), max_length=40)
    name_ar = models.CharField(_("البيان"), max_length=150)
    line_type = models.CharField(_("نوع البند"), max_length=20)
    amount = models.DecimalField(
        _("المبلغ"), max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)])

    #: من أي شهرٍ أُجِّل
    from_year = models.PositiveSmallIntegerField()
    from_month = models.PositiveSmallIntegerField()
    #: وإلى أي شهر
    to_year = models.PositiveSmallIntegerField(_("إلى سنة"))
    to_month = models.PositiveSmallIntegerField(_("إلى شهر"))

    reason = models.CharField(_("السبب"), max_length=255)
    status = models.CharField(_("الحالة"), max_length=12,
                              choices=DeferralStatus.choices,
                              default=DeferralStatus.PENDING,
                              db_index=True)

    #: إن كان قسط سلفة — فجدولها يمتدّ شهرًا
    advance_id = models.BigIntegerField(null=True, blank=True)

    applied_run_id = models.BigIntegerField(null=True, blank=True)
    deferred_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("بند مؤجَّل")
        verbose_name_plural = _("البنود المؤجَّلة")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["company", "status"],
                         name="idx_defer_company_status"),
            models.Index(fields=["to_year", "to_month", "status"],
                         name="idx_defer_target"),
        ]

    def __str__(self):
        return f"{self.component_code} — {self.amount}"
