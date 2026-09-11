"""
تذاكر الدعم (ق-133).

**كل موظف يفتح تذكرة** ويرى تذاكره وحده ويردّ ويتابع — فمن واجه
العلّة أدرى بوصفها، وإحالتُه لمديره تُضيع الوقت والتفاصيل.

⚠️ **والصورة إلزامية**: «لا يعمل» بلا صورة تُستهلك في أسئلةٍ
متبادلة — والشاشة تقول أكثر من فقرة.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class TicketKind(models.TextChoices):
    BUG = "bug", _("علّة")
    QUESTION = "question", _("استفسار")
    FEATURE = "feature", _("طلب ميزة")


class TicketStatus(models.TextChoices):
    OPEN = "open", _("مفتوحة")
    ANSWERED = "answered", _("رُدّ عليها")
    WAITING = "waiting", _("بانتظار العميل")
    RESOLVED = "resolved", _("مغلقة")


class TicketPriority(models.TextChoices):
    NORMAL = "normal", _("عادية")
    HIGH = "high", _("عالية")
    URGENT = "urgent", _("عاجلة")


class SupportTicket(CompanyScopedModel):
    """
    تذكرةُ دعمٍ يفتحها موظف.

    ⚠️ **وزمن الاستجابة من الباقة**: أساسيّ ٢٤ ساعة، احترافيّ ٨
    ساعات عمل، متقدّم ساعتان — ويُحسب **بختم الوقت** فيُقاس ولا
    يبقى وعدًا.
    """
    ticket_no = models.CharField(_("رقم التذكرة"), max_length=30,
                                 unique=True)
    subject = models.CharField(_("العنوان"), max_length=200)
    body = models.TextField(_("الشرح"))

    #: ⚠️ إلزامية — لا تُفتح تذكرة بلا صورة شاشة
    screenshot_url = models.CharField(_("صورة الشاشة"), max_length=500)

    kind = models.CharField(_("التصنيف"), max_length=15,
                            choices=TicketKind.choices,
                            default=TicketKind.BUG)
    priority = models.CharField(_("الأولوية"), max_length=10,
                                choices=TicketPriority.choices,
                                default=TicketPriority.NORMAL)
    status = models.CharField(_("الحالة"), max_length=15,
                              choices=TicketStatus.choices,
                              default=TicketStatus.OPEN, db_index=True)

    opened_by_person_id = models.BigIntegerField(db_index=True)
    opened_by_name = models.CharField(max_length=150, blank=True)

    #: ساعات الاستجابة المتعهَّد بها — **تُجمَّد عند الفتح**
    sla_hours = models.PositiveSmallIntegerField(
        _("مهلة الاستجابة"), default=24,
        help_text=_("من باقته يوم فتحها — فترقيتها بعدها لا تُغيّر تعهّدنا"))
    #: ⚠️ **بساعات العمل** لا بالساعة الجدارية إن كانت الباقة كذلك
    sla_business_hours = models.BooleanField(default=False)
    due_at = models.DateTimeField(_("موعد الاستجابة"), null=True, blank=True)

    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    plan_code_at_open = models.CharField(max_length=40, blank=True)

    class Meta:
        verbose_name = _("تذكرة دعم")
        verbose_name_plural = _("تذاكر الدعم")
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["company", "status"],
                         name="idx_ticket_company_status"),
            models.Index(fields=["opened_by_person_id", "status"],
                         name="idx_ticket_person_status"),
        ]

    def __str__(self):
        return f"{self.ticket_no} — {self.subject}"

    @property
    def breached(self):
        """أتجاوزت المهلة بلا ردّ؟"""
        from django.utils import timezone

        if self.first_response_at or self.due_at is None:
            return False
        return timezone.now() > self.due_at


class TicketMessage(CompanyScopedModel):
    """
    رسالةٌ في تذكرة — من العميل أو من الدعم.

    ⚠️ **ولا تُحذف**: سجلُّ المحادثة حجّةٌ للطرفين.
    """
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE,
                               related_name="messages")
    body = models.TextField(_("الرسالة"))
    attachment_url = models.CharField(_("مرفق"), max_length=500, blank=True)

    #: من المنصّة؟ وإلا فمن العميل
    from_support = models.BooleanField(default=False)
    author_person_id = models.BigIntegerField(null=True, blank=True)
    author_name = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = _("رسالة تذكرة")
        verbose_name_plural = _("رسائل التذاكر")
        ordering = ["id"]

    def __str__(self):
        return f"{self.ticket_id} — {self.id}"
