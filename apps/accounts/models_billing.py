"""
الباقات والاشتراكات والفوترة.

قرارات المالك (الوثيقة المعمارية 3):
  • الاشتراك لكل شركة لا لكل حساب — شركتان تحت مالك واحد قد تكونان
    على باقتين مختلفتين.
  • التسعير لكل موظف حسب الباقة، بشرائح حجم اختيارية.
  • أساس الفوترة: ذروة عدد الموظفين خلال الفترة (غير قابل للتحايل).
  • الموظف في شركتين يُحتسب مرتين.
  • الإيقاف لا يمنع تصدير البيانات أبدًا.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ValueType(models.TextChoices):
    BOOL = "bool", _("نعم/لا")
    INT  = "int",  _("حد رقمي")
    TEXT = "text", _("نص")


class Feature(models.Model):
    """سجل المزايا — مصدر الحقيقة الوحيد لكل ميزة في النظام."""

    feature_key = models.CharField(_("المفتاح"), max_length=60, unique=True)
    module      = models.CharField(_("الوحدة"), max_length=40)
    name_ar     = models.CharField(_("الاسم"), max_length=150)
    name_en     = models.CharField(_("الاسم بالإنجليزية"), max_length=150, blank=True)
    description_ar = models.TextField(_("الوصف"), blank=True)
    value_type  = models.CharField(_("نوع القيمة"), max_length=10,
                                   choices=ValueType.choices, default=ValueType.BOOL)
    is_core     = models.BooleanField(_("ميزة أساسية"), default=False,
                                      help_text=_("متاحة لكل الباقات، لا تُطفأ"))
    sort_order  = models.IntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("ميزة")
        verbose_name_plural = _("المزايا")
        ordering = ["module", "sort_order"]

    def __str__(self):
        return self.name_ar


class Plan(models.Model):
    """باقة — تُشترى لكل شركة على حدة."""

    code       = models.CharField(_("الرمز"), max_length=40, unique=True)
    name_ar    = models.CharField(_("الاسم"), max_length=120)
    name_en    = models.CharField(_("الاسم بالإنجليزية"), max_length=120, blank=True)
    tier_order = models.PositiveSmallIntegerField(_("المستوى"), default=1,
                                                  help_text=_("للترقية والتنزيل"))
    base_fee_monthly = models.DecimalField(_("الرسم الثابت الشهري"),
                                           max_digits=12, decimal_places=2, default=0)
    min_billable_employees = models.PositiveSmallIntegerField(
        _("الحد الأدنى للفوترة"), default=1)
    max_employees = models.PositiveIntegerField(_("الحد الأقصى للموظفين"),
                                                null=True, blank=True)
    trial_days = models.PositiveSmallIntegerField(_("أيام التجربة"), default=14)
    is_public  = models.BooleanField(_("معروضة للعملاء"), default=True)
    is_active  = models.BooleanField(_("مفعّلة"), default=True)

    class Meta:
        verbose_name = _("باقة")
        verbose_name_plural = _("الباقات")
        ordering = ["tier_order"]

    def __str__(self):
        return self.name_ar


class PlanPriceTier(models.Model):
    """شريحة سعر لكل موظف — تسمح بخصم الحجم بلا تغيير كود."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE,
                             related_name="price_tiers", verbose_name=_("الباقة"))
    from_employees = models.PositiveIntegerField(_("من عدد"))
    to_employees   = models.PositiveIntegerField(_("إلى عدد"), null=True, blank=True,
                                                 help_text=_("فارغ = فأكثر"))
    price_per_employee_monthly = models.DecimalField(
        _("السعر الشهري لكل موظف"), max_digits=10, decimal_places=2)
    price_per_employee_yearly = models.DecimalField(
        _("السعر السنوي لكل موظف"), max_digits=10, decimal_places=2,
        null=True, blank=True)
    currency = models.CharField(_("العملة"), max_length=3, default="SAR")

    class Meta:
        verbose_name = _("شريحة سعر")
        verbose_name_plural = _("شرائح الأسعار")
        ordering = ["plan", "from_employees"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "from_employees"],
                                    name="uq_plan_tier_start"),
        ]

    def __str__(self):
        upper = self.to_employees or "∞"
        return f"{self.plan.code} [{self.from_employees}–{upper}]"


