"""
أجهزة الجوال لإشعارات الدفع (ق-232).

⚠️⚠️ **وقناة الجوال كانت معرَّفةً بلا منفّذ** (ق-90): فرعها يُسجّل
«قيد الإرسال» للأبد. وهذا الجدول أول نصفَي المنفّذ: **من يستقبل وعلى أيّ جهاز**.

- الجهاز يُربط **بالشخص** — كما يُعرّف الإشعار مستقبله (`recipient_person_id`)
- وللشخص أكثر من جهاز — فكلّ جهازٍ سطر
- ⚠️ **والرمز فريدٌ داخل الحساب لا عالميًّا**: فالعزل يحجب الحسابات الأخرى،
  ورمزٌ فريدٌ عالميًّا **يصطدم بسطرٍ لا يُرى فيُسقط التسجيل**
- ⚠️ **ولا حذف**: الجهاز يُعطَّل بسببه (خروج · رفض Expo) — فالسجلّ يشرح
  لماذا لم يصل إشعارٌ لموظف
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel


class DevicePlatform(models.TextChoices):
    IOS = "ios", _("آيفون")
    ANDROID = "android", _("أندرويد")


class PushDevice(AccountScopedModel):
    person_id = models.BigIntegerField(_("الشخص"), db_index=True)
    token = models.CharField(_("رمز الجهاز"), max_length=200)
    platform = models.CharField(_("المنصّة"), max_length=10,
                                choices=DevicePlatform.choices)
    app_version = models.CharField(_("إصدار التطبيق"), max_length=20,
                                   blank=True)
    is_active = models.BooleanField(_("نشط"), default=True, db_index=True)
    last_seen_at = models.DateTimeField(_("آخر ظهور"), null=True, blank=True)
    deactivated_reason = models.CharField(_("سبب التعطيل"), max_length=120,
                                          blank=True)

    class Meta:
        verbose_name = _("جهاز جوال")
        verbose_name_plural = _("أجهزة الجوال")
        constraints = [
            models.UniqueConstraint(fields=["account", "token"],
                                    name="uq_push_device_account_token"),
        ]
        indexes = [
            models.Index(fields=["person_id", "is_active"],
                         name="idx_push_person_active"),
        ]

    def __str__(self):
        return f"{self.person_id} · {self.platform}"
