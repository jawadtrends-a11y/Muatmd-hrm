"""
محرك الإشعارات الموحّد.

المبدأ الحاكم: الموديولات تُطلق أحداثًا ولا تعرف من المستقبل ولا
بأي قناة ولا بأي لغة. المحرك يقرر.

    موديول → emit(event) → المحرك → [مستقبلون × قنوات × قوالب بلغتهم]

راجع الوثيقة المعمارية (2) القسم 5.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel, TimeStampedModel


class Channel(models.TextChoices):
    IN_APP   = "in_app",   _("داخل النظام")
    EMAIL    = "email",    _("بريد إلكتروني")
    WHATSAPP = "whatsapp", _("واتساب")
    PUSH     = "push",     _("إشعار جوال")


class DeliveryStatus(models.TextChoices):
    PENDING   = "pending",   _("قيد الإرسال")
    SENT      = "sent",      _("أُرسل")
    DELIVERED = "delivered", _("وصل")
    FAILED    = "failed",    _("فشل")
    SKIPPED   = "skipped",   _("متخطّى")


class NotificationEvent(models.Model):
    """سجل الأحداث — جدول منصة يعرّفه المطوّر لا العميل."""

    event_key = models.CharField(_("مفتاح الحدث"), max_length=80, unique=True)
    module    = models.CharField(_("الوحدة"), max_length=40)
    name_ar   = models.CharField(_("الاسم"), max_length=200)
    description_ar = models.TextField(_("الوصف"), blank=True)
    default_channels = models.JSONField(_("القنوات الافتراضية"), default=list)
    is_mandatory = models.BooleanField(
        _("إلزامي"), default=False,
        help_text=_("لا يستطيع المستخدم إيقافه — أحداث حرجة"))
    sort_order = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("حدث إشعار")
        verbose_name_plural = _("أحداث الإشعارات")
        ordering = ["module", "sort_order"]

    def __str__(self):
        return self.name_ar


class NotificationTemplate(TimeStampedModel):
    """
    قالب رسالة. account فارغ = قالب افتراضي للمنصة.
    الشركة تنسخه وتعدّله إن أرادت.
    """

    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE,
        null=True, blank=True, related_name="notification_templates",
        help_text=_("فارغ = قالب افتراضي"))
    event_key = models.CharField(max_length=80, db_index=True)
    channel   = models.CharField(max_length=20, choices=Channel.choices)
    locale    = models.CharField(max_length=5,
                                 choices=[("ar", "العربية"), ("en", "English"),
                                          ("ur", "اردو")])
    subject = models.CharField(_("العنوان"), max_length=255, blank=True)
    body    = models.TextField(_("النص"),
                               help_text=_("متغيرات بصيغة {{employee_name}}"))

    class Meta:
        verbose_name = _("قالب إشعار")
        verbose_name_plural = _("قوالب الإشعارات")
        constraints = [
            models.UniqueConstraint(
                fields=["account", "event_key", "channel", "locale"],
                name="uq_template_per_account"),
            models.UniqueConstraint(
                fields=["event_key", "channel", "locale"],
                condition=models.Q(account__isnull=True),
                name="uq_default_template"),
        ]

    def __str__(self):
        return f"{self.event_key}/{self.channel}/{self.locale}"


class NotificationPreference(AccountScopedModel):
    """تفضيلات المستخدم — لا تسري على الأحداث الإلزامية."""

    person_id = models.BigIntegerField(_("الشخص"), db_index=True)
    event_key = models.CharField(max_length=80)
    channel   = models.CharField(max_length=20, choices=Channel.choices)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("تفضيل إشعار")
        verbose_name_plural = _("تفضيلات الإشعارات")
        constraints = [
            models.UniqueConstraint(fields=["person_id", "event_key", "channel"],
                                    name="uq_pref_per_person"),
        ]


class Notification(AccountScopedModel):
    """إشعار داخل النظام — ما يظهر في جرس الإشعارات."""

    company_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    recipient_person_id = models.BigIntegerField(_("المستقبل"), db_index=True)
    event_key = models.CharField(max_length=80, db_index=True)
    title = models.CharField(_("العنوان"), max_length=255)
    body  = models.TextField(_("النص"), blank=True)
    link_url = models.CharField(_("الرابط"), max_length=500, blank=True)
    payload  = models.JSONField(default=dict, blank=True)
    locale   = models.CharField(max_length=5, default="ar")
    read_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("إشعار")
        verbose_name_plural = _("الإشعارات")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient_person_id", "-created_at"],
                         condition=models.Q(read_at__isnull=True),
                         name="idx_notif_unread"),
        ]

    def __str__(self):
        return self.title


class NotificationDelivery(AccountScopedModel):
    """سجل التسليم لكل قناة — يشمل التكلفة لاحتساب الاستهلاك."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE,
                                     related_name="deliveries")
    channel = models.CharField(max_length=20, choices=Channel.choices)
    status  = models.CharField(max_length=20, choices=DeliveryStatus.choices,
                               default=DeliveryStatus.PENDING, db_index=True)
    provider_ref = models.CharField(max_length=120, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=4, default=0,
                               help_text=_("تكلفة واتساب تُحتسب في الاستهلاك"))
    error = models.TextField(blank=True)
    attempted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("تسليم إشعار")
        verbose_name_plural = _("تسليمات الإشعارات")
