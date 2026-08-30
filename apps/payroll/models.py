"""
مكوّنات الأجر والإعدادات المالية — أساس كل حسابات الرواتب.

قرارات المالك (السبرنت 6):
  • الأجر الخاضع للتأمينات: الأساسي + بدل السكن فقط (افتراض)
  • أجر نهاية الخدمة: حسب العقد — الشركة تحدد بلا افتراض مفروض
  • العمل الإضافي: أجر ساعة الأجر الكامل + 50% من ساعة الأساسي

المبدأ الحاكم (ق-19/1): لا رقم تشريعي داخل الكود. كل نسبة وحد في
جدول بتاريخ سريان، ويُقرأ بتاريخ الاستحقاق لا تاريخ اليوم.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ComponentType(models.TextChoices):
    EARNING   = "earning",   _("استحقاق")
    DEDUCTION = "deduction", _("استقطاع")


class CalculationType(models.TextChoices):
    FIXED      = "fixed",      _("مبلغ ثابت")
    PERCENT_OF = "percent_of", _("نسبة من مكوّن آخر")
    FORMULA    = "formula",    _("معادلة")


class PayComponent(CompanyScopedModel):
    """
    مكوّن أجر — بدل أو استقطاع.

    الأعلام الأربعة هي جوهر النظام: كل خلاف عمّالي في السعودية
    تقريبًا ينشأ من سؤال «هل هذا البدل يدخل في نهاية الخدمة؟».
    نجعلها إعدادًا صريحًا يراه العميل ويوقّع عليه، لا افتراضًا مخفيًا.
    """

    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("الاسم"), max_length=150)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=150, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=150, blank=True)

    component_type = models.CharField(
        _("النوع"), max_length=20, choices=ComponentType.choices)
    calculation_type = models.CharField(
        _("طريقة الاحتساب"), max_length=20,
        choices=CalculationType.choices, default=CalculationType.FIXED)
    percent_of_code = models.CharField(
        _("نسبة من"), max_length=40, blank=True,
        help_text=_("رمز المكوّن الأساس عند النسبة — غالبًا BASIC"))
    percent_value = models.DecimalField(
        _("النسبة"), max_digits=7, decimal_places=4, null=True, blank=True)

    # ══ الأعلام النظامية الأربعة ══
    is_gosi_subject = models.BooleanField(
        _("خاضع للتأمينات"), default=False,
        help_text=_("يدخل في الأجر الخاضع لاشتراك التأمينات"))
    is_eosb_subject = models.BooleanField(
        _("يدخل في نهاية الخدمة"), default=False,
        help_text=_("حسب العقد — الشركة تحدد ما يدخل"))
    is_overtime_base = models.BooleanField(
        _("يدخل أساس الإضافي"), default=False)
    is_wps_subject = models.BooleanField(
        _("يظهر في حماية الأجور"), default=True)
    is_absence_base = models.BooleanField(
        _("يدخل أساس خصم الغياب"), default=True,
        help_text=_("ق-36: الافتراض أن الخصم على الإجمالي. الشركة "
                    "تستثني بدلًا أو أكثر بإطفاء هذا العلم"))

    is_taxable = models.BooleanField(_("خاضع للضريبة"), default=False)
    display_order = models.IntegerField(_("الترتيب"), default=0)
    is_active = models.BooleanField(_("نشط"), default=True, db_index=True)
    is_system = models.BooleanField(
        _("مكوّن نظامي"), default=False,
        help_text=_("لا يُحذف — مثل الراتب الأساسي"))

    class Meta:
        verbose_name = _("مكوّن أجر")
        verbose_name_plural = _("مكوّنات الأجر")
        ordering = ["display_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_paycomponent_code_per_company"),
        ]

    def __str__(self):
        return self.name_ar


class OvertimeBasis(models.TextChoices):
    """
    المادة 107 تحتمل قراءتين والسوق منقسم. الافتراض قرار المالك:
    أجر ساعة الأجر الكامل + 50% من ساعة الأساسي.
    """
    FULL_PLUS_HALF_BASIC = "full_plus_half_basic", _(
        "أجر ساعة الأجر الكامل + 50% من ساعة الأساسي")
    BASIC_TIMES_1_5 = "basic_x1_5", _("أجر ساعة الأساسي × 1.5")
    FULL_TIMES_1_5 = "full_x1_5", _("أجر ساعة الأجر الكامل × 1.5")


class PayrollRunType(models.TextChoices):
    """
    ثلاثة أنواع مسيرات (ق-21). مسير المستحقات يخرج عن الدورة
    الشهرية — يُنشأ فور اعتماد حساب نهاية الخدمة لموظف واحد.
    """
    REGULAR       = "regular",       _("المسير العام")
    SUPPLEMENTARY = "supplementary", _("مسير الإضافي والإضافات")
    SETTLEMENT    = "settlement",    _("مسير المستحقات ونهاية الخدمة")


class EOSBWageBasis(models.TextChoices):
    """
    ما يدخل في أجر مكافأة نهاية الخدمة — حسب العقد (قرار المالك).
    NOT_SET يمنع تشغيل أول مسير مستحقات حتى تختار الشركة صراحةً:
    الصمت هنا قرار مالي لم يتخذه أحد.
    """
    NOT_SET       = "not_set",       _("لم يُحدَّد بعد")
    BASIC_ONLY    = "basic_only",    _("الأساسي وحده")
    FLAGGED       = "flagged",       _("حسب أعلام المكوّنات (is_eosb_subject)")


class PayrollSettings(CompanyScopedModel):
    """إعدادات الرواتب لكل شركة — تُقرأ منها كل الحسابات."""

    # ── أنواع المسيرات (ق-21) ──
    merge_supplementary_into_regular = models.BooleanField(
        _("دمج مسير الإضافي مع العام"), default=True,
        help_text=_("الافتراض: مسير واحد. الفصل خيار الشركة"))
    terminated_pay_in_regular_run = models.BooleanField(
        _("راتب أيام المنتهية خدمته في المسير العام"), default=True,
        help_text=_("إن أُطفئ، يُدمج راتب الأيام في مسير المستحقات"))

    # ── تحمّل حصة الموظف من التأمينات (ق-29) ──
    company_bears_employee_gosi = models.BooleanField(
        _("الشركة تتحمل حصة الموظف من التأمينات"), default=False,
        help_text=_("الافتراض: الخصم من الموظف. عند التفعيل يستلم "
                    "راتبه كاملًا وتظهر الحصة في القسيمة مقابل بند "
                    "«تحملته الشركة». يمكن استثناء موظف بعينه."))

    # ── أجر نهاية الخدمة ──
    exclude_unpaid_leave_from_service = models.BooleanField(
        _("استبعاد الإجازات بلا أجر من مدة الخدمة"), default=False,
        help_text=_("خيار الشركة — لا افتراض مفروض (ق-24)"))
    eosb_wage_basis = models.CharField(
        _("أساس أجر المكافأة"), max_length=20,
        choices=EOSBWageBasis.choices, default=EOSBWageBasis.NOT_SET,
        help_text=_("يجب تحديده قبل أول مسير مستحقات"))

    payroll_days_per_month = models.PositiveSmallIntegerField(
        _("أيام الشهر للاحتساب"), default=30,
        validators=[MinValueValidator(28), MaxValueValidator(31)],
        help_text=_("القاعدة المعتمدة في السوق السعودي: 30 يومًا"))
    working_hours_per_day = models.DecimalField(
        _("ساعات العمل اليومية"), max_digits=4, decimal_places=2, default=8)
    ramadan_hours_per_day = models.DecimalField(
        _("ساعات رمضان للمسلمين"), max_digits=4, decimal_places=2, default=6)

    overtime_basis = models.CharField(
        _("أساس العمل الإضافي"), max_length=30,
        choices=OvertimeBasis.choices,
        default=OvertimeBasis.FULL_PLUS_HALF_BASIC)

    # نهاية الخدمة: الشركة تحدد ما يدخل عبر أعلام المكوّنات
    eosb_note = models.TextField(
        _("ملاحظة نهاية الخدمة"), blank=True,
        help_text=_("ما يدخل في أجر المكافأة يحدده علم is_eosb_subject "
                    "على كل مكوّن، حسب العقد"))

    # ق-37: الصافي السالب مستحيل نظاميًا — لا سياسة تختارها الشركة.
    # الخصم يُقصّ عند حد الاستحقاق، والصافي أدناه صفر.
    exclude_zero_net_from_wps = models.BooleanField(
        _("استبعاد الصافي الصفري من ملف حماية الأجور"), default=True,
        help_text=_("الموظف بصافٍ صفري يُحذف من ملف البنك قبل الإرسال"))
    variance_threshold_percent = models.DecimalField(
        _("عتبة الفروقات %"), max_digits=5, decimal_places=2, default=10,
        help_text=_("تغيّر الصافي بأكثر من هذه النسبة يظهر في شاشة المراجعة"))

    class Meta:
        verbose_name = _("إعدادات رواتب")
        verbose_name_plural = _("إعدادات الرواتب")
        constraints = [
            models.UniqueConstraint(fields=["company"],
                                    name="uq_payroll_settings_per_company"),
        ]

    def __str__(self):
        return f"إعدادات رواتب — {self.company.legal_name_ar}"


# ══════════ جداول التأمينات: بيانات منصة بتواريخ سريان ══════════

class GosiScheme(models.Model):
    """
    النظام التأميني. بعد إصلاح يوليو 2024 صار نظامان يعملان بالتوازي:
    القدامى على النسب التقليدية، والمنضمّون الجدد على تدرّج تصاعدي.
    """

    code = models.CharField(max_length=30, unique=True)
    name_ar = models.CharField(max_length=150)
    description_ar = models.TextField(blank=True)

    class Meta:
        verbose_name = _("نظام تأميني")
        verbose_name_plural = _("الأنظمة التأمينية")

    def __str__(self):
        return self.name_ar


class GosiRate(models.Model):
    """
    نسب الاشتراك بتاريخ سريان.

    تُقرأ بتاريخ استحقاق المسير لا تاريخ اليوم — فإعادة احتساب مسير
    قديم تعطي نفس الأرقام دائمًا. شرط للتدقيق لا تفاوض عليه.
    """

    scheme = models.ForeignKey(GosiScheme, on_delete=models.PROTECT,
                               related_name="rates")
    effective_from = models.DateField(_("سريان من"), db_index=True)
    effective_to = models.DateField(_("سريان إلى"), null=True, blank=True)

    employee_pension_rate = models.DecimalField(
        _("معاشات — الموظف"), max_digits=6, decimal_places=4, default=0)
    employer_pension_rate = models.DecimalField(
        _("معاشات — صاحب العمل"), max_digits=6, decimal_places=4, default=0)
    employee_saned_rate = models.DecimalField(
        _("ساند — الموظف"), max_digits=6, decimal_places=4, default=0)
    employer_saned_rate = models.DecimalField(
        _("ساند — صاحب العمل"), max_digits=6, decimal_places=4, default=0)
    employer_hazards_rate = models.DecimalField(
        _("الأخطار المهنية — صاحب العمل"),
        max_digits=6, decimal_places=4, default=0)

    min_subject_wage = models.DecimalField(
        _("الحد الأدنى للأجر الخاضع"), max_digits=12, decimal_places=2)
    max_subject_wage = models.DecimalField(
        _("الحد الأعلى للأجر الخاضع"), max_digits=12, decimal_places=2)

    source_note = models.CharField(
        _("مرجع"), max_length=255, blank=True,
        help_text=_("مصدر النسبة — للتدقيق"))

    class Meta:
        verbose_name = _("نسبة تأمينات")
        verbose_name_plural = _("نسب التأمينات")
        ordering = ["scheme", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["scheme", "effective_from"],
                                    name="uq_gosi_rate_per_date"),
        ]

    def __str__(self):
        return f"{self.scheme.code} من {self.effective_from}"

    @property
    def employee_total_rate(self):
        return self.employee_pension_rate + self.employee_saned_rate

    @property
    def employer_total_rate(self):
        return (self.employer_pension_rate + self.employer_saned_rate
                + self.employer_hazards_rate)


# ══════════════════ مسير الرواتب ══════════════════

class PayrollRunStatus(models.TextChoices):
    DRAFT       = "draft",       _("مسودة")
    CALCULATING = "calculating", _("قيد الاحتساب")
    CALCULATED  = "calculated",  _("محتسب — بانتظار المراجعة")
    SUBMITTED   = "submitted",   _("مرفوع للاعتماد")
    APPROVED    = "approved",    _("معتمد")
    PAID        = "paid",        _("مصروف")
    CANCELLED   = "cancelled",   _("ملغى")
    FAILED      = "failed",      _("فشل الاحتساب")


class PayrollRun(CompanyScopedModel):
    """
    مسير رواتب (ق-21): عام أو إضافي أو مستحقات.

    الاحتساب لا يمس أي شيء خارج جداول المسير — إعادة الاحتساب
    تعطي نفس الأرقام لأن كل المدخلات تُقرأ بتاريخ الاستحقاق.
    """

    run_no = models.CharField(_("رقم المسير"), max_length=30)
    run_type = models.CharField(_("النوع"), max_length=20,
                                choices=PayrollRunType.choices,
                                default=PayrollRunType.REGULAR, db_index=True)
    period_year = models.PositiveSmallIntegerField(_("السنة"))
    period_month = models.PositiveSmallIntegerField(_("الشهر"))
    accrual_date = models.DateField(
        _("تاريخ الاستحقاق"),
        help_text=_("تُقرأ به نسب التأمينات وهياكل الرواتب — لا تاريخ اليوم"))
    payment_date = models.DateField(_("تاريخ الصرف"), null=True, blank=True)

    status = models.CharField(_("الحالة"), max_length=20,
                              choices=PayrollRunStatus.choices,
                              default=PayrollRunStatus.DRAFT, db_index=True)

    # ── الإجماليات ──
    employee_count = models.PositiveIntegerField(_("عدد الموظفين"), default=0)
    total_gross = models.DecimalField(_("إجمالي الاستحقاقات"), max_digits=14,
                                      decimal_places=2, default=0)
    total_deductions = models.DecimalField(_("إجمالي الاستقطاعات"),
                                           max_digits=14, decimal_places=2,
                                           default=0)
    total_net = models.DecimalField(_("إجمالي الصافي"), max_digits=14,
                                    decimal_places=2, default=0)
    total_employer_cost = models.DecimalField(
        _("تكلفة صاحب العمل"), max_digits=14, decimal_places=2, default=0)

    calculated_at = models.DateTimeField(_("وقت الاحتساب"), null=True, blank=True)
    submitted_at = models.DateTimeField(_("وقت الرفع"), null=True, blank=True)
    approved_at = models.DateTimeField(_("وقت الاعتماد"), null=True, blank=True)
    approved_by_person = models.ForeignKey(
        "employees.Person", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_payroll_runs", verbose_name=_("المعتمِد"))

    variance_count = models.PositiveIntegerField(
        _("عدد الفروقات"), default=0,
        help_text=_("موظفون تغيّر صافيهم عن الشهر السابق فوق العتبة"))
    error_log = models.JSONField(_("سجل الأخطاء"), default=list, blank=True)
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("مسير رواتب")
        verbose_name_plural = _("مسيرات الرواتب")
        ordering = ["-period_year", "-period_month", "run_type"]
        constraints = [
            models.UniqueConstraint(fields=["company", "run_no"],
                                    name="uq_payroll_run_no"),
            models.UniqueConstraint(
                fields=["company", "run_type", "period_year", "period_month"],
                condition=models.Q(status__in=["draft", "calculating",
                                               "calculated", "submitted",
                                               "approved", "paid"]),
                name="uq_active_run_per_period"),
        ]

    def __str__(self):
        return f"{self.run_no} — {self.period_year}/{self.period_month:02d}"

    @property
    def is_editable(self):
        return self.status in (PayrollRunStatus.DRAFT,
                               PayrollRunStatus.CALCULATED,
                               PayrollRunStatus.FAILED)

    @property
    def is_locked(self):
        """المعتمد والمصروف لا يُعاد احتسابهما — سجل مالي نهائي."""
        return self.status in (PayrollRunStatus.APPROVED,
                               PayrollRunStatus.PAID)


class Payslip(CompanyScopedModel):
    """
    قسيمة راتب موظف في مسير.

    calculation_trace يحفظ كل خطوة — الموظف يعيد الحساب بورقة وقلم،
    وهذا ما يُنهي أغلب النزاعات.
    """

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE,
                            related_name="payslips")
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="payslips", verbose_name=_("الموظف"))

    # ── الأجور المرجعية (تُحفظ لحظة الاحتساب) ──
    basic_salary = models.DecimalField(_("الأساسي"), max_digits=12,
                                       decimal_places=2, default=0)
    gross_earnings = models.DecimalField(_("إجمالي الاستحقاقات"),
                                         max_digits=12, decimal_places=2,
                                         default=0)
    total_deductions = models.DecimalField(_("إجمالي الاستقطاعات"),
                                           max_digits=12, decimal_places=2,
                                           default=0)
    net_pay = models.DecimalField(_("صافي المستحق"), max_digits=12,
                                  decimal_places=2, default=0)
    employer_cost = models.DecimalField(_("تكلفة صاحب العمل"), max_digits=12,
                                        decimal_places=2, default=0)

    # ── التأمينات ──
    gosi_subject_wage = models.DecimalField(_("الأجر الخاضع"), max_digits=12,
                                            decimal_places=2, default=0)
    gosi_employee_share = models.DecimalField(_("حصة الموظف"), max_digits=12,
                                              decimal_places=2, default=0)
    gosi_employer_share = models.DecimalField(_("حصة صاحب العمل"),
                                              max_digits=12, decimal_places=2,
                                              default=0)
    gosi_borne_by_company = models.BooleanField(
        _("الشركة تحملت حصة الموظف"), default=False)

    # ── الحضور ──
    worked_days = models.DecimalField(_("أيام العمل"), max_digits=6,
                                      decimal_places=2, default=0)
    unpaid_absence_days = models.DecimalField(_("أيام الغياب"), max_digits=6,
                                              decimal_places=2, default=0)
    unpaid_leave_days = models.DecimalField(
        _("أيام الإجازة بلا أجر"), max_digits=6, decimal_places=2, default=0,
        help_text=_("منفصلة عن الغياب — حق مأذون لا مخالفة (ق-32)"))
    overtime_minutes = models.PositiveIntegerField(_("دقائق الإضافي"),
                                                   default=0)

    payment_method = models.CharField(_("طريقة الصرف"), max_length=20,
                                      default="bank")
    iban = models.CharField(_("الآيبان"), max_length=24, blank=True)
    include_in_wps = models.BooleanField(_("في حماية الأجور"), default=False)

    previous_net = models.DecimalField(_("صافي الشهر السابق"), max_digits=12,
                                       decimal_places=2, null=True, blank=True)
    variance_percent = models.DecimalField(_("نسبة الفرق"), max_digits=7,
                                           decimal_places=2, null=True,
                                           blank=True)
    has_variance = models.BooleanField(_("فرق يحتاج مراجعة"), default=False)

    calculation_trace = models.JSONField(_("خطوات الاحتساب"), default=dict,
                                         blank=True)
    warnings = models.JSONField(_("تنبيهات"), default=list, blank=True)

    class Meta:
        verbose_name = _("قسيمة راتب")
        verbose_name_plural = _("قسائم الرواتب")
        ordering = ["run", "employment__employee_no"]
        constraints = [
            models.UniqueConstraint(fields=["run", "employment"],
                                    name="uq_payslip_per_run"),
        ]
        indexes = [
            models.Index(fields=["company", "run"]),
            models.Index(fields=["employment", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.employment.employee_no} — {self.run.run_no}"


class PayslipLineType(models.TextChoices):
    EARNING = "earning", _("استحقاق")
    DEDUCTION = "deduction", _("استقطاع")
    EMPLOYER_COST = "employer_cost", _("تكلفة صاحب عمل")
    INFO = "info", _("بيان فقط")


class PayslipLine(models.Model):
    """بند في القسيمة — بشرح احتسابه."""

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE,
                                related_name="lines")
    component_code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("البيان"), max_length=150)
    line_type = models.CharField(_("النوع"), max_length=20,
                                 choices=PayslipLineType.choices)
    amount = models.DecimalField(_("المبلغ"), max_digits=12, decimal_places=2)
    explanation = models.CharField(
        _("شرح الاحتساب"), max_length=300, blank=True,
        help_text=_("مثال: 3 أيام × 400 ريال"))
    display_order = models.IntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("بند قسيمة")
        verbose_name_plural = _("بنود القسائم")
        ordering = ["payslip", "display_order", "component_code"]

    def __str__(self):
        return f"{self.name_ar}: {self.amount}"


# ══════════════════ قوالب ملفات البنوك ══════════════════

class BankFileFormat(models.TextChoices):
    CSV = "csv", _("CSV")
    TXT_DELIMITED = "txt", _("نصي بفاصل")
    EXCEL = "xlsx", _("إكسل")


class BankTemplate(CompanyScopedModel):
    """
    قالب ملف بنك.

    القوالب الجاهزة تُنسخ للشركة (is_builtin=True) وتعدّلها بحرية،
    والشركة تنشئ قوالب خاصة لبنوك لا قالب لها.

    ⚠️ لا نبني قالبًا من تخمين: البنك يسلّم مواصفاته للمنشأة عند
    توقيع اتفاقية الرواتب. القالب الخاطئ يعني رفض الملف وتأخر رواتب.
    """

    code = models.CharField(_("الرمز"), max_length=30)
    name_ar = models.CharField(_("اسم القالب"), max_length=120)
    bank_name_ar = models.CharField(_("البنك"), max_length=120)
    swift_prefix = models.CharField(
        _("رمز سويفت"), max_length=4, blank=True,
        help_text=_("NCBK للأهلي، RJHI للراجحي"))

    file_format = models.CharField(_("الصيغة"), max_length=10,
                                   choices=BankFileFormat.choices,
                                   default=BankFileFormat.CSV)
    delimiter = models.CharField(_("الفاصل"), max_length=3, default=",")
    include_header = models.BooleanField(_("يتضمن سطر ترويسة"), default=True)
    line_ending = models.CharField(
        _("نهاية السطر"), max_length=10, default="crlf",
        choices=[("crlf", _("ويندوز CRLF")), ("lf", _("يونكس LF"))])
    encoding = models.CharField(_("الترميز"), max_length=20, default="utf-8")
    filename_pattern = models.CharField(
        _("نمط اسم الملف"), max_length=120, default="{bank}_For_{date}.csv",
        help_text=_("متغيرات: {bank} {date} {period} {company}"))

    is_builtin = models.BooleanField(
        _("قالب جاهز"), default=False,
        help_text=_("مبني على مواصفات موثّقة من البنك"))
    is_active = models.BooleanField(_("نشط"), default=True)
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("قالب بنك")
        verbose_name_plural = _("قوالب البنوك")
        ordering = ["bank_name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_bank_template_code"),
        ]

    def __str__(self):
        return f"{self.bank_name_ar} — {self.name_ar}"


class BankColumnSource(models.TextChoices):
    EMPLOYEE_BANK_SWIFT = "employee_bank_swift", _("رمز بنك الموظف")
    IBAN = "iban", _("الآيبان")
    ACCOUNT_NUMBER = "account_number", _("رقم الحساب")
    NET_PAY = "net_pay", _("صافي المستحق")
    GROSS = "gross", _("إجمالي الاستحقاقات")
    BASIC = "basic", _("الراتب الأساسي")
    HOUSING = "housing", _("بدل السكن")
    OTHER_EARNINGS = "other_earnings", _("باقي الاستحقاقات")
    DEDUCTIONS = "deductions", _("إجمالي الاستقطاعات")
    EMPLOYEE_NO = "employee_no", _("الرقم الوظيفي")
    NAME_AR = "name_ar", _("الاسم بالعربية")
    NAME_EN = "name_en", _("الاسم بالإنجليزية")
    ID_NUMBER = "id_number", _("رقم الهوية")
    DEPARTMENT = "department", _("القسم")
    BRANCH = "branch", _("الفرع")
    JOB_TITLE = "job_title", _("المسمى الوظيفي")
    CONSTANT = "constant", _("قيمة ثابتة")
    SEQUENCE = "sequence", _("رقم تسلسلي")


class BankColumn(models.Model):
    """عمود في قالب البنك."""

    template = models.ForeignKey(BankTemplate, on_delete=models.CASCADE,
                                 related_name="columns")
    position = models.PositiveSmallIntegerField(_("الترتيب"))
    header = models.CharField(_("عنوان العمود"), max_length=80)
    source = models.CharField(_("المصدر"), max_length=40,
                              choices=BankColumnSource.choices)
    constant_value = models.CharField(
        _("القيمة الثابتة"), max_length=120, blank=True,
        help_text=_("عند المصدر: قيمة ثابتة"))
    number_format = models.CharField(
        _("تنسيق الرقم"), max_length=20, blank=True,
        help_text=_("مثال: 0.00 لخانتين عشريتين"))
    text_transform = models.CharField(
        _("تحويل النص"), max_length=20, blank=True,
        choices=[("upper", _("حروف كبيرة")), ("lower", _("حروف صغيرة")),
                 ("strip", _("إزالة المسافات"))])
    max_length = models.PositiveSmallIntegerField(
        _("أقصى طول"), null=True, blank=True)

    class Meta:
        verbose_name = _("عمود قالب")
        verbose_name_plural = _("أعمدة القوالب")
        ordering = ["template", "position"]
        constraints = [
            models.UniqueConstraint(fields=["template", "position"],
                                    name="uq_bank_column_position"),
        ]

    def __str__(self):
        return f"{self.position}. {self.header}"
