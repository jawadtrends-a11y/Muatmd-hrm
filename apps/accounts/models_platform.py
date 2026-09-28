"""
إعدادات المنصة — صف واحد يضبطه السوبر أدمن (ق-50).

ليست إعدادات شركة: هذه تخص المنصة كلها ولا تُعزل بالحساب.
"""
from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class PlatformSettings(TimeStampedModel):
    """
    صف واحد فقط — يُقرأ بـget_settings() لا بالاستعلام المباشر.
    """

    # ── الضريبة (ق-50) ──
    vat_rate = models.DecimalField(
        _("نسبة ضريبة القيمة المضافة %"), max_digits=5, decimal_places=2,
        default=Decimal("15"),
        help_text=_("تغيّرت من 5% إلى 15% في 2020 — قد تتغير مجددًا"))
    vat_number = models.CharField(
        _("الرقم الضريبي للمنصة"), max_length=20, blank=True)

    # ── التجربة المجانية (ق-47) ──
    trial_days = models.PositiveSmallIntegerField(
        _("أيام التجربة"), default=7)
    trial_max_employees = models.PositiveSmallIntegerField(
        _("حد موظفي التجربة"), default=5)

    # ── التجديد (ق-48) ──
    grace_days_after_expiry = models.PositiveSmallIntegerField(
        _("مهلة السماح بعد الانتهاء"), default=3,
        help_text=_("يعمل الحساب فيها ثم يصير للقراءة"))
    renewal_alert_monthly = models.PositiveSmallIntegerField(
        _("التنبيه قبل (شهري)"), default=5)
    renewal_alert_annual = models.PositiveSmallIntegerField(
        _("التنبيه قبل (سنوي)"), default=15)
    invoice_due_days = models.PositiveSmallIntegerField(
        _("مهلة سداد الفاتورة"), default=7)

    # ── محاولات الدفع (ق-48) ──
    manual_retry_limit = models.PositiveSmallIntegerField(
        _("محاولات الدفع اليدوي"), default=3)
    manual_retry_cooldown_hours = models.PositiveSmallIntegerField(
        _("مهلة الحظر بعدها (ساعات)"), default=6)
    auto_retry_hours = models.CharField(
        _("جدول إعادة المحاولة التلقائية"), max_length=50, default="12,24",
        help_text=_("ساعات بين المحاولات — 12,24 يعني بعد 12 ثم بعد 24"))

    # ── الربط بالمحاسبي (ق-12) ──
    accounting_api_url = models.CharField(
        _("رابط محاسبة معتمد"), max_length=300, blank=True)
    accounting_enabled = models.BooleanField(
        _("مزامنة الفواتير مع المحاسبي"), default=False)

    support_email = models.EmailField(_("بريد الدعم"), blank=True)

    # ── ق-٢٧٦: إشعارات المنصّة والتحويل البنكيّ (قرار جواد) ──
    #: ⚠️⚠️ **تسجيلٌ جديد بلا إشعارٍ يضيع**: يسجّل العميل وينتظر، ولا أحد
    #: يعلم. فيصل إشعارٌ بكل تسجيل — وبمن اختار التحويل البنكيّ خاصّةً،
    #: **فتفعيلُه بيد المشرف لا بالبوابة**.
    notify_email = models.EmailField(
        _("بريد إشعارات المنصّة"), blank=True,
        help_text=_("يصله كل تسجيلٍ جديد وكل طلب تحويلٍ بنكيّ"))

    #: ⚠️ **التحويل البنكيّ يتمّ خارج معتمد** (قرار جواد): تُعرض البيانات
    #: وملخّص الدفع، ولا تُنشأ فاتورة. والشركات المتوسطة والكبيرة تفضّله
    #: على البطاقة.
    #: ⚠️⚠️ **وإخفاء البوابة لازمٌ أيضًا** (قرار جواد): فقد تتعطّل ميسر،
    #: أو يُراد التحويل وحده فترةً. **ولا يجوز أن يبقى خيارٌ لا يعمل.**
    gateway_enabled = models.BooleanField(
        _("إتاحة الدفع بالبطاقة"), default=True)
    bank_transfer_enabled = models.BooleanField(
        _("إتاحة التحويل البنكي"), default=False)
    # ── ق-٢٨١: الإعلان عن العرض (قرار جواد) ──
    #: ⚠️⚠️ **كودٌ لا يعرفه أحدٌ لا يُستعمل**: تُنشئه اللوحة ويقبله الخادم،
    #: **ولا مكانَ يُعلن عنه** — فيبقى حبرًا. فيُعرض شريطًا في شاشتي
    #: الأسعار: العامّة (قبل التسجيل) والاشتراك (للتجديد).
    promo_enabled = models.BooleanField(_("إظهار شريط العرض"), default=False)
    promo_text = models.CharField(
        _("نصّ العرض"), max_length=160, blank=True,
        help_text=_("مثال: خصم ٢٠٪ على الاشتراك السنوي"))
    promo_code = models.CharField(
        _("كود العرض"), max_length=40, blank=True,
        help_text=_("يُعرض للنسخ — ويجب أن يكون كودًا قائمًا في الخصومات"))

    bank_name = models.CharField(_("اسم البنك"), max_length=120, blank=True)
    bank_iban = models.CharField(_("الآيبان"), max_length=34, blank=True)
    bank_beneficiary = models.CharField(
        _("اسم المستفيد"), max_length=150, blank=True)
    support_mobile = models.CharField(_("جوال الدعم"), max_length=20,
                                      blank=True)

    class Meta:
        verbose_name = _("إعدادات المنصة")
        verbose_name_plural = _("إعدادات المنصة")

    def __str__(self):
        return f"إعدادات المنصة (ضريبة {self.vat_rate}%)"

    def save(self, *args, **kwargs):
        """صف واحد فقط."""
        self.pk = 1
        super().save(*args, **kwargs)

    @property
    def auto_retry_schedule(self):
        """[12, 24] — ساعات بين محاولات التجديد التلقائي."""
        try:
            return [int(x.strip()) for x in self.auto_retry_hours.split(",")
                    if x.strip()]
        except ValueError:
            return [12, 24]


def get_settings():
    """
    إعدادات المنصة — تُنشأ بقيمها الافتراضية عند أول نداء.
    """
    obj, _created = PlatformSettings.objects.get_or_create(pk=1)
    return obj
