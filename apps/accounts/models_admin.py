"""
مستخدمو المنصة — عزل تام عن نظام العملاء (ق-51).

⚠️ لا يرتبط هذا النموذج بأي حساب عميل، ولا يظهر في أدوار
العملاء، ولا يشاركهم الجلسة. من يقف فوق كل الحسابات لا يكون
واحدًا منهم.
"""
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class PlatformRole(models.TextChoices):
    VIEWER = "viewer", _("مطّلع — قراءة فقط")
    SUPPORT = "support", _("دعم — تفعيل وتمديد")
    OWNER = "owner", _("مالك المنصة — كل الصلاحيات")


# ما يستطيعه كل دور — يُفحص في كل نقطة (ق-51)
ROLE_CAPABILITIES = {
    PlatformRole.VIEWER: {
        "accounts.view", "dashboard.view", "invoices.view",
    },
    PlatformRole.SUPPORT: {
        "accounts.view", "dashboard.view", "invoices.view",
        "subscription.activate", "subscription.extend",
        "invoice.mark_paid", "account.impersonate",
    },
    PlatformRole.OWNER: {
        "accounts.view", "dashboard.view", "invoices.view",
        "subscription.activate", "subscription.extend",
        "invoice.mark_paid", "account.impersonate",
        "discounts.manage", "platform.settings", "users.manage",
        "account.write", "account.delete",
    },
}


