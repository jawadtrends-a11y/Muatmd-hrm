"""
تفضيلات لوحة المستخدم (ق-106).

ما اختاره وترتيبه — ولا يُخزَّن ما لم يخصّص: من لم يلمس اللوحة
يرى الافتراضيّ لدوره، فلو تغيّر دوره تبدّل ما يراه تلقائيًّا.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel


class DashboardPreference(AccountScopedModel):
    # الحساب للعزل كبقيّة الجداول، والمستخدم هو المفتاح الحقيقيّ:
    # لكلّ صفّه، ولا يرى غيره.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="dashboard_preference", verbose_name=_("المستخدم"))
    # قائمة مفاتيح مرتّبة — الترتيب هو ترتيب العرض.
    widget_keys = models.JSONField(_("الودجتات"), default=list)

    class Meta:
        verbose_name = _("تفضيل لوحة")
        verbose_name_plural = _("تفضيلات اللوحات")

    def __str__(self):
        return f"لوحة {self.user_id}"
