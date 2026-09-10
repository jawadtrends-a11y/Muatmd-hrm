"""
باني التقارير المخصّصة (ق-126).

**العميل يختار حقوله ويبني تقريره** — لا ينتظر منّا تقريرًا جديدًا
لكل حاجة.

⚠️ **والحقول معلَنة لا حرّة**: أعمدة القاعدة فيها ما لا يخصّه
(مفاتيح داخلية، حقول محذوفة، بيانات غيره)، واختيارها حرًّا يكشف
ما لا يُكشف. فكل حقلٍ يُعلَن بمصدره ونوعه وصلاحيته.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ReportSource(models.TextChoices):
    EMPLOYEES = "employees", _("الموظفون")
    ATTENDANCE = "attendance", _("الحضور")
    REQUESTS = "requests", _("الطلبات")
    PAYROLL = "payroll", _("الرواتب")


class CustomReport(CompanyScopedModel):
    """
    تقريرٌ بناه العميل — حقولُه وتصفيتُه محفوظة.

    ويُشغَّل كأي تقرير: يمرّ بالبوابة والعزل، ويُصدَّر إكسل أو PDF.
    """
    name_ar = models.CharField(_("اسم التقرير"), max_length=150)
    description = models.CharField(_("الوصف"), max_length=255, blank=True)
    source = models.CharField(_("المصدر"), max_length=20,
                              choices=ReportSource.choices)

    #: قائمة مفاتيح الحقول بترتيب عرضها
    fields = models.JSONField(_("الحقول"), default=list)
    #: {"branch_id": 3, "department_id": 7, ...}
    filters = models.JSONField(_("التصفية"), default=dict, blank=True)
    #: مفتاح الترتيب، وبادئة - للتنازلي
    sort_by = models.CharField(_("الترتيب"), max_length=60, blank=True)

    is_shared = models.BooleanField(
        _("مشترك"), default=False,
        help_text=_("مطفأ = يراه بانيه وحده"))
    created_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("تقرير مخصّص")
        verbose_name_plural = _("التقارير المخصّصة")
        ordering = ["name_ar"]
        indexes = [
            models.Index(fields=["company", "source"],
                         name="idx_custrep_company_src"),
        ]

    def __str__(self):
        return self.name_ar