class PlanFeature(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="features")
    feature_key = models.CharField(max_length=60)
    value = models.CharField(max_length=255, default="true",
                             help_text=_("true أو رقم حدّ"))

    class Meta:
        verbose_name = _("ميزة باقة")
        verbose_name_plural = _("مزايا الباقات")
        constraints = [
            models.UniqueConstraint(fields=["plan", "feature_key"],
                                    name="uq_plan_feature"),
        ]

    def __str__(self):
        return f"{self.plan.code}: {self.feature_key}={self.value}"


class SubscriptionStatus(models.TextChoices):
    TRIAL     = "trial",     _("تجريبي")
    ACTIVE    = "active",    _("نشط")
    PAST_DUE  = "past_due",  _("متأخر السداد")
    GRACE     = "grace",     _("فترة سماح")
    SUSPENDED = "suspended", _("موقوف")
    CANCELLED = "cancelled", _("ملغى")


class BillingCycle(models.TextChoices):
    MONTHLY = "monthly", _("شهري")
    YEARLY  = "yearly",  _("سنوي")


class CompanySubscription(CompanyScopedModel):
    """
    اشتراك شركة — لكل شركة باقتها وعدد موظفيها.

    يرث account و company والطوابع الزمنية من CompanyScopedModel،
    فيبقى العزل متسقًا مع بقية النظام (حارس المعمارية يفرض هذا).
    """

    plan    = models.ForeignKey(Plan, on_delete=models.PROTECT,
                                related_name="subscriptions")
    billing_cycle = models.CharField(_("دورة الفوترة"), max_length=10,
                                     choices=BillingCycle.choices,
                                     default=BillingCycle.MONTHLY)
    status = models.CharField(_("الحالة"), max_length=20,
                              choices=SubscriptionStatus.choices,
                              default=SubscriptionStatus.TRIAL, db_index=True)
    starts_on = models.DateField(_("تاريخ البدء"))
    current_period_start = models.DateField(_("بداية الفترة الحالية"))
    current_period_end   = models.DateField(_("نهاية الفترة الحالية"))
    trial_ends_on = models.DateField(_("انتهاء التجربة"), null=True, blank=True)
    grace_ends_on = models.DateField(_("انتهاء فترة السماح"), null=True, blank=True)
    auto_renew = models.BooleanField(_("تجديد تلقائي"), default=True)
    price_override_per_employee = models.DecimalField(
        _("سعر تفاوضي لكل موظف"), max_digits=10, decimal_places=2,
        null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = _("اشتراك")
        verbose_name_plural = _("الاشتراكات")
        constraints = [
            models.UniqueConstraint(
                fields=["company"],
                condition=models.Q(status__in=["trial", "active",
                                               "past_due", "grace"]),
                name="uq_active_subscription_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.company.legal_name_ar} — {self.plan.name_ar}"

    @property
    def allows_writes(self):
        """الإيقاف يمنع الكتابة لا القراءة والتصدير."""
        return self.status in {SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE,
                               SubscriptionStatus.PAST_DUE, SubscriptionStatus.GRACE}

    @property
    def allows_payroll(self):
        """فترة السماح توقف الرواتب قبل غيرها."""
        return self.status in {SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE,
                               SubscriptionStatus.PAST_DUE}


class CompanyHeadcountDaily(CompanyScopedModel):
    """لقطة يومية — أساس الفوترة بالذروة."""

    snapshot_date = models.DateField(_("التاريخ"), db_index=True)
    active_employments   = models.PositiveIntegerField(_("الارتباطات النشطة"), default=0)
    billable_employments = models.PositiveIntegerField(_("المُفوترة"), default=0)

    class Meta:
        verbose_name = _("لقطة عدد الموظفين")
        verbose_name_plural = _("لقطات عدد الموظفين")
        constraints = [
            models.UniqueConstraint(fields=["company", "snapshot_date"],
                                    name="uq_headcount_per_day"),
        ]
