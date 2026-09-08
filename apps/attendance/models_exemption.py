"""
الإعفاء من الحضور والانصراف (ق-104).

سجلٌّ بمدّة لا حقلٌ في الموظف: المندوب يُعفى ستّة أشهر ثم يعود
يبصم، والحقل الواحد لا يحفظ متى بدأ ولا متى انتهى ولا من اعتمده.

والنهاية الفارغة تعني **غير محدّدة المدّة** — كالمدير العام.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class AttendanceExemption(CompanyScopedModel):
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="attendance_exemptions", verbose_name=_("الموظف"))

    start_date = models.DateField(_("من"), db_index=True)
    end_date = models.DateField(
        _("إلى"), null=True, blank=True,
        help_text=_("فارغ = غير محدّدة المدّة"))

    reason = models.CharField(_("السبب"), max_length=255, blank=True)

    # الطلب الذي أنشأه — للتتبّع: من طلب ومن اعتمد.
    request = models.ForeignKey(
        "leaves.Request", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="exemptions", verbose_name=_("الطلب"))
    granted_by_person_id = models.BigIntegerField(null=True, blank=True)

    # الإلغاء لا الحذف: من أُعفي ثم أُعيد للبصمة يبقى أثره.
    is_active = models.BooleanField(_("ساري"), default=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("إعفاء من البصمة")
        verbose_name_plural = _("الإعفاءات من البصمة")
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["employment", "is_active"],
                         name="idx_exempt_emp_active"),
        ]

    def __str__(self):
        return f"إعفاء {self.employment_id} من {self.start_date}"

    def covers(self, day):
        if not self.is_active or day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date
