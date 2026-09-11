"""
صرف المخصّصات المعتمدة (ق-134).

⚠️ **القرار عند الاعتماد لا في تعريف المخصّص**: المعتمِد أدرى
بحال الصرف يومَه — أيُدرج في المسير أم يُصرف خارجه.

**وخارج المسير تنتهي مسؤوليتنا بالتوثيق**: كاش أو حوالة أو غيرها
— ولا نُجبر العميل على طريقةٍ لا نعرفها.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class DisbursementMethod(models.TextChoices):
    PAYROLL = "payroll", _("يُدرج في المسير")
    OUTSIDE = "outside", _("صُرف خارج المسير")


class AllowanceClaim(CompanyScopedModel):
    """
    مخصّصٌ اعتُمد صرفه — وطريقةُ صرفه.

    ⚠️ **ولا يُصرف مرّتين**: بندٌ في المسير ثم صرفٌ نقديّ يُضاعف
    المبلغ — فالطريقة واحدة، والتغيير يُوثَّق.
    """
    request_id = models.BigIntegerField(unique=True, db_index=True)
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="allowance_claims")
    allowance = models.ForeignKey(
        "payroll.ClaimableAllowance", on_delete=models.PROTECT,
        related_name="claims")

    claim_date = models.DateField(_("تاريخ الاستحقاق"), db_index=True)
    amount = models.DecimalField(_("المبلغ"), max_digits=12,
                                 decimal_places=2)

    method = models.CharField(
        _("طريقة الصرف"), max_length=15,
        choices=DisbursementMethod.choices, blank=True,
        help_text=_("فارغ = لم يُقرَّر بعد"))

    #: حين يُدرج في المسير — أيّ مسير
    payroll_run_type = models.CharField(
        _("نوع المسير"), max_length=20, blank=True)
    payroll_run_id = models.BigIntegerField(null=True, blank=True)

    #: حين يُصرف خارجه — متى وبمن، **ولا نسأل كيف**
    paid_on = models.DateField(_("تاريخ الصرف"), null=True, blank=True)
    paid_by_person_id = models.BigIntegerField(null=True, blank=True)
    paid_note = models.CharField(_("ملاحظة الصرف"), max_length=255,
                                 blank=True)

    is_settled = models.BooleanField(_("صُرف"), default=False,
                                     db_index=True)

    class Meta:
        verbose_name = _("مخصّص معتمد")
        verbose_name_plural = _("المخصّصات المعتمدة")
        ordering = ["-claim_date", "-id"]
        indexes = [
            models.Index(fields=["company", "is_settled"],
                         name="idx_claim_company_settled"),
        ]

    def __str__(self):
        return f"{self.allowance_id} — {self.amount}"
