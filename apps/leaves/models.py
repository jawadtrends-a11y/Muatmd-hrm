"""
الإجازات والطلبات.

المبدأ (ق-32): كل سياسة إجازة خيار الشركة — الاستحقاق والترحيل
واحتساب العطل. النظام يوفّر الخيارات ولا يفرض.

الإجازة بلا أجر لا تُحتسب غيابًا لكن يُخصم أجر اليوم — الغياب
مخالفة والإجازة بلا أجر حق مأذون.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class AccrualMethod(models.TextChoices):
    MONTHLY = "monthly", _("شهري بالتناسب")
    ANNUAL = "annual", _("دفعة سنوية")
    PER_EVENT = "per_event", _("لكل واقعة")
    NONE = "none", _("بلا استحقاق تلقائي")


class CarryForwardPolicy(models.TextChoices):
    FULL = "full", _("يُرحَّل كاملًا")
    CAPPED = "capped", _("يُرحَّل بحد أقصى")
    EXPIRE = "expire", _("يسقط ما لم يُستخدم")


class HolidayTreatment(models.TextChoices):
    COUNTED = "counted", _("تُحتسب من الرصيد")
    EXTENDS = "extends", _("تُمدَّد الإجازة بعددها")


class GenderRestriction(models.TextChoices):
    ANY = "any", _("الجميع")
    MALE = "male", _("ذكور فقط")
    FEMALE = "female", _("إناث فقط")


class LeaveType(CompanyScopedModel):
    """
    نوع إجازة — بسياساته التي تحددها الشركة (ق-32).

    البذرة تتبع النظام السعودي، والشركة تعدّل كل شيء.
    """

    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("الاسم"), max_length=120)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=120, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=120, blank=True)

    is_paid = models.BooleanField(
        _("مدفوعة"), default=True,
        help_text=_("غير المدفوعة: لا تُحتسب غيابًا لكن يُخصم أجر اليوم"))
    pay_percentage = models.DecimalField(
        _("نسبة الأجر"), max_digits=5, decimal_places=2, default=100,
        help_text=_("للإجازات متدرجة الأجر مثل المرضية"))

    # ── الاستحقاق (ق-32) ──
    accrual_method = models.CharField(
        _("طريقة الاستحقاق"), max_length=20,
        choices=AccrualMethod.choices, default=AccrualMethod.ANNUAL)
    days_per_year = models.DecimalField(
        _("الأيام السنوية (افتراضي)"), max_digits=6, decimal_places=2,
        null=True, blank=True,
        help_text=_("يُستخدم عند غياب استحقاق فردي للموظف (ق-33)"))
    days_after_five_years = models.DecimalField(
        _("الأيام بعد 5 سنوات"), max_digits=6, decimal_places=2,
        null=True, blank=True,
        help_text=_("السنوية ترتفع من 21 إلى 30 بعد 5 سنوات خدمة"))
    days_per_event = models.DecimalField(
        _("أيام الواقعة"), max_digits=6, decimal_places=2,
        null=True, blank=True)

    # ── الترحيل (ق-32) ──
    carry_forward_policy = models.CharField(
        _("سياسة الترحيل"), max_length=20,
        choices=CarryForwardPolicy.choices, default=CarryForwardPolicy.FULL)
    max_carry_forward_days = models.DecimalField(
        _("الحد الأقصى للترحيل"), max_digits=6, decimal_places=2,
        null=True, blank=True)

    # ── احتساب العطل (ق-32) ──
    holiday_treatment = models.CharField(
        _("العطل داخل الإجازة"), max_length=20,
        choices=HolidayTreatment.choices, default=HolidayTreatment.EXTENDS,
        help_text=_("الافتراض: العطل تُمدّد الإجازة ولا تُخصم من الرصيد"))
    weekend_treatment = models.CharField(
        _("الراحة الأسبوعية داخل الإجازة"), max_length=20,
        choices=HolidayTreatment.choices, default=HolidayTreatment.COUNTED,
        help_text=_("الافتراض: الراحة الأسبوعية تُحتسب من الرصيد"))

    # ق-34: حد نظامي صارم لكل نوع — أقل منه مخالفة تُسقط حق الموظف
    statutory_min_days = models.DecimalField(
        _("الحد النظامي الأدنى"), max_digits=6, decimal_places=2,
        null=True, blank=True,
        help_text=_("السنوية 21، والحج 10 — يُمنع النزول عنه"))

    # ── الشروط ──
    gender_restriction = models.CharField(
        _("قيد الجنس"), max_length=10,
        choices=GenderRestriction.choices, default=GenderRestriction.ANY)
    muslim_only = models.BooleanField(
        _("للمسلمين فقط"), default=False, help_text=_("مثل إجازة الحج"))
    min_service_months = models.PositiveSmallIntegerField(
        _("أقل مدة خدمة (أشهر)"), default=0)
    once_per_service = models.BooleanField(
        _("مرة واحدة طوال الخدمة"), default=False)
    requires_attachment = models.BooleanField(
        _("يتطلب مرفقًا"), default=False)
    max_consecutive_days = models.PositiveSmallIntegerField(
        _("أقصى مدة متصلة"), null=True, blank=True)

    is_system = models.BooleanField(_("نوع نظامي"), default=False)
    is_active = models.BooleanField(_("نشط"), default=True)
    display_order = models.IntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("نوع إجازة")
        verbose_name_plural = _("أنواع الإجازات")
        ordering = ["display_order", "code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_leavetype_code_per_company"),
        ]

    def __str__(self):
        return self.name_ar


class LeaveTier(models.Model):
    """
    شريحة أجر داخل نوع الإجازة.

    المرضية: 30 يومًا بأجر كامل، ثم 60 بثلاثة أرباع، ثم 30 بلا أجر.
    """

    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE,
                                   related_name="tiers")
    from_day = models.PositiveSmallIntegerField(_("من اليوم"))
    to_day = models.PositiveSmallIntegerField(_("إلى اليوم"),
                                              null=True, blank=True)
    pay_percentage = models.DecimalField(
        _("نسبة الأجر"), max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = _("شريحة إجازة")
        verbose_name_plural = _("شرائح الإجازات")
        ordering = ["leave_type", "from_day"]
        constraints = [
            models.UniqueConstraint(fields=["leave_type", "from_day"],
                                    name="uq_leave_tier_start"),
        ]

    def __str__(self):
        upper = self.to_day or "∞"
        return f"{self.from_day}–{upper}: {self.pay_percentage}%"


class LeaveBalance(CompanyScopedModel):
    """رصيد إجازة لموظف في سنة."""

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="leave_balances", verbose_name=_("الموظف"))
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT,
                                   related_name="balances")
    year = models.PositiveSmallIntegerField(_("السنة"))

    opening_balance = models.DecimalField(
        _("الرصيد الافتتاحي"), max_digits=7, decimal_places=2, default=0)
    accrued = models.DecimalField(_("المستحق"), max_digits=7,
                                  decimal_places=2, default=0)
    consumed = models.DecimalField(_("المستهلك"), max_digits=7,
                                   decimal_places=2, default=0)
    adjusted = models.DecimalField(_("التسويات"), max_digits=7,
                                   decimal_places=2, default=0)
    carried_forward = models.DecimalField(
        _("المُرحَّل للسنة التالية"), max_digits=7, decimal_places=2, default=0)
    last_accrual_date = models.DateField(_("آخر استحقاق"),
                                         null=True, blank=True)

    class Meta:
        verbose_name = _("رصيد إجازة")
        verbose_name_plural = _("أرصدة الإجازات")
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "leave_type", "year"],
                name="uq_leave_balance"),
        ]

    def __str__(self):
        return f"{self.employment.employee_no} — {self.leave_type.code} {self.year}"

    @property
    def available(self):
        return (self.opening_balance + self.accrued
                + self.adjusted - self.consumed)


class LeaveEntitlement(CompanyScopedModel):
    """
    استحقاق إجازة لموظف بعينه (ق-33).

    الرصيد يُعيَّن لكل موظف حسب عقده بأي رقم — 21 أو 25 أو 30 أو
    أعلى. ليس خيارًا بين رقمين.

    ق-34: الحد النظامي **قيد صارم لا تنبيه**. أقل من الحد الأدنى
    لنوع الإجازة مخالفة قاطعة تُسقط حقًا للموظف، والنظام يمنعها.
    هذا استثناء مبرَّر على ق-20 (نحفظ مدخلات الشركة): نحفظ ما
    أدخلته إلا ما كان إسقاطًا لحق نظامي.
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="leave_entitlements", verbose_name=_("الموظف"))
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE,
                                   related_name="entitlements")
    days_per_year = models.DecimalField(
        _("الأيام السنوية"), max_digits=6, decimal_places=2,
        help_text=_("أي رقم حسب العقد. يُمنع النزول عن الحد النظامي"))
    effective_from = models.DateField(_("سريان من"))
    effective_to = models.DateField(_("سريان إلى"), null=True, blank=True)
    note = models.TextField(_("ملاحظة"), blank=True,
                            help_text=_("مرجع بند العقد مثلًا"))

    class Meta:
        verbose_name = _("استحقاق إجازة")
        verbose_name_plural = _("استحقاقات الإجازات")
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "leave_type", "effective_from"],
                name="uq_leave_entitlement"),
            models.CheckConstraint(
                condition=models.Q(days_per_year__gt=0),
                name="chk_entitlement_positive"),
        ]

    def __str__(self):
        return (f"{self.employment.employee_no} — {self.leave_type.code}: "
                f"{self.days_per_year} يومًا")

    def clean(self):
        """
        ق-34: المنع الصارم. الفحص هنا وفي طبقة الخدمة معًا —
        قيد قاعدة البيانات لا يستطيع قراءة الحد من جدول آخر.
        """
        from django.core.exceptions import ValidationError
        minimum = self.leave_type.statutory_min_days
        if minimum is not None and self.days_per_year < minimum:
            raise ValidationError({
                "days_per_year": (
                    f"الحد النظامي الأدنى لـ{self.leave_type.name_ar} هو "
                    f"{minimum} يومًا. أقل منه مخالفة تُسقط حق الموظف."
                )
            })

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["account", "company"])
        super().save(*args, **kwargs)


