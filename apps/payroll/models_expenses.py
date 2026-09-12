"""
المصروفات وتعويضها (ق-139).

**المصروف تعويضٌ عمّا دفعه الموظف فعلًا** — لا استحقاقٌ مُقرّ.
فوقودٌ صرفه في مهمّة، وضيافةٌ لعميل، ومكتبياتٌ اشتراها.

⚠️ **والفرق عن المخصّص جوهريّ**: المخصّص بمبلغٍ تُقرّه الشركة،
**والمصروف بما دُفع** — فالفاتورة إلزاميّة، والسبب مصرَّحٌ به
بفئته لا باسمٍ عائم (قرار جواد).
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ExpenseCategory(CompanyScopedModel):
    """
    فئة مصروفٍ تُعرّفها الشركة.

    **والسقف اختياريّ**: «وقود حتى ٥٠٠ شهريًّا» — فارغ = بلا حدّ،
    والاعتماد هو الضابط.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("الفئة"), max_length=120)
    description = models.CharField(_("الوصف"), max_length=255, blank=True)

    #: سقف الطلب الواحد — فارغ = بلا حدّ
    max_per_claim = models.DecimalField(
        _("سقف المطالبة"), max_digits=12, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)])
    #: سقف الشهر لكل موظف — فارغ = بلا حدّ
    max_per_month = models.DecimalField(
        _("سقف الشهر"), max_digits=12, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)])

    component_code = models.CharField(
        _("بند المسير"), max_length=40, blank=True,
        help_text=_("يُصرف به في القسيمة — فارغ = يدويًّا"))

    is_active = models.BooleanField(_("مفعّلة"), default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("فئة مصروف")
        verbose_name_plural = _("فئات المصروفات")
        ordering = ["sort_order", "name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_expcat_company_code"),
        ]

    def __str__(self):
        return self.name_ar


class ExpenseStatus(models.TextChoices):
    PENDING = "pending", _("قيد الاعتماد")
    APPROVED = "approved", _("معتمدة")
    REJECTED = "rejected", _("مرفوضة")
    SETTLED = "settled", _("صُرفت")


class ExpenseClaim(CompanyScopedModel):
    """
    مطالبةٌ بتعويض مصروف.

    ⚠️ **والفاتورة إلزامية**: تعويضٌ بلا إثباتٍ يفتح بابًا لا
    يُغلق — فالمصروف يُثبَت لا يُدّعى.
    """
    claim_no = models.CharField(_("رقم المطالبة"), max_length=30,
                                unique=True)
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="expense_claims", verbose_name=_("الموظف"))
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT,
        related_name="claims", verbose_name=_("الفئة"))

    spent_on = models.DateField(_("تاريخ الصرف"), db_index=True)
    amount = models.DecimalField(
        _("المبلغ المدفوع"), max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)])
    description = models.CharField(_("البيان"), max_length=255)

    #: ⚠️ إلزاميّ — لا مطالبة بلا فاتورة
    receipt_url = models.CharField(_("الفاتورة"), max_length=500)

    status = models.CharField(_("الحالة"), max_length=12,
                              choices=ExpenseStatus.choices,
                              default=ExpenseStatus.PENDING,
                              db_index=True)
    decided_by_person_id = models.BigIntegerField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(_("سبب القرار"), max_length=255,
                                     blank=True)

    #: الصرف — بنفس آلية المخصّصات
    method = models.CharField(_("طريقة الصرف"), max_length=15, blank=True)
    payroll_run_type = models.CharField(max_length=20, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    paid_note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("مطالبة مصروف")
        verbose_name_plural = _("مطالبات المصروفات")
        ordering = ["-spent_on", "-id"]
        indexes = [
            models.Index(fields=["company", "status"],
                         name="idx_expclaim_company_status"),
            models.Index(fields=["employment", "spent_on"],
                         name="idx_expclaim_emp_date"),
        ]

    def __str__(self):
        return f"{self.claim_no} — {self.amount}"
