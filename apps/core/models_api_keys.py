"""
مفاتيح API للعملاء (ق-151).

**العميل يُنشئ مفتاحًا فيقرأ به بياناته برمجيًّا** — موظفين
وحضورًا ومسيرات.

⚠️ **والمفتاح يُعرض مرّةً ويُخزَّن مجزّأً**: فمن يقرأ القاعدة لا
ينتحل عميلًا (كأجهزة البصمة ق-٩٤).

⚠️⚠️ **والمفتاح لشركةٍ واحدة لا للحساب كلّه**: فحسابٌ بثلاث شركات
ومفتاحٌ يقرأ الثلاث **تسريبٌ لا تكامل** (قرار جواد).

⚠️ **والقراءة أوّلًا**: فالكتابة خطؤها يُفسد بيانات، وتُفتح حين
تُطلب.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class ApiScope(models.TextChoices):
    """
    ⚠️ **نطاقاتٌ محدّدة لا مفتاحٌ يقرأ كل شيء**.

    فمفتاحُ تكاملٍ محاسبيّ لا يحتاج ملفّات الموظفين.
    """
    EMPLOYEES = "employees", _("الموظفون")
    ATTENDANCE = "attendance", _("الحضور")
    PAYROLL = "payroll", _("المسيرات والقسائم")
    LEAVES = "leaves", _("الإجازات والطلبات")
    ORG = "org", _("الهيكل التنظيميّ")


class ApiKey(CompanyScopedModel):
    """
    مفتاحُ وصولٍ برمجيّ.

    ⚠️ **ولا يُعرض بعد إنشائه**: فمن فقده أنشأ غيره — وتخزينُه
    نصًّا يجعل تسريب القاعدة تسريبَ كل العملاء.
    """
    name = models.CharField(_("الاسم"), max_length=120,
                            help_text=_("لأيّ تكاملٍ هذا المفتاح"))
    #: البادئة تُعرض للتمييز — والباقي مجزّأ
    prefix = models.CharField(_("البادئة"), max_length=12,
                              db_index=True)
    key_hash = models.CharField(max_length=255)

    scopes = models.JSONField(_("النطاقات"), default=list)

    #: ⚠️ سقفٌ بالساعة — فمفتاحٌ بلا حدّ يُسقط الخادم
    rate_limit_per_hour = models.PositiveIntegerField(
        _("سقف الطلبات بالساعة"), default=1000)

    is_active = models.BooleanField(_("مفعّل"), default=True)
    expires_on = models.DateField(_("ينتهي في"), null=True, blank=True)

    last_used_at = models.DateTimeField(null=True, blank=True)
    last_used_ip = models.CharField(max_length=45, blank=True)
    call_count = models.PositiveIntegerField(default=0)

    created_by_person_id = models.BigIntegerField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("مفتاح API")
        verbose_name_plural = _("مفاتيح API")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["company", "is_active"],
                         name="idx_apikey_company_active"),
        ]

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"

    @property
    def is_usable(self):
        """
        ⚠️ **والمنتهي لا يعمل ولو كان مفعَّلًا**: فتاريخُ انتهاءٍ
        لا يُفحص زينةٌ لا ضابط.
        """
        from django.utils import timezone

        if not self.is_active or self.revoked_at:
            return False
        if self.expires_on and self.expires_on < timezone.localdate():
            return False
        return True

    def allows(self, scope):
        return scope in (self.scopes or [])


class ApiCallLog(CompanyScopedModel):
    """
    سجلُّ نداءٍ — **للحدّ والمراجعة**.

    ⚠️ **ولا يُحفظ جسم الطلب**: فبياناتُ الموظفين لا تُنسخ في
    سجلّ.
    """
    api_key = models.ForeignKey(
        ApiKey, on_delete=models.CASCADE, related_name="calls")
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    status_code = models.PositiveSmallIntegerField()
    ip = models.CharField(max_length=45, blank=True)

    class Meta:
        verbose_name = _("نداء API")
        verbose_name_plural = _("نداءات API")
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["api_key", "at"],
                         name="idx_apicall_key_at"),
        ]

    def __str__(self):
        return f"{self.method} {self.path} — {self.status_code}"