# ══════════════════ الطلبات الموحّدة ══════════════════

class RequestType(models.TextChoices):
    LEAVE = "leave", _("إجازة")
    ADVANCE = "advance", _("سلفة")
    TICKET = "ticket", _("تذكرة سفر")
    ASSET = "asset", _("عهدة")
    PERMISSION = "permission", _("استئذان")
    CERTIFICATE = "certificate", _("شهادة أو خطاب")
    RESIGNATION = "resignation", _("استقالة")
    OVERTIME = "overtime", _("عمل إضافي")
    ATTENDANCE_FIX = "attendance_fix", _("تصحيح بصمة")
    REMOTE_WORK = "remote_work", _("عمل عن بُعد")
    BUSINESS_TRIP = "business_trip", _("رحلة عمل")
    PROFILE_UPDATE = "profile_update", _("تعديل بيانات")


class RequestStatus(models.TextChoices):
    DRAFT = "draft", _("مسودة")
    PENDING = "pending", _("قيد الاعتماد")
    APPROVED = "approved", _("معتمد")
    REJECTED = "rejected", _("مرفوض")
    CANCELLED = "cancelled", _("ملغى")
    WITHDRAWN = "withdrawn", _("مسحوب")


class Request(CompanyScopedModel):
    """
    جدول الطلبات الموحّد — إجازة وسلفة وتذكرة وعهدة واستئذان.

    جدول واحد لكل الأنواع: لا تكرار للمسارات، والاعتماد يمر بسلسلة
    واحدة مهما اختلف النوع.
    """

    request_no = models.CharField(_("رقم الطلب"), max_length=30)
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="requests", verbose_name=_("مقدّم الطلب"))
    request_type = models.CharField(_("النوع"), max_length=40,
                                    choices=RequestType.choices, db_index=True)
    status = models.CharField(_("الحالة"), max_length=20,
                              choices=RequestStatus.choices,
                              default=RequestStatus.DRAFT, db_index=True)

    payload = models.JSONField(_("تفاصيل الطلب"), default=dict)
    note = models.TextField(_("ملاحظة مقدّم الطلب"), blank=True)
    attachment_url = models.CharField(_("المرفق"), max_length=500, blank=True)

    channel = models.CharField(
        _("قناة التقديم"), max_length=20, default="web",
        choices=[("web", _("المتصفح")), ("mobile", _("الجوال")),
                 ("whatsapp", _("واتساب"))])

    submitted_at = models.DateTimeField(_("وقت التقديم"), null=True, blank=True)
    closed_at = models.DateTimeField(_("وقت الإغلاق"), null=True, blank=True)
    current_step = models.PositiveSmallIntegerField(
        _("درجة الاعتماد الحالية"), default=0)

    class Meta:
        verbose_name = _("طلب")
        verbose_name_plural = _("الطلبات")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "request_no"],
                                    name="uq_request_no_per_company"),
        ]
        indexes = [
            models.Index(fields=["company", "status", "request_type"]),
            models.Index(fields=["employment", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.request_no} — {self.get_request_type_display()}"


class ApproverType(models.TextChoices):
    DIRECT_MANAGER = "direct_manager", _("المدير المباشر")
    DEPARTMENT_HEAD = "department_head", _("مدير الإدارة")
    ROLE = "role", _("دور محدد")
    SPECIFIC_PERSON = "specific_person", _("شخص محدد")


class ApprovalChain(CompanyScopedModel):
    """
    سلسلة اعتماد — سلسلة افتراضية جاهزة تعدّلها الشركة (ق-9).

    condition_json يسمح بسلاسل مشروطة بلا كود: «إجازة تتجاوز 5 أيام
    تحتاج درجتين»، أو «سلفة فوق 5000 تحتاج المدير العام».
    """

    request_type = models.CharField(_("نوع الطلب"), max_length=40,
                                    choices=RequestType.choices, db_index=True)
    name_ar = models.CharField(_("اسم السلسلة"), max_length=120)
    condition_json = models.JSONField(
        _("الشرط"), default=dict, blank=True,
        help_text=_('مثال: {"days_gt": 5} أو {"amount_gt": 5000}'))
    priority = models.IntegerField(
        _("الأولوية"), default=0,
        help_text=_("الأعلى يُفحص أولًا — للسلاسل المشروطة"))
    is_active = models.BooleanField(_("نشطة"), default=True)

    class Meta:
        verbose_name = _("سلسلة اعتماد")
        verbose_name_plural = _("سلاسل الاعتماد")
        ordering = ["request_type", "-priority"]

    def __str__(self):
        return f"{self.get_request_type_display()} — {self.name_ar}"


class ApprovalStep(models.Model):
    """درجة في سلسلة الاعتماد."""

    chain = models.ForeignKey(ApprovalChain, on_delete=models.CASCADE,
                              related_name="steps")
    step_order = models.PositiveSmallIntegerField(_("الترتيب"))
    approver_type = models.CharField(_("نوع المعتمِد"), max_length=30,
                                     choices=ApproverType.choices)
    approver_role_code = models.CharField(
        _("رمز الدور"), max_length=40, blank=True,
        help_text=_("عند approver_type=role"))
    approver_person = models.ForeignKey(
        "employees.Person", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", help_text=_("عند approver_type=specific_person"))
    is_mandatory = models.BooleanField(_("إلزامية"), default=True)
    sla_hours = models.PositiveSmallIntegerField(
        _("مهلة الاعتماد (ساعات)"), null=True, blank=True,
        help_text=_("التجاوز يُطلق حدث تصعيد"))

    class Meta:
        verbose_name = _("درجة اعتماد")
        verbose_name_plural = _("درجات الاعتماد")
        ordering = ["chain", "step_order"]
        constraints = [
            models.UniqueConstraint(fields=["chain", "step_order"],
                                    name="uq_approval_step_order"),
        ]

    def __str__(self):
        return f"{self.chain.name_ar} #{self.step_order}"


class ApprovalDecision(models.TextChoices):
    APPROVED = "approved", _("معتمد")
    REJECTED = "rejected", _("مرفوض")
    DELEGATED = "delegated", _("مُحوَّل")


class RequestApproval(CompanyScopedModel):
    """
    سجل اعتماد — من اعتمد ومتى وبأي قناة.
    سجل تدقيق كامل: لا يُحذف ولا يُعدَّل بعد القرار.
    """

    request = models.ForeignKey(Request, on_delete=models.CASCADE,
                                related_name="approvals")
    step_order = models.PositiveSmallIntegerField(_("الدرجة"))
    approver_employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="approvals_given", verbose_name=_("المعتمِد"))
    decision = models.CharField(_("القرار"), max_length=20,
                                choices=ApprovalDecision.choices, blank=True)
    decided_at = models.DateTimeField(_("وقت القرار"), null=True, blank=True)
    comment = models.TextField(_("التعليق"), blank=True)
    acted_via = models.CharField(_("القناة"), max_length=20, default="web")
    due_at = models.DateTimeField(_("موعد الاستحقاق"), null=True, blank=True)
    escalated = models.BooleanField(_("صُعِّد"), default=False)

    class Meta:
        verbose_name = _("اعتماد طلب")
        verbose_name_plural = _("اعتمادات الطلبات")
        ordering = ["request", "step_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "step_order", "approver_employment"],
                name="uq_approval_per_step_approver"),
        ]

    def __str__(self):
        return f"{self.request.request_no} #{self.step_order}"
