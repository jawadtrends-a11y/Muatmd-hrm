"""
وسوم الموظفين والمهام (ق-131).

**الوسم تصنيفٌ حرّ** تكتبه الشركة — لا حقلٌ نضيفه لكل حاجة:
«سائق»، «مناوب ليليّ»، «يتقن الإنجليزية»، «مدرَّب على السلامة».
فتُرشَّح به القوائم وتُبنى عليه التقارير.

**والمهمّة تُسنَد وتُتابَع** — لا رسالةً تضيع في محادثة.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class EmployeeTag(CompanyScopedModel):
    """وسمٌ تكتبه الشركة وتُسنده لمن تشاء."""
    name_ar = models.CharField(_("الوسم"), max_length=60)
    color = models.CharField(
        _("اللون"), max_length=20, blank=True,
        help_text=_("teal · copper · ok · danger — أو فارغ"))
    description = models.CharField(_("الوصف"), max_length=255, blank=True)
    is_active = models.BooleanField(_("مفعّل"), default=True)

    class Meta:
        verbose_name = _("وسم موظفين")
        verbose_name_plural = _("وسوم الموظفين")
        ordering = ["name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "name_ar"],
                                    name="uq_tag_company_name"),
        ]

    def __str__(self):
        return self.name_ar


class EmployeeTagAssignment(CompanyScopedModel):
    """إسناد وسمٍ لموظف."""
    tag = models.ForeignKey(EmployeeTag, on_delete=models.CASCADE,
                            related_name="assignments")
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="tag_assignments")
    assigned_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("إسناد وسم")
        verbose_name_plural = _("إسنادات الوسوم")
        constraints = [
            models.UniqueConstraint(fields=["tag", "employment"],
                                    name="uq_tagassign_tag_emp"),
        ]

    def __str__(self):
        return f"{self.tag_id} → {self.employment_id}"


class TaskStatus(models.TextChoices):
    OPEN = "open", _("مفتوحة")
    IN_PROGRESS = "in_progress", _("قيد التنفيذ")
    DONE = "done", _("منجزة")
    CANCELLED = "cancelled", _("ملغاة")


class TaskPriority(models.TextChoices):
    LOW = "low", _("منخفضة")
    NORMAL = "normal", _("عادية")
    HIGH = "high", _("عالية")
    URGENT = "urgent", _("عاجلة")


class Task(CompanyScopedModel):
    """
    مهمّةٌ تُسنَد وتُتابَع.

    ⚠️ **ولا تُحذف المنجزة**: سجلُّ ما أُنجز يُراجَع، ومحوُه
    يُخفي عمل الموظف — وتُلغى بدل ذلك.
    """
    title = models.CharField(_("المهمّة"), max_length=200)
    description = models.TextField(_("التفاصيل"), blank=True)

    assignee = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="tasks", verbose_name=_("المسنَد إليه"))
    assigned_by = models.ForeignKey(
        "employees.Employment", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="tasks_assigned",
        verbose_name=_("المُسنِد"))

    due_date = models.DateField(_("تاريخ الاستحقاق"), null=True, blank=True)
    priority = models.CharField(_("الأولوية"), max_length=10,
                                choices=TaskPriority.choices,
                                default=TaskPriority.NORMAL)
    status = models.CharField(_("الحالة"), max_length=15,
                              choices=TaskStatus.choices,
                              default=TaskStatus.OPEN, db_index=True)

    completed_at = models.DateTimeField(null=True, blank=True)
    completion_note = models.CharField(_("ملاحظة الإنجاز"), max_length=255,
                                       blank=True)

    class Meta:
        verbose_name = _("مهمّة")
        verbose_name_plural = _("المهامّ")
        ordering = ["status", "due_date", "-id"]
        indexes = [
            models.Index(fields=["assignee", "status"],
                         name="idx_task_assignee_status"),
            models.Index(fields=["company", "due_date"],
                         name="idx_task_company_due"),
        ]

    def __str__(self):
        return self.title
