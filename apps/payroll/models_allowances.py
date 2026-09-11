"""
كتالوج المخصّصات المصروفة (ق-134).

**الشركة تُعرّف مخصّصاتها وتُسندها للأفراد** — «غداء عمل»، «بدل
مواصلات»، «بدل سفر». فلا يرى الموظف إلا ما أُسند له، ولا يطلب
مبلغًا لم تُقرّه.

⚠️ **والمنع على المخصّص نفسه لا على نوع الطلب**: من له «غداء عمل»
و«مواصلات» يطلبهما في يومٍ واحد — ولا يطلب الغداء مرّتين.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class AmountMode(models.TextChoices):
    FIXED = "fixed", _("مبلغ ثابت")
    CAP = "cap", _("سقف أعلى")


class ClaimableAllowance(CompanyScopedModel):
    """
    مخصّصٌ يطلب الموظف صرفه.

    **الثابت** يُصرف كما هو، **والسقف** يُدخل الموظف أقلّ منه —
    فالغداء بفاتورته، والمواصلات ببدلٍ مقطوع.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("المخصّص"), max_length=120)
    description = models.CharField(_("الوصف"), max_length=255, blank=True)

    mode = models.CharField(_("نوع المبلغ"), max_length=10,
                            choices=AmountMode.choices,
                            default=AmountMode.FIXED)
    amount = models.DecimalField(
        _("المبلغ أو السقف"), max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)])

    requires_attachment = models.BooleanField(
        _("يلزمه مرفق"), default=False,
        help_text=_("كفاتورةٍ تُثبت الصرف"))

    #: بند الأجر الذي يدخل به المسير
    component_code = models.CharField(
        _("بند المسير"), max_length=40, blank=True,
        help_text=_("يُصرف به في القسيمة — فارغ = يدويًّا"))

    is_active = models.BooleanField(_("مفعّل"), default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("مخصّص مصروف")
        verbose_name_plural = _("المخصّصات المصروفة")
        ordering = ["sort_order", "name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_claimallow_company_code"),
        ]

    def __str__(self):
        return self.name_ar


class AllowanceEligibility(CompanyScopedModel):
    """
    إسناد مخصّصٍ لموظف — **فلا يراه من لم يُسند له**.

    ⚠️ ولو أُتيح للجميع لطلبه من لا يستحقّه، ورُدّ فضاع وقت
    الطرفين.
    """
    allowance = models.ForeignKey(
        ClaimableAllowance, on_delete=models.CASCADE,
        related_name="eligibilities", verbose_name=_("المخصّص"))
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="allowance_eligibilities", verbose_name=_("الموظف"))

    #: سقفٌ يخصّ هذا الموظف — يغلب سقف المخصّص إن وُجد
    custom_amount = models.DecimalField(
        _("مبلغ خاصّ"), max_digits=12, decimal_places=2,
        null=True, blank=True)
    granted_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("استحقاق مخصّص")
        verbose_name_plural = _("استحقاقات المخصّصات")
        constraints = [
            models.UniqueConstraint(fields=["allowance", "employment"],
                                    name="uq_alloweligib_allow_emp"),
        ]

    def __str__(self):
        return f"{self.allowance_id} → {self.employment_id}"

    @property
    def effective_amount(self):
        """المبلغ الساري له — الخاصّ إن وُجد وإلا مبلغ المخصّص."""
        return (self.custom_amount
                if self.custom_amount is not None
                else self.allowance.amount)
