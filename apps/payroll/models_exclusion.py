"""
استبعاد موظفٍ من المسير يدويًّا (ق-228).

**بلاغ جواد**: لا طريق لاستبعاد موظفٍ من المسير — والتبويب يعرض
من أخرجه المحرّك آليًّا فقط.

**وقرار جواد: نطاقان**
- **هذا المسير فقط** — يعود تلقائيًّا في الشهر التالي
- **حتى يُعاد يدويًّا** — يبقى خارج المسيرات حتى يُعيده مدير

⚠️⚠️ **والسبب إلزاميّ والفاعل يُنسب**: فالاستبعاد قرارٌ ماليّ —
موظفٌ لا يصله راتبه. **والإعادة لا تحذف** بل تُسجَّل بفاعلها
وتاريخها (ق-44): فمن سأل «لماذا لم أُصرف في مارس؟» يجد الجواب.

⚠️ **وقبل الاعتماد فقط**: المسير المعتمد سجلٌّ ماليّ نهائيّ.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ExclusionScope(models.TextChoices):
    RUN = "run", _("هذا المسير فقط")
    UNTIL_REVOKED = "until_revoked", _("حتى يُعاد يدويًّا")


class PayrollExclusion(CompanyScopedModel):
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="payroll_exclusions", verbose_name=_("الموظف"))
    scope = models.CharField(_("النطاق"), max_length=20,
                             choices=ExclusionScope.choices)
    # ⚠️ للنطاق الأول وحده — ولا يُحذف بحذف المسير
    run = models.ForeignKey(
        "payroll.PayrollRun", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="exclusions",
        verbose_name=_("المسير"))
    reason = models.CharField(_("السبب"), max_length=255)
    excluded_by_person_id = models.BigIntegerField(null=True, blank=True)

    revoked_at = models.DateTimeField(_("أُعيد في"), null=True, blank=True)
    revoked_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("استبعاد من المسير")
        verbose_name_plural = _("الاستبعادات من المسير")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["company", "scope", "revoked_at"],
                         name="idx_excl_company_scope"),
            models.Index(fields=["run", "revoked_at"],
                         name="idx_excl_run"),
        ]

    def __str__(self):
        return f"{self.employment_id} — {self.get_scope_display()}"
