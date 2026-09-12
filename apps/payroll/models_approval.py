"""
سلسلة موافقات المسير (ق-140).

**المسير مالٌ يُصرف** — وشركاتٌ تشترط مرورَه بالمالية ثم المدير
العام. فبلا سلسلة يُعتمد بضغطةٍ واحدة.

⚠️ **وبلا سلسلة يُعتمد مباشرةً** كما هو اليوم — فلا نكسر من لا
يحتاجها.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class PayrollApprovalStep(CompanyScopedModel):
    """
    خطوةٌ في سلسلة اعتماد المسير.

    **بالدور لا بالشخص**: فمن غاب حلّ محلّه من يحمل دوره — ولو
    رُبطت بشخصٍ تعطّل المسير بإجازته.
    """
    step_order = models.PositiveSmallIntegerField(_("الترتيب"))
    role = models.ForeignKey(
        "accounts.Role", on_delete=models.PROTECT,
        related_name="payroll_steps", verbose_name=_("الدور المعتمِد"))
    title = models.CharField(_("مسمّى الخطوة"), max_length=120, blank=True)

    #: مهلة الخطوة — للتنبيه لا للتخطّي
    sla_hours = models.PositiveSmallIntegerField(
        _("مهلة الاعتماد (ساعة)"), null=True, blank=True)
    is_active = models.BooleanField(_("مفعّلة"), default=True)

    class Meta:
        verbose_name = _("خطوة اعتماد مسير")
        verbose_name_plural = _("خطوات اعتماد المسير")
        ordering = ["step_order"]
        constraints = [
            models.UniqueConstraint(fields=["company", "step_order"],
                                    name="uq_payrollstep_company_order"),
        ]

    def __str__(self):
        return f"{self.step_order}. {self.title or self.role_id}"


class PayrollApprovalDecision(models.TextChoices):
    PENDING = "pending", _("قيد الانتظار")
    APPROVED = "approved", _("معتمد")
    REJECTED = "rejected", _("مرفوض")


class PayrollApproval(CompanyScopedModel):
    """
    قرار خطوةٍ على مسيرٍ بعينه.

    ⚠️ **ولا يُحذف بإعادة الاحتساب**: سجلُّ من اعتمد ومتى حجّةٌ
    ماليّة — والرفض يُعيد المسير للتصحيح لا يمحو تاريخه.
    """
    run = models.ForeignKey(
        "payroll.PayrollRun", on_delete=models.CASCADE,
        related_name="approvals", verbose_name=_("المسير"))
    step_order = models.PositiveSmallIntegerField(_("الترتيب"))
    role = models.ForeignKey(
        "accounts.Role", on_delete=models.PROTECT,
        related_name="payroll_approvals")
    title = models.CharField(max_length=120, blank=True)

    decision = models.CharField(
        _("القرار"), max_length=12,
        choices=PayrollApprovalDecision.choices,
        default=PayrollApprovalDecision.PENDING, db_index=True)
    decided_by_person_id = models.BigIntegerField(null=True, blank=True)
    decided_by_name = models.CharField(max_length=150, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(_("السبب"), max_length=255, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("اعتماد مسير")
        verbose_name_plural = _("اعتمادات المسير")
        ordering = ["run", "step_order"]
        constraints = [
            models.UniqueConstraint(fields=["run", "step_order"],
                                    name="uq_payrollapproval_run_step"),
        ]

    def __str__(self):
        return f"{self.run_id} — {self.step_order}"
