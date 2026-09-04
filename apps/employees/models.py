"""
ملف الموظف: الشخص والارتباط الوظيفي.

المبدأ الحاكم (ق-4): الشخص مفصول عن الارتباط الوظيفي.
سجل شخص واحد داخل الحساب، وارتباطات متعددة بشركاته — فمحمد يدخل
مرة واحدة ويعمل مديرًا في شركة وموظفًا في أخرى.

قاعدة التوزيع:
  • ما يتبع الفرد        → Person
  • ما يتبع علاقته بمنشأة → Employment
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel, CompanyScopedModel


class Gender(models.TextChoices):
    MALE = "male", _("ذكر")
    FEMALE = "female", _("أنثى")


class IdType(models.TextChoices):
    NATIONAL_ID = "national_id", _("هوية وطنية")
    IQAMA = "iqama", _("إقامة")
    BORDER_NUMBER = "border_no", _("رقم حدود")
    PASSPORT = "passport", _("جواز سفر")
    GCC_ID = "gcc_id", _("هوية خليجية")


class MaritalStatus(models.TextChoices):
    SINGLE = "single", _("أعزب")
    MARRIED = "married", _("متزوج")
    DIVORCED = "divorced", _("مطلق")
    WIDOWED = "widowed", _("أرمل")


class Person(AccountScopedModel):
    """
    الشخص — هوية واحدة داخل الحساب مهما تعددت جهات عمله.

    التفرد الحقيقي: رقم الهوية (ق-5). الاسم قد يتكرر لشخصين
    حقيقيين فمنعه خطأ وظيفي — يُكشف تشابهه ويُحذَّر منه فقط.
    """

    # ── الاسم: الاستثناء الوحيد المسموح بازدواجه لغويًا ──
    first_name_ar = models.CharField(_("الاسم الأول"), max_length=80)
    father_name_ar = models.CharField(_("اسم الأب"), max_length=80, blank=True)
    grandfather_name_ar = models.CharField(_("اسم الجد"), max_length=80, blank=True)
    family_name_ar = models.CharField(_("اسم العائلة"), max_length=80)
    full_name_en = models.CharField(
        _("الاسم بالإنجليزية"), max_length=200, blank=True,
        help_text=_("كما في الجواز أو الإقامة حرفيًا"))

    gender = models.CharField(_("الجنس"), max_length=10, choices=Gender.choices)
    birth_date = models.DateField(_("تاريخ الميلاد"), null=True, blank=True)
    birth_date_hijri = models.CharField(_("الميلاد هجريًا"), max_length=10, blank=True)
    marital_status = models.CharField(
        _("الحالة الاجتماعية"), max_length=20,
        choices=MaritalStatus.choices, blank=True)

    # ── الهوية والجنسية ──
    nationality_code = models.CharField(
        _("الجنسية"), max_length=2,
        help_text=_("رمز الدولة ISO 3166-1 alpha-2 — SA للسعودية"))
    id_type = models.CharField(_("نوع الهوية"), max_length=20,
                               choices=IdType.choices)
    id_number = models.CharField(_("رقم الهوية"), max_length=20)
    id_expiry_date = models.DateField(_("انتهاء الهوية"), null=True, blank=True)
    id_expiry_hijri = models.CharField(_("الانتهاء هجريًا"), max_length=10, blank=True)

    passport_number = models.CharField(_("رقم الجواز"), max_length=20, blank=True)
    passport_expiry_date = models.DateField(_("انتهاء الجواز"),
                                            null=True, blank=True)
    border_number = models.CharField(_("رقم الحدود"), max_length=20, blank=True)

    # ── الاتصال ──
    email = models.EmailField(_("البريد الإلكتروني"), blank=True)
    mobile_e164 = models.CharField(
        _("الجوال"), max_length=20, blank=True,
        help_text=_("بصيغة دولية +9665… — مفتاح التعريف في واتساب"))
    preferred_locale = models.CharField(
        _("اللغة المفضلة"), max_length=5, default="ar",
        choices=[("ar", "العربية"), ("en", "English"), ("ur", "اردو")])

    # ── النظام التأميني: صفة في الفرد لا الوظيفة (ق-16) ──
    gosi_scheme_code = models.CharField(
        _("النظام التأميني"), max_length=30, null=True, blank=True,
        help_text=_("يتحدد بتاريخ أول اشتراك للفرد وعمره حينها. "
                    "فارغ = غير مسجّل في التأمينات لدى أي جهة. "
                    "لا يتغير بتغير جهة العمل."))
    gosi_first_subscription_date = models.DateField(
        _("تاريخ أول اشتراك"), null=True, blank=True)

    user = models.OneToOneField(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="person", verbose_name=_("حساب الدخول"))

    class Meta:
        verbose_name = _("شخص")
        verbose_name_plural = _("الأشخاص")
        ordering = ["family_name_ar", "first_name_ar"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "id_type", "id_number"],
                name="uq_person_identity"),
        ]
        indexes = [
            models.Index(fields=["account", "id_number"]),
            models.Index(fields=["account", "mobile_e164"]),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        parts = [self.first_name_ar, self.father_name_ar,
                 self.grandfather_name_ar, self.family_name_ar]
        return " ".join(p for p in parts if p)

    @property
    def is_saudi(self):
        return self.nationality_code == "SA"

    @property
    def masked_id(self):
        """رقم الهوية مقنّعًا — للعرض في كشف التشابه."""
        if len(self.id_number) <= 4:
            return "*" * len(self.id_number)
        return "*" * (len(self.id_number) - 4) + self.id_number[-4:]


class EmploymentType(models.TextChoices):
    PRIMARY = "primary", _("أساسي")
    SECONDARY = "secondary", _("ثانوي")
    SECONDED = "seconded", _("منتدب")
    BOARD_MEMBER = "board_member", _("عضو مجلس")


class EmploymentStatus(models.TextChoices):
    ACTIVE = "active", _("على رأس العمل")
    ON_LEAVE = "on_leave", _("في إجازة")
    SUSPENDED = "suspended", _("موقوف")
    TERMINATED = "terminated", _("منتهية خدمته")
    TRANSFERRED = "transferred", _("منقول داخل المجموعة")


class ContractType(models.TextChoices):
    FIXED_TERM = "fixed_term", _("محدد المدة")
    INDEFINITE = "indefinite", _("غير محدد المدة")


class TransferMode(models.TextChoices):
    SETTLED = "settled", _("تصفية ثم نقل")
    CONTINUED = "continued", _("استمرار احتساب الخدمة")


class PaymentMethod(models.TextChoices):
    BANK = "bank", _("تحويل بنكي")
    CASH = "cash", _("نقدًا")
    CHEQUE = "cheque", _("شيك")


class Employment(CompanyScopedModel):
    """
    الارتباط الوظيفي — شخص × شركة.

    شخص واحد قد يحمل ارتباطات متعددة بشركات الحساب، بمستويات إدارية
    مختلفة (ق-4). كل ما هو مالي معلّق هنا لا على الشخص — فمديرة
    الموارد في شركة لا ترى راتبه في شركة أخرى إطلاقًا.
    """

    person = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="employments",
        verbose_name=_("الشخص"))

    employee_no = models.CharField(_("الرقم الوظيفي"), max_length=30)
    employment_type = models.CharField(
        _("نوع الارتباط"), max_length=20,
        choices=EmploymentType.choices, default=EmploymentType.PRIMARY)
    work_ratio = models.DecimalField(
        _("نسبة الدوام"), max_digits=4, decimal_places=3, default=1,
        help_text=_("1.000 = دوام كامل"))

    # ── التنظيم ──
    branch = models.ForeignKey(
        "organization.Branch", on_delete=models.PROTECT,
        null=True, blank=True, related_name="employments",
        verbose_name=_("الفرع"))
    department = models.ForeignKey(
        "organization.Department", on_delete=models.PROTECT,
        null=True, blank=True, related_name="employments",
        verbose_name=_("القسم"))
    cost_center = models.ForeignKey(
        "organization.CostCenter", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="employments",
        verbose_name=_("مركز التكلفة"))
    job_title = models.ForeignKey(
        "organization.JobTitle", on_delete=models.PROTECT,
        null=True, blank=True, related_name="employments",
        verbose_name=_("المسمى الوظيفي"))
    direct_manager = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subordinates", verbose_name=_("المدير المباشر"))

    # ── العقد والخدمة ──
    join_date = models.DateField(
        _("تاريخ المباشرة"),
        help_text=_("المباشرة في هذه الشركة — للعقد والوثائق الرسمية"))
    service_start_date = models.DateField(
        _("بداية الخدمة المحتسبة"), null=True, blank=True,
        help_text=_("أساس مكافأة نهاية الخدمة والإجازات. يساوي تاريخ "
                    "المباشرة عادةً، ويسبقه عند النقل باستمرارية "
                    "الخدمة داخل المجموعة (ق-14)"))
    contract_type = models.CharField(
        _("نوع العقد"), max_length=20, choices=ContractType.choices,
        default=ContractType.INDEFINITE)
    contract_start_date = models.DateField(_("بداية العقد"), null=True, blank=True)
    contract_end_date = models.DateField(_("نهاية العقد"), null=True, blank=True)
    probation_days = models.PositiveSmallIntegerField(
        _("فترة التجربة (أيام)"), default=90,
        help_text=_("90 يومًا، وتُمدَّد إلى 180 باتفاق كتابي"))
    probation_end_date = models.DateField(_("انتهاء التجربة"),
                                          null=True, blank=True)

    status = models.CharField(
        _("الحالة"), max_length=20, choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE, db_index=True)
    termination_date = models.DateField(_("تاريخ انتهاء الخدمة"),
                                        null=True, blank=True)
    termination_reason = models.CharField(
        _("سبب انتهاء الخدمة"), max_length=40, blank=True,
        help_text=_("من قائمة الوزارة الرسمية (ق-26)"))

    # ── النقل داخل المجموعة (ق-14) ──
    previous_employment = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="next_employments", verbose_name=_("الارتباط السابق"))
    transfer_mode = models.CharField(
        _("نمط النقل"), max_length=20, choices=TransferMode.choices, blank=True)

    # ── أعلام التسجيل النظامي: مستقلة تمامًا (ق-15) ──
    # ق-63: المرتبة والدرجة اختياريتان — للشركات ذات السلّم الوظيفي
    job_grade = models.ForeignKey(
        "employees.JobGrade", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="employments",
        verbose_name=_("المرتبة الوظيفية"))
    job_step = models.ForeignKey(
        "employees.JobStep", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="employments",
        verbose_name=_("الدرجة الوظيفية"))

    # موقع العمل الأساسي (ق-62) — الإسناد التفصيلي في SiteAssignment
    primary_site = models.ForeignKey(
        "attendance.WorkSite", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="primary_employments",
        verbose_name=_("موقع العمل"))

    is_gosi_registered = models.BooleanField(
        _("مسجّل في التأمينات"), default=False, db_index=True)
    gosi_establishment_no = models.CharField(
        _("رقم منشأة التأمينات"), max_length=20, blank=True)
    gosi_registered_at = models.DateField(_("تاريخ التسجيل"),
                                          null=True, blank=True)
    gosi_declared_wage = models.DecimalField(
        _("الأجر المسجّل لدى التأمينات"), max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text=_("قد يخالف الأجر المدفوع فعلًا — النظام يعكس الواقع"))

    is_mol_registered = models.BooleanField(
        _("مسجّل في قوى"), default=False, db_index=True,
        help_text=_("نطاقات تحتسب المسجّلين في قوى فقط"))
    mol_contract_no = models.CharField(_("رقم عقد قوى"), max_length=40, blank=True)
    mol_registered_at = models.DateField(_("تاريخ التسجيل في قوى"),
                                         null=True, blank=True)

    include_in_wps = models.BooleanField(
        _("مُدرج في حماية الأجور"), default=False, db_index=True)
    registration_note = models.TextField(
        _("ملاحظة التسجيل"), blank=True,
        help_text=_("سبب عدم التسجيل — للتقارير الداخلية لا للحجب"))

    # ── استثناء تحمّل التأمينات (ق-29) ──
    gosi_borne_by_company = models.BooleanField(
        _("الشركة تتحمل حصته من التأمينات"), null=True, blank=True,
        help_text=_("فارغ = يتبع إعداد الشركة. يُضبط لاستثناء موظف بعينه"))

    # ── البنك ──
    bank_code = models.CharField(_("رمز البنك"), max_length=20, blank=True)
    iban = models.CharField(_("الآيبان"), max_length=24, blank=True)
    payment_method = models.CharField(
        _("طريقة الصرف"), max_length=20,
        choices=PaymentMethod.choices, default=PaymentMethod.BANK)

    class Meta:
        verbose_name = _("ارتباط وظيفي")
        verbose_name_plural = _("الارتباطات الوظيفية")
        ordering = ["employee_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_no"],
                name="uq_employment_no_per_company"),
            models.UniqueConstraint(
                fields=["company", "person"],
                condition=models.Q(status="active"),
                name="uq_active_employment_per_person_company"),
        ]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["person"]),
        ]

    def __str__(self):
        return f"{self.person.display_name} — {self.employee_no}"

    def save(self, *args, **kwargs):
        if self.service_start_date is None:
            self.service_start_date = self.join_date
        super().save(*args, **kwargs)

    @property
    def effective_service_start(self):
        """أساس مكافأة نهاية الخدمة (ق-14)."""
        return self.service_start_date or self.join_date

    @property
    def counts_in_nitaqat(self):
        """
        نطاقات تحتسب المسجّلين في قوى فقط (ق-15).
        سعودي غير مسجّل لا يرفع نسبة التوطين.
        """
        return self.is_mol_registered and self.status == EmploymentStatus.ACTIVE


class SalaryChangeReason(models.TextChoices):
    HIRING = "hiring", _("تعيين")
    ANNUAL_RAISE = "annual_raise", _("علاوة سنوية")
    PROMOTION = "promotion", _("ترقية")
    ADJUSTMENT = "adjustment", _("تعديل")
    TRANSFER = "transfer", _("نقل داخل المجموعة")
    CONTRACT_RENEWAL = "contract_renewal", _("تجديد عقد")


class SalaryStructure(CompanyScopedModel):
    """
    هيكل راتب بتاريخ سريان — لا تعديل في المكان أبدًا.

    كل تغيير سجل جديد. بهذا تستطيع إعادة احتساب أي مسير قديم
    بأرقامه الصحيحة، وتُجيب على «كم كان راتبه في مارس؟» بلا تخمين.
    """

    employment = models.ForeignKey(
        Employment, on_delete=models.CASCADE,
        related_name="salary_structures", verbose_name=_("الارتباط الوظيفي"))
    effective_from = models.DateField(_("سريان من"), db_index=True)
    effective_to = models.DateField(_("سريان إلى"), null=True, blank=True)
    reason = models.CharField(
        _("السبب"), max_length=30, choices=SalaryChangeReason.choices,
        default=SalaryChangeReason.HIRING)
    note = models.TextField(_("ملاحظة"), blank=True)
    approved_by_person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_salary_structures", verbose_name=_("المعتمِد"))

    class Meta:
        verbose_name = _("هيكل راتب")
        verbose_name_plural = _("هياكل الرواتب")
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "effective_from"],
                name="uq_salary_structure_per_date"),
        ]

    def __str__(self):
        return f"{self.employment.employee_no} — من {self.effective_from}"

    @property
    def gross_monthly(self):
        from decimal import Decimal
        return sum(
            (l.amount for l in self.lines.all()
             if l.component.component_type == "earning"),
            Decimal("0"),
        )

    def as_lines(self):
        """[(component, amount), ...] — مدخلات دوال الأجور المشتقة."""
        return [(l.component, l.amount)
                for l in self.lines.select_related("component")]


class SalaryLine(models.Model):
    """بند في هيكل الراتب."""

    structure = models.ForeignKey(
        SalaryStructure, on_delete=models.CASCADE, related_name="lines")
    component = models.ForeignKey(
        "payroll.PayComponent", on_delete=models.PROTECT,
        related_name="salary_lines", verbose_name=_("المكوّن"))
    amount = models.DecimalField(_("المبلغ"), max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = _("بند راتب")
        verbose_name_plural = _("بنود الراتب")
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "component"],
                name="uq_salary_line_per_component"),
        ]

    def __str__(self):
        return f"{self.component.code}: {self.amount}"


# السلف والعهد والوثائق (ق-41)
from apps.employees.models_assets import (  # noqa: E402,F401
    Advance, AdvanceInstallment, AdvanceStatus, Asset, AssetCategory,
    AssetStatus, DocumentType, EmployeeDocument, RepaymentMethod,
)


# توسعة ملف الموظف (ق-63)
from apps.employees.models_profile import (  # noqa: E402,F401
    Dependent, EmergencyContact, JobGrade, JobStep, RelationKind,
)


# التغيير الوظيفي (ق-82)
from apps.employees.models_changes import (  # noqa: E402,F401
    ChangeStatus, ChangeType, JobChange,
)