class PlatformUser(TimeStampedModel):
    """
    مستخدم لوحة المنصة.

    منفصل عن django auth.User تمامًا — فلا تتداخل الجلسات ولا
    تصل ثغرة في مسار عميل إلى هنا.
    """

    username = models.CharField(_("اسم المستخدم"), max_length=60, unique=True)
    email = models.EmailField(_("البريد"), unique=True)
    full_name = models.CharField(_("الاسم"), max_length=150)
    mobile_e164 = models.CharField(_("الجوال"), max_length=20, blank=True)

    password_hash = models.CharField(_("كلمة المرور"), max_length=256)
    role = models.CharField(_("الدور"), max_length=20,
                            choices=PlatformRole.choices,
                            default=PlatformRole.VIEWER)

    # ── الأمان (ق-51) ──
    totp_secret = models.CharField(
        _("سرّ التحقق الثنائي"), max_length=64, blank=True)
    totp_enabled = models.BooleanField(
        _("التحقق الثنائي مفعّل"), default=False,
        help_text=_("إلزامي — الحساب يفتح بيانات كل العملاء"))
    allowed_ips = models.TextField(
        _("عناوين IP المسموحة"), blank=True,
        help_text=_("مفصولة بفاصلة — فارغ يعني بلا قيد"))

    is_active = models.BooleanField(_("نشط"), default=True)
    last_login_at = models.DateTimeField(_("آخر دخول"), null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(_("آخر عنوان"), null=True,
                                                 blank=True)
    failed_attempts = models.PositiveSmallIntegerField(
        _("محاولات فاشلة"), default=0)
    locked_until = models.DateTimeField(_("مقفل حتى"), null=True, blank=True)

    class Meta:
        verbose_name = _("مستخدم منصة")
        verbose_name_plural = _("مستخدمو المنصة")
        ordering = ["username"]

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    # ── كلمة المرور ──
    def set_password(self, raw):
        self.password_hash = make_password(raw)

    def check_password(self, raw):
        return check_password(raw, self.password_hash)

    # ── الصلاحيات ──
    def can(self, capability):
        """هل يملك هذه القدرة؟ يُفحص في كل نقطة."""
        if not self.is_active:
            return False
        return capability in ROLE_CAPABILITIES.get(self.role, set())

    @property
    def capabilities(self):
        return sorted(ROLE_CAPABILITIES.get(self.role, set()))

    # ── القفل بعد المحاولات الفاشلة ──
    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def ip_allowed(self, ip):
        if not self.allowed_ips.strip():
            return True
        allowed = {x.strip() for x in self.allowed_ips.split(",") if x.strip()}
        return ip in allowed


class PlatformSession(TimeStampedModel):
    """
    جلسة لوحة المنصة — كوكي منفصل عن جلسات العملاء (ق-51).
    """

    user = models.ForeignKey(PlatformUser, on_delete=models.CASCADE,
                             related_name="sessions")
    token = models.CharField(_("الرمز"), max_length=128, unique=True,
                             db_index=True)
    ip_address = models.GenericIPAddressField(_("العنوان"), null=True,
                                              blank=True)
    user_agent = models.CharField(_("المتصفح"), max_length=300, blank=True)
    expires_at = models.DateTimeField(_("تنتهي في"))
    revoked_at = models.DateTimeField(_("أُبطلت في"), null=True, blank=True)

    class Meta:
        verbose_name = _("جلسة منصة")
        verbose_name_plural = _("جلسات المنصة")
        ordering = ["-created_at"]

    @property
    def is_valid(self):
        return (self.revoked_at is None
                and self.expires_at > timezone.now()
                and self.user.is_active)


class PlatformAuditLog(TimeStampedModel):
    """
    سجل عمليات السوبر أدمن — منفصل عن سجل عمليات المنشأة (ق-44).

    يُسجَّل هنا كل ما يفعله مستخدم المنصة، ويُسجَّل في سجل العميل
    كذلك ما يمسّ بياناته — فيرى العميل من عدّل حسابه.
    """

    user = models.ForeignKey(PlatformUser, on_delete=models.SET_NULL,
                             null=True, related_name="audit_logs")
    user_name = models.CharField(_("اسم الفاعل"), max_length=150)
    action = models.CharField(_("العملية"), max_length=60, db_index=True)
    target_account_id = models.PositiveIntegerField(
        _("الحساب المستهدف"), null=True, blank=True, db_index=True)
    target_label = models.CharField(_("وصف الهدف"), max_length=200, blank=True)
    detail = models.JSONField(_("التفاصيل"), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_("العنوان"), null=True,
                                              blank=True)
    success = models.BooleanField(_("نجحت"), default=True)

    class Meta:
        verbose_name = _("قيد سجل المنصة")
        verbose_name_plural = _("سجل عمليات المنصة")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["target_account_id", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user_name}: {self.action}"


class ImpersonationSession(TimeStampedModel):
    """
    جلسة انتحال للدعم الفني (ق-51).

    يرى السوبر أدمن ما يراه العميل بالضبط — الشاشة والصلاحيات معًا.
    الجلسة مؤقتة (ساعة)، وكل كتابة تُسجَّل باسمه لا باسم العميل.

    المنطق في apps/accounts/services/platform/impersonation.py
    """

    HOURS = 1      # تنتهي تلقائيًا فلا تُنسى مفتوحة

    platform_user = models.ForeignKey(
        PlatformUser, on_delete=models.CASCADE,
        related_name="impersonations", verbose_name=_("مستخدم المنصة"))
    account_id = models.PositiveIntegerField(_("الحساب"), db_index=True)
    account_label = models.CharField(_("اسم الحساب"), max_length=200)
    company_id = models.PositiveIntegerField(_("الشركة"), null=True,
                                             blank=True)
    as_role = models.CharField(
        _("بدور"), max_length=40, blank=True,
        help_text=_("hr_manager · employee — لتشخيص مشاكل الصلاحيات"))

    token = models.CharField(_("الرمز"), max_length=128, unique=True,
                             db_index=True)
    reason = models.CharField(_("سبب الدخول"), max_length=300, blank=True)
    expires_at = models.DateTimeField(_("تنتهي في"))
    ended_at = models.DateTimeField(_("انتهت في"), null=True, blank=True)
    ip_address = models.GenericIPAddressField(_("العنوان"), null=True,
                                              blank=True)
    writes_count = models.PositiveIntegerField(_("عمليات الكتابة"), default=0)

    class Meta:
        verbose_name = _("جلسة انتحال")
        verbose_name_plural = _("جلسات الانتحال")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account_id", "-created_at"]),
            models.Index(fields=["platform_user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.platform_user.username} → {self.account_label}"

    @property
    def is_active(self):
        return self.ended_at is None and self.expires_at > timezone.now()

    @property
    def minutes_left(self):
        if not self.is_active:
            return 0
        return int((self.expires_at - timezone.now()).total_seconds() / 60)
