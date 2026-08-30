"""
السلف والعهد ووثائق الموظف (ق-41).

السلف: طريقة السداد خيار الشركة، بحد أقصى ومنع سلفة ثانية قبل
سداد الأولى، وإمكانية إلغاء النظام كليًا.

العهد: تُقوَّم ماليًا وتُخصم من مخالصة نهاية الخدمة عند عدم الإرجاع.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


# ══════════════════ السلف ══════════════════

class RepaymentMethod(models.TextChoices):
    EQUAL_INSTALLMENTS = "equal", _("أقساط شهرية متساوية")
    MANUAL = "manual", _("مبلغ يحدده مدير الموارد شهريًا")
    LUMP_SUM = "lump_sum", _("دفعة واحدة في شهر محدد")


class AdvanceStatus(models.TextChoices):
    PENDING = "pending", _("قيد الاعتماد")
    ACTIVE = "active", _("قيد السداد")
    SETTLED = "settled", _("مسدَّدة")
    CANCELLED = "cancelled", _("ملغاة")
    WRITTEN_OFF = "written_off", _("مشطوبة")


class Advance(CompanyScopedModel):
    """سلفة موظف."""

    advance_no = models.CharField(_("رقم السلفة"), max_length=30)
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="advances", verbose_name=_("الموظف"))
    request = models.ForeignKey(
        "leaves.Request", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="advances", verbose_name=_("الطلب"))

    amount = models.DecimalField(_("مبلغ السلفة"), max_digits=12,
                                 decimal_places=2)
    reason = models.TextField(_("السبب"), blank=True)

    repayment_method = models.CharField(
        _("طريقة السداد"), max_length=20, choices=RepaymentMethod.choices,
        default=RepaymentMethod.EQUAL_INSTALLMENTS)
    installments_count = models.PositiveSmallIntegerField(
        _("عدد الأقساط"), default=1,
        help_text=_("عند الأقساط المتساوية"))
    installment_amount = models.DecimalField(
        _("قيمة القسط"), max_digits=12, decimal_places=2,
        null=True, blank=True)
    start_year = models.PositiveSmallIntegerField(_("سنة بدء السداد"))
    start_month = models.PositiveSmallIntegerField(_("شهر بدء السداد"))

    repaid_amount = models.DecimalField(_("المسدَّد"), max_digits=12,
                                        decimal_places=2, default=0)
    status = models.CharField(_("الحالة"), max_length=20,
                              choices=AdvanceStatus.choices,
                              default=AdvanceStatus.PENDING, db_index=True)

    approved_at = models.DateTimeField(_("وقت الاعتماد"), null=True, blank=True)
    approved_by_person = models.ForeignKey(
        "employees.Person", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_advances")
    settled_at = models.DateTimeField(_("وقت السداد الكامل"),
                                      null=True, blank=True)
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("سلفة")
        verbose_name_plural = _("السلف")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "advance_no"],
                                    name="uq_advance_no_per_company"),
            models.CheckConstraint(condition=models.Q(amount__gt=0),
                                   name="chk_advance_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["employment", "status"]),
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self):
        return f"{self.advance_no} — {self.amount}"

    @property
    def outstanding(self):
        """المتبقي على الموظف."""
        return self.amount - self.repaid_amount

    @property
    def is_outstanding(self):
        return (self.status == AdvanceStatus.ACTIVE
                and self.outstanding > 0)


class AdvanceInstallment(CompanyScopedModel):
    """
    قسط سلفة — يُخصم في مسير شهر معيّن.

    يُسجَّل بعد الخصم الفعلي، فسجل السداد مرتبط بقسيمة حقيقية.
    """

    advance = models.ForeignKey(Advance, on_delete=models.CASCADE,
                                related_name="installments")
    period_year = models.PositiveSmallIntegerField(_("السنة"))
    period_month = models.PositiveSmallIntegerField(_("الشهر"))
    amount = models.DecimalField(_("المبلغ"), max_digits=12, decimal_places=2)
    payslip = models.ForeignKey(
        "payroll.Payslip", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="advance_installments", verbose_name=_("القسيمة"))
    is_deducted = models.BooleanField(_("خُصم فعلًا"), default=False)
    note = models.CharField(_("ملاحظة"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("قسط سلفة")
        verbose_name_plural = _("أقساط السلف")
        ordering = ["advance", "period_year", "period_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["advance", "period_year", "period_month"],
                name="uq_installment_per_period"),
        ]


# ══════════════════ العهد ══════════════════

class AssetCategory(models.TextChoices):
    DEVICE = "device", _("جهاز")
    VEHICLE = "vehicle", _("مركبة")
    PHONE = "phone", _("هاتف")
    TOOL = "tool", _("أداة")
    UNIFORM = "uniform", _("زي")
    CARD = "card", _("بطاقة")
    OTHER = "other", _("أخرى")


class AssetStatus(models.TextChoices):
    ASSIGNED = "assigned", _("بعهدة الموظف")
    RETURNED = "returned", _("مُرجَعة")
    DAMAGED = "damaged", _("تالفة")
    LOST = "lost", _("مفقودة")
    DEDUCTED = "deducted", _("خُصمت قيمتها")


class Asset(CompanyScopedModel):
    """
    عهدة بقيمة مالية (ق-41).

    القيمة تُخصم من مخالصة نهاية الخدمة عند عدم الإرجاع — الجرد
    وحده لا يكفي.
    """

    asset_no = models.CharField(_("رقم العهدة"), max_length=40)
    name_ar = models.CharField(_("الوصف"), max_length=200)
    category = models.CharField(_("التصنيف"), max_length=20,
                                choices=AssetCategory.choices,
                                default=AssetCategory.OTHER)
    serial_number = models.CharField(_("الرقم التسلسلي"), max_length=100,
                                     blank=True)
    value = models.DecimalField(
        _("القيمة"), max_digits=12, decimal_places=2, default=0,
        help_text=_("تُخصم من المخالصة عند عدم الإرجاع"))

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="assets", verbose_name=_("الموظف"))
    assigned_date = models.DateField(_("تاريخ التسليم"))
    expected_return_date = models.DateField(_("تاريخ الإرجاع المتوقع"),
                                            null=True, blank=True)
    returned_date = models.DateField(_("تاريخ الإرجاع"),
                                     null=True, blank=True)

    status = models.CharField(_("الحالة"), max_length=20,
                              choices=AssetStatus.choices,
                              default=AssetStatus.ASSIGNED, db_index=True)
    condition_note = models.TextField(_("ملاحظة الحالة"), blank=True)
    handover_document = models.CharField(_("مستند التسليم"), max_length=500,
                                         blank=True)

    class Meta:
        verbose_name = _("عهدة")
        verbose_name_plural = _("العهد")
        ordering = ["-assigned_date"]
        constraints = [
            models.UniqueConstraint(fields=["company", "asset_no"],
                                    name="uq_asset_no_per_company"),
        ]
        indexes = [
            models.Index(fields=["employment", "status"]),
        ]

    def __str__(self):
        return f"{self.asset_no} — {self.name_ar}"

    @property
    def is_outstanding(self):
        """بعهدة الموظف ولم تُرجَع — تدخل المخالصة."""
        return self.status in (AssetStatus.ASSIGNED, AssetStatus.LOST,
                               AssetStatus.DAMAGED)


# ══════════════════ وثائق الموظف ══════════════════

class DocumentType(models.TextChoices):
    IQAMA = "iqama", _("إقامة")
    PASSPORT = "passport", _("جواز سفر")
    NATIONAL_ID = "national_id", _("هوية وطنية")
    WORK_PERMIT = "work_permit", _("رخصة عمل")
    DRIVING_LICENSE = "driving_license", _("رخصة قيادة")
    HEALTH_CERT = "health_cert", _("شهادة صحية")
    QUALIFICATION = "qualification", _("مؤهل علمي")
    CONTRACT = "contract", _("عقد عمل")
    MEDICAL_INSURANCE = "medical_insurance", _("تأمين طبي")
    OTHER = "other", _("أخرى")


class EmployeeDocument(CompanyScopedModel):
    """
    وثيقة موظف بتاريخ انتهاء — أساس التنبيه الاستباقي.

    انتهاء إقامة أو رخصة عمل يوقف الموظف عن العمل ويعرّض الشركة
    لغرامات، فالتنبيه قبلها أرخص من معالجتها.
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="documents", verbose_name=_("الموظف"))
    document_type = models.CharField(_("النوع"), max_length=30,
                                     choices=DocumentType.choices)
    document_number = models.CharField(_("الرقم"), max_length=60, blank=True)
    issue_date = models.DateField(_("تاريخ الإصدار"), null=True, blank=True)
    expiry_date = models.DateField(_("تاريخ الانتهاء"), null=True, blank=True,
                                   db_index=True)
    expiry_hijri = models.CharField(_("الانتهاء هجريًا"), max_length=10,
                                    blank=True)
    issuing_authority = models.CharField(_("جهة الإصدار"), max_length=150,
                                         blank=True)
    file_url = models.CharField(_("الملف"), max_length=500, blank=True)
    alert_days_before = models.PositiveSmallIntegerField(
        _("التنبيه قبل (أيام)"), default=60)
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("وثيقة موظف")
        verbose_name_plural = _("وثائق الموظفين")
        ordering = ["expiry_date"]
        indexes = [
            models.Index(fields=["company", "expiry_date"]),
            models.Index(fields=["employment", "document_type"]),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.document_number}"

    @property
    def days_to_expiry(self):
        from datetime import date
        if self.expiry_date is None:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def is_expired(self):
        d = self.days_to_expiry
        return d is not None and d < 0

    @property
    def needs_alert(self):
        d = self.days_to_expiry
        return d is not None and d <= self.alert_days_before
