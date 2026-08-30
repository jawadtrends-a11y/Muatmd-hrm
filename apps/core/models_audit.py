"""
سجل عمليات المنشأة (ق-44).

كل تعديل يُسجَّل، ويُعرض في مكان التعديل نفسه لا في شاشة منفصلة:
ملف الموظف يعرض تعديلاته أسفله، والمسير يعرض من اعتمده.

معزول بالحساب كبقية البيانات — شركة لا ترى سجل أخرى.
الحفظ بلا حد: نصوص لا ملفات، والقرص أرخص من فقدان أثر تعديل.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel


class AuditAction(models.TextChoices):
    CREATE = "create", _("إنشاء")
    UPDATE = "update", _("تعديل")
    DELETE = "delete", _("حذف")
    APPROVE = "approve", _("اعتماد")
    REJECT = "reject", _("رفض")
    APPROVED = "approved", _("اعتماد")     # قيمة ApprovalDecision
    REJECTED = "rejected", _("رفض")        # قيمة ApprovalDecision
    SUBMIT = "submit", _("رفع")
    CANCEL = "cancel", _("إلغاء")
    EXPORT = "export", _("تصدير")
    LOGIN = "login", _("دخول")


class AuditEntry(AccountScopedModel):
    """
    قيد في سجل العمليات.

    object_type و object_id يربطانه بالسجل المعدَّل، فتعرضه الشاشة
    التي تعرض ذلك السجل.
    """

    # ── ما تغيّر ──
    object_type = models.CharField(
        _("نوع السجل"), max_length=60, db_index=True,
        help_text=_("employment · payslip · advance · leave_request …"))
    object_id = models.PositiveIntegerField(_("معرّف السجل"), db_index=True)
    object_label = models.CharField(
        _("وصف السجل"), max_length=200, blank=True,
        help_text=_("يُحفظ لحظة التسجيل فيبقى مفهومًا بعد الحذف"))

    action = models.CharField(_("العملية"), max_length=20,
                              choices=AuditAction.choices, db_index=True)
    changes = models.JSONField(
        _("التغييرات"), default=dict, blank=True,
        help_text=_('{"field": {"from": "قديم", "to": "جديد"}}'))
    summary_ar = models.CharField(_("الملخص"), max_length=300, blank=True)

    # ── من ومتى وكيف ──
    actor_person = models.ForeignKey(
        "employees.Person", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_entries", verbose_name=_("الفاعل"))
    actor_name = models.CharField(
        _("اسم الفاعل"), max_length=200, blank=True,
        help_text=_("يُحفظ نصًا فيبقى بعد حذف الشخص"))
    actor_user_id = models.PositiveIntegerField(_("معرّف المستخدم"),
                                                null=True, blank=True)
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True,
        related_name="audit_entries", verbose_name=_("الشركة"))

    channel = models.CharField(
        _("القناة"), max_length=20, default="web",
        choices=[("web", _("المتصفح")), ("mobile", _("الجوال")),
                 ("whatsapp", _("واتساب")), ("api", _("واجهة برمجية")),
                 ("system", _("النظام"))])
    ip_address = models.GenericIPAddressField(_("العنوان"), null=True,
                                              blank=True)
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("قيد تدقيق")
        verbose_name_plural = _("سجل العمليات")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account", "object_type", "object_id"]),
            models.Index(fields=["company", "-created_at"]),
            models.Index(fields=["actor_person", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.object_type}#{self.object_id}"

    @property
    def changed_fields(self):
        return list(self.changes.keys()) if self.changes else []
