"""
الفوترة والاشتراكات (ق-47).

الفاتورة الضريبية تصدر من «محاسبة معتمد» (ق-12) — هذا النظام
يحتسب المستحق ويقبض ويُبلغ المحاسبي.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel, TimeStampedModel


class BillingCycle(models.TextChoices):
    MONTHLY = "monthly", _("شهري")
    ANNUAL = "annual", _("سنوي")


class DiscountKind(models.TextChoices):
    PERCENT = "percent", _("نسبة مئوية")
    AMOUNT = "amount", _("مبلغ ثابت")


class DiscountScope(models.TextChoices):
    ONE_TIME = "one_time", _("مرة واحدة على فاتورة")
    RECURRING = "recurring", _("سعر خاص يستمر مع التجديد")
    COUPON = "coupon", _("كود خصم يُدخله العميل")


class Discount(TimeStampedModel):
    """
    خصم — بثلاثة أنواع (ق-47).

    على مستوى المنصة لا الحساب: السوبر أدمن ينشئه ويربطه بحساب
    أو يتركه كودًا عامًا.
    """

    code = models.CharField(
        _("الكود"), max_length=40, unique=True,
        help_text=_("يُدخله العميل عند الاشتراك — للنوع coupon"))
    name_ar = models.CharField(_("الاسم"), max_length=150)
    scope = models.CharField(_("النطاق"), max_length=20,
                             choices=DiscountScope.choices)
    kind = models.CharField(_("النوع"), max_length=20,
                            choices=DiscountKind.choices,
                            default=DiscountKind.PERCENT)
    value = models.DecimalField(_("القيمة"), max_digits=10, decimal_places=2,
                                help_text=_("نسبة أو مبلغ حسب النوع"))

    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE, null=True, blank=True,
        related_name="discounts", verbose_name=_("مخصص لحساب"),
        help_text=_("فارغ = متاح للجميع"))
    applies_to_cycle = models.CharField(
        _("يسري على الدورة"), max_length=20,
        choices=BillingCycle.choices, blank=True,
        help_text=_("فارغ = الدورتان"))
    covers_setup_fee = models.BooleanField(
        _("يشمل رسوم الإعداد"), default=False)

    valid_from = models.DateField(_("صالح من"), null=True, blank=True)
    valid_until = models.DateField(_("صالح حتى"), null=True, blank=True)
    max_uses = models.PositiveIntegerField(_("أقصى استخدام"), null=True,
                                           blank=True)
    used_count = models.PositiveIntegerField(_("عدد الاستخدام"), default=0)
    is_active = models.BooleanField(_("نشط"), default=True)
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("خصم")
        verbose_name_plural = _("الخصومات")
        ordering = ["-created_at"]

    def __str__(self):
        symbol = "%" if self.kind == DiscountKind.PERCENT else "ريال"
        return f"{self.name_ar} ({self.value}{symbol})"

    def is_valid_on(self, day):
        if not self.is_active:
            return False, "الخصم غير نشط"
        if self.valid_from and day < self.valid_from:
            return False, f"يبدأ سريانه في {self.valid_from}"
        if self.valid_until and day > self.valid_until:
            return False, f"انتهى سريانه في {self.valid_until}"
        if self.max_uses and self.used_count >= self.max_uses:
            return False, "استُنفد عدد مرات الاستخدام"
        return True, ""


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", _("مسودة")
    ISSUED = "issued", _("صادرة")
    PAID = "paid", _("مدفوعة")
    OVERDUE = "overdue", _("متأخرة")
    CANCELLED = "cancelled", _("ملغاة")
    REFUNDED = "refunded", _("مستردة")


class Invoice(AccountScopedModel):
    """
    فاتورة اشتراك.

    ⚠️ ليست فاتورة ضريبية — تلك تصدر من «محاسبة معتمد» (ق-12).
    هذه سجل المستحق والمدفوع في هذا النظام.
    """

    invoice_no = models.CharField(_("رقم الفاتورة"), max_length=30,
                                  unique=True)
    period_start = models.DateField(_("بداية الفترة"))
    period_end = models.DateField(_("نهاية الفترة"))
    cycle = models.CharField(_("الدورة"), max_length=20,
                             choices=BillingCycle.choices)

    subtotal = models.DecimalField(_("المجموع قبل الخصم"), max_digits=12,
                                   decimal_places=2, default=0)
    setup_fee = models.DecimalField(
        _("رسوم الإعداد"), max_digits=12, decimal_places=2, default=0,
        help_text=_("مرة واحدة في حياة الحساب — سطر منفصل (ق-47)"))
    discount_amount = models.DecimalField(_("قيمة الخصم"), max_digits=12,
                                          decimal_places=2, default=0)
    discount = models.ForeignKey(
        Discount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="invoices", verbose_name=_("الخصم المطبَّق"))
    total = models.DecimalField(_("الإجمالي المستحق"), max_digits=12,
                                decimal_places=2, default=0)

    status = models.CharField(_("الحالة"), max_length=20,
                              choices=InvoiceStatus.choices,
                              default=InvoiceStatus.DRAFT, db_index=True)
    issued_at = models.DateTimeField(_("تاريخ الإصدار"), null=True, blank=True)
    due_date = models.DateField(_("تاريخ الاستحقاق"), null=True, blank=True)
    paid_at = models.DateTimeField(_("تاريخ السداد"), null=True, blank=True)

    # ── الربط بالمحاسبي (ق-12) ──
    accounting_invoice_id = models.CharField(
        _("رقم الفاتورة في المحاسبي"), max_length=60, blank=True,
        help_text=_("الفاتورة الضريبية تصدر من محاسبة معتمد"))
    accounting_synced_at = models.DateTimeField(
        _("وقت المزامنة"), null=True, blank=True)

    headcount = models.PositiveIntegerField(
        _("عدد الموظفين المحتسب"), default=0,
        help_text=_("ذروة الفترة — أساس الاحتساب"))
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("فاتورة اشتراك")
        verbose_name_plural = _("فواتير الاشتراكات")
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["account", "status"]),
            models.Index(fields=["status", "due_date"]),
        ]

    def __str__(self):
        return f"{self.invoice_no} — {self.total}"

    @property
    def is_overdue(self):
        from datetime import date
        return (self.status == InvoiceStatus.ISSUED
                and self.due_date and self.due_date < date.today())


class InvoiceLine(models.Model):
    """سطر في الفاتورة — الاشتراك ورسوم الإعداد منفصلان (ق-47)."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE,
                                related_name="lines")
    description_ar = models.CharField(_("البيان"), max_length=250)
    quantity = models.DecimalField(_("الكمية"), max_digits=10,
                                   decimal_places=2, default=1)
    unit_price = models.DecimalField(_("سعر الوحدة"), max_digits=12,
                                     decimal_places=2)
    amount = models.DecimalField(_("المبلغ"), max_digits=12,
                                 decimal_places=2)
    is_setup_fee = models.BooleanField(_("رسوم إعداد"), default=False)
    note_ar = models.CharField(_("ملاحظة"), max_length=250, blank=True)
    display_order = models.IntegerField(_("الترتيب"), default=0)

    class Meta:
        verbose_name = _("سطر فاتورة")
        verbose_name_plural = _("سطور الفواتير")
        ordering = ["invoice", "display_order"]

    def __str__(self):
        return f"{self.description_ar}: {self.amount}"


