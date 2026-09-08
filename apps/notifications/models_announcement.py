"""
الإعلانات — رسالة تصل موظفًا أو إدارة أو الشركة كلّها.

تركب على محرّك الإشعارات ولا تلتفّ عليه: الإعلان سجلّ يُحفظ (من
أرسل، ولمن، وماذا)، والتوصيل يمرّ بـemit كأي حدث — فتنتفع
بتفضيلات المستخدم ولغته وسجلّ تسليمه.

والنوع ليس زينةً: الموظف يميّز التعزية من الاجتماع قبل أن يفتح.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel

EVENT_KEY = "announcement.published"


class AnnouncementKind(models.TextChoices):
    GENERAL   = "general",   _("إعلان عام")
    EVENT     = "event",     _("فعالية")
    MEETING   = "meeting",   _("اجتماع")
    CONGRATS  = "congrats",  _("تهنئة")
    CONDOLENCE = "condolence", _("تعزية")
    DECISION  = "decision",  _("قرار إداري")


class AudienceType(models.TextChoices):
    COMPANY     = "company",     _("كل الشركة")
    DEPARTMENTS = "departments", _("إدارات محددة")
    PERSONS     = "persons",     _("أشخاص محددون")


class Announcement(AccountScopedModel):
    company_id = models.BigIntegerField(_("الشركة"), db_index=True)

    kind = models.CharField(_("النوع"), max_length=20,
                            choices=AnnouncementKind.choices,
                            default=AnnouncementKind.GENERAL, db_index=True)

    # بلغتيه (ق-92): الشركة تكتب النصّين، ومن نقص إنجليزيّه يرتدّ
    # للعربي — فلا موظف يقرأ فراغًا.
    title_ar = models.CharField(_("العنوان"), max_length=255)
    title_en = models.CharField(_("العنوان بالإنجليزية"), max_length=255,
                                blank=True)
    body_ar  = models.TextField(_("النص"))
    body_en  = models.TextField(_("النص بالإنجليزية"), blank=True)

    audience_type = models.CharField(_("المستقبلون"), max_length=20,
                                     choices=AudienceType.choices)
    # أرقام الإدارات أو الأشخاص حسب النوع — فارغة لـcompany.
    audience_ids = models.JSONField(_("المحددون"), default=list, blank=True)

    via_email = models.BooleanField(
        _("إرسال بالبريد"), default=False,
        help_text=_("داخل النظام دائمًا، والبريد باختيار المرسل"))

    sent_by_person_id = models.BigIntegerField(_("المرسل"), null=True,
                                               blank=True, db_index=True)
    # المستقبلون يُجمَّدون عند الإرسال: من انضم بعده لا يرى إعلانًا
    # لم يكن مقصودًا به، ومن نُقل لا يفقد ما وصله.
    recipient_count = models.IntegerField(_("عدد المستقبلين"), default=0)
    sent_at = models.DateTimeField(_("أُرسل في"), null=True, blank=True,
                                   db_index=True)

    class Meta:
        verbose_name = _("إعلان")
        verbose_name_plural = _("الإعلانات")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title_ar

    def title_for(self, locale="ar"):
        if locale == "en" and self.title_en.strip():
            return self.title_en
        return self.title_ar

    def body_for(self, locale="ar"):
        if locale == "en" and self.body_en.strip():
            return self.body_en
        return self.body_ar


class AnnouncementAttachment(AccountScopedModel):
    """مرفق — يُعرض في النظام ويُرفق في البريد."""

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE,
                                     related_name="attachments")
    stored_file = models.ForeignKey("core.StoredFile", on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("مرفق إعلان")
        verbose_name_plural = _("مرفقات الإعلانات")
