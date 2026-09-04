"""
التغيير الوظيفي (ق-82).

مسار واحد لأربع حالات: الترقية والتنزيل والنقل والفصل. موظف
الموارد يسجّله، ومدير الموارد يعتمده، ثم يسري.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ChangeType(models.TextChoices):
    PROMOTION = "promotion", _("ترقية")
    DEMOTION = "demotion", _("تنزيل")
    TRANSFER = "transfer", _("نقل وظيفي")
    DISMISSAL = "dismissal", _("فصل")


class ChangeStatus(models.TextChoices):
    PENDING = "pending", _("بانتظار الاعتماد")
    APPROVED = "approved", _("معتمد")
    REJECTED = "rejected", _("مرفوض")
    CANCELLED = "cancelled", _("ملغى")


class JobChange(CompanyScopedModel):
    """
    تغيير وظيفي مسجَّل بانتظار الاعتماد.

    والقيم القديمة تُحفظ لا لتُقرأ فقط: من يراجع بعد سنة يحتاج
    معرفة ما كان قبل ما صار (ق-80).
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="job_changes", verbose_name=_("الموظف"))
    change_type = models.CharField(
        _("نوع التغيير"), max_length=20, choices=ChangeType.choices)

    effective_from = models.DateField(_("يسري من"))

    # ── ما يتغيّر (كل حقل بحسب النوع) ──
    new_job_title = models.ForeignKey(
        "organization.JobTitle", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
        verbose_name=_("المسمّى الجديد"))
    new_department = models.ForeignKey(
        "organization.Department", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
        verbose_name=_("الإدارة الجديدة"))
    new_direct_manager = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
        verbose_name=_("المدير المباشر الجديد"))
    new_role_code = models.CharField(
        _("الدور الجديد"), max_length=30, blank=True)
    dismissal_reason = models.CharField(
        _("سبب الفصل"), max_length=60, blank=True)

    # ── ما كان قبل (ق-80: المراجعة تحتاج القديم والجديد) ──
    old_job_title_id = models.BigIntegerField(null=True, blank=True)
    old_department_id = models.BigIntegerField(null=True, blank=True)
    old_direct_manager_id = models.BigIntegerField(null=True, blank=True)
    old_role_code = models.CharField(max_length=30, blank=True)

    # ── البديل (ق-79) ──
    successor = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        null=True, blank=True, related_name="+",
        verbose_name=_("من يخلفه في موقعه"))

    status = models.CharField(
        _("الحالة"), max_length=20, choices=ChangeStatus.choices,
        default=ChangeStatus.PENDING, db_index=True)
    note = models.CharField(_("ملاحظة"), max_length=300, blank=True)

    created_by_person_id = models.BigIntegerField(null=True, blank=True)
    decided_by_person_id = models.BigIntegerField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = _("تغيير وظيفي")
        verbose_name_plural = _("التغييرات الوظيفية")
        ordering = ["-effective_from", "-id"]
        indexes = [
            models.Index(fields=["employment", "-effective_from"]),
            models.Index(fields=["status", "company"]),
        ]

    def __str__(self):
        return (f"{self.employment.employee_no} — "
                f"{self.get_change_type_display()}")