# ══════════════════ المدفوعات ══════════════════

class PaymentStatus(models.TextChoices):
    INITIATED = "initiated", _("قيد التنفيذ")
    PAID = "paid", _("مدفوعة")
    FAILED = "failed", _("فاشلة")
    REFUNDED = "refunded", _("مستردة")
    VOIDED = "voided", _("ملغاة")


class Payment(AccountScopedModel):
    """
    عملية دفع عبر ميسر.

    لا تُحفظ بيانات البطاقة أبدًا — الرمز فقط، وميسر تحتفظ بالباقي.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT,
                                related_name="payments",
                                verbose_name=_("الفاتورة"))
    amount = models.DecimalField(_("المبلغ"), max_digits=12,
                                 decimal_places=2)
    currency = models.CharField(_("العملة"), max_length=3, default="SAR")

    # ── ميسر ──
    moyasar_payment_id = models.CharField(
        _("معرّف ميسر"), max_length=80, blank=True, db_index=True)
    moyasar_status = models.CharField(_("حالة ميسر"), max_length=40, blank=True)
    source_type = models.CharField(
        _("وسيلة الدفع"), max_length=30, blank=True,
        help_text=_("creditcard · applepay · stcpay · token"))
    card_brand = models.CharField(_("نوع البطاقة"), max_length=20, blank=True)
    card_last_four = models.CharField(_("آخر أربعة"), max_length=4, blank=True)

    status = models.CharField(_("الحالة"), max_length=20,
                              choices=PaymentStatus.choices,
                              default=PaymentStatus.INITIATED, db_index=True)
    failure_message = models.CharField(_("سبب الفشل"), max_length=300,
                                       blank=True)
    is_recurring = models.BooleanField(
        _("شحن تلقائي"), default=False,
        help_text=_("تم بالرمز المحفوظ بلا تدخّل العميل"))

    paid_at = models.DateTimeField(_("وقت الدفع"), null=True, blank=True)
    raw_response = models.JSONField(_("رد ميسر"), default=dict, blank=True)

    class Meta:
        verbose_name = _("عملية دفع")
        verbose_name_plural = _("المدفوعات")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["account", "status"])]

    def __str__(self):
        return f"{self.amount} {self.currency} — {self.get_status_display()}"


class SavedCard(AccountScopedModel):
    """
    بطاقة محفوظة كرمز لدى ميسر — للتجديد التلقائي.

    ⚠️ لا رقم بطاقة هنا ولا CVC. الرمز وحده، وميسر تحتفظ بالباقي.
    """

    moyasar_token = models.CharField(_("رمز ميسر"), max_length=120,
                                     unique=True)
    brand = models.CharField(_("النوع"), max_length=20, blank=True)
    last_four = models.CharField(_("آخر أربعة"), max_length=4, blank=True)
    holder_name = models.CharField(_("اسم حامل البطاقة"), max_length=150,
                                   blank=True)
    exp_month = models.CharField(_("شهر الانتهاء"), max_length=2, blank=True)
    exp_year = models.CharField(_("سنة الانتهاء"), max_length=4, blank=True)

    is_default = models.BooleanField(_("الافتراضية"), default=True)
    is_active = models.BooleanField(_("نشطة"), default=True)
    last_used_at = models.DateTimeField(_("آخر استخدام"), null=True,
                                        blank=True)

    class Meta:
        verbose_name = _("بطاقة محفوظة")
        verbose_name_plural = _("البطاقات المحفوظة")
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.brand} •••• {self.last_four}"


# ══════════════════ الاشتراك ══════════════════

class SubscriptionState(models.TextChoices):
    TRIAL = "trial", _("تجربة مجانية")
    ACTIVE = "active", _("نشط")
    READ_ONLY = "read_only", _("للقراءة فقط")
    PAST_DUE = "past_due", _("متأخر السداد")
    CANCELLED = "cancelled", _("ملغى")


class AccountSubscription(AccountScopedModel):
    """
    اشتراك الحساب (ق-47).

    التجربة سبعة أيام بخمسة موظفين، وبعدها قراءة فقط بلا حد زمني
    حتى يشترك — لا يُقفل ولا يُحذف.
    """

    TRIAL_DAYS = 7
    TRIAL_MAX_EMPLOYEES = 5

    plan = models.ForeignKey(
        "accounts.Plan", on_delete=models.PROTECT, null=True, blank=True,
        related_name="account_subscriptions", verbose_name=_("الباقة"))
    cycle = models.CharField(_("الدورة"), max_length=20,
                             choices=BillingCycle.choices,
                             default=BillingCycle.MONTHLY)
    state = models.CharField(_("الحالة"), max_length=20,
                             choices=SubscriptionState.choices,
                             default=SubscriptionState.TRIAL, db_index=True)

    trial_started_at = models.DateField(_("بداية التجربة"), null=True,
                                        blank=True)
    trial_ends_at = models.DateField(_("نهاية التجربة"), null=True,
                                     blank=True)

    current_period_start = models.DateField(_("بداية الفترة"), null=True,
                                            blank=True)
    current_period_end = models.DateField(_("نهاية الفترة"), null=True,
                                          blank=True)
    next_billing_date = models.DateField(_("تاريخ التجديد"), null=True,
                                         blank=True, db_index=True)

    auto_renew = models.BooleanField(_("تجديد تلقائي"), default=True)
    saved_card = models.ForeignKey(
        SavedCard, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subscriptions", verbose_name=_("بطاقة التجديد"))

    setup_fee_amount = models.DecimalField(
        _("رسوم الإعداد"), max_digits=12, decimal_places=2, default=0,
        help_text=_("تُحصَّل مرة واحدة في حياة الحساب"))
    setup_fee_charged = models.BooleanField(_("حُصّلت رسوم الإعداد"),
                                            default=False)
    custom_price = models.DecimalField(
        _("سعر خاص"), max_digits=12, decimal_places=2, null=True, blank=True,
        help_text=_("يتجاوز سعر الباقة — يستمر مع التجديد"))
    recurring_discount = models.ForeignKey(
        Discount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subscriptions", verbose_name=_("خصم مستمر"))

    cancelled_at = models.DateTimeField(_("تاريخ الإلغاء"), null=True,
                                        blank=True)
    cancellation_reason = models.TextField(_("سبب الإلغاء"), blank=True)

    class Meta:
        verbose_name = _("اشتراك حساب")
        verbose_name_plural = _("اشتراكات الحسابات")
        constraints = [
            models.UniqueConstraint(fields=["account"],
                                    name="uq_subscription_per_account"),
        ]

    def __str__(self):
        return f"{self.account_id} — {self.get_state_display()}"

    @property
    def is_writable(self):
        """القراءة فقط بعد انتهاء التجربة (ق-47)."""
        return self.state in (SubscriptionState.TRIAL,
                              SubscriptionState.ACTIVE,
                              SubscriptionState.PAST_DUE)

    @property
    def employee_limit(self):
        """التجربة محدودة بخمسة موظفين."""
        if self.state == SubscriptionState.TRIAL:
            return self.TRIAL_MAX_EMPLOYEES
        return None

    @property
    def trial_days_left(self):
        from datetime import date
        if self.state != SubscriptionState.TRIAL or not self.trial_ends_at:
            return None
        return max(0, (self.trial_ends_at - date.today()).days)
