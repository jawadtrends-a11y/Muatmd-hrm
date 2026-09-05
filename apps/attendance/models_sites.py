"""
مواقع العمل والبصمة بالنطاق المكاني (ق-62).

الموقع دائرة: مركز ونصف قطر وهامش تسامح. والبصمة تُقبل إن كانت
داخل (نصف القطر + الهامش) وتُرفض خارجها.

**المواقع مستقلة عن الفروع** — فمشروع مؤقت أو موقع عميل ليس
فرعًا في السجل التجاري.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class PunchMethod(models.TextChoices):
    MOBILE_GPS = "mobile_gps", _("جوال بالموقع")
    DEVICE = "device", _("جهاز بصمة")
    MANUAL = "manual", _("إدخال يدوي")
    WEB = "web", _("متصفح")


class WorkSite(CompanyScopedModel):
    """
    موقع عمل — دائرة على الخريطة.

    التحقق الجغرافي **اختياري لكل موقع**: مكتب فيه جهاز بصمة قد
    لا يحتاجه، وموقع ميداني يحتاجه.
    """

    code = models.CharField(_("الرمز"), max_length=20)
    name_ar = models.CharField(_("الاسم"), max_length=150)
    name_en = models.CharField(_("بالإنجليزية"), max_length=150, blank=True)

    # ── الموقع الجغرافي ──
    latitude = models.DecimalField(
        _("خط العرض"), max_digits=10, decimal_places=7, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(
        _("خط الطول"), max_digits=10, decimal_places=7, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])

    radius_meters = models.IntegerField(
        _("نصف القطر (متر)"), default=100,
        validators=[MinValueValidator(20), MaxValueValidator(5000)],
        help_text=_("حجم الموقع نفسه"))

    # ق-62: الهامش يُضبط لكل موقع بين 50 و500 متر — فالـGPS يخطئ
    # داخل المباني الخرسانية، والهامش الثابت لا يناسب مستودعًا
    # مفتوحًا ومكتبًا في برج.
    tolerance_meters = models.IntegerField(
        _("هامش التسامح (متر)"), default=100,
        validators=[MinValueValidator(50), MaxValueValidator(500)],
        help_text=_("يُضاف لنصف القطر — بين 50 و500 متر"))

    enforce_geofence = models.BooleanField(
        _("التحقق من الموقع الجغرافي"), default=True,
        help_text=_("عند تعطيله تُقبل البصمة من أي مكان"))

    # ── العنوان الوصفي ──
    city = models.CharField(_("المدينة"), max_length=80, blank=True)
    address = models.CharField(_("العنوان"), max_length=255, blank=True)

    site_manager = models.ForeignKey(
        "employees.Employment", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="managed_sites",
        verbose_name=_("مدير الموقع"))

    is_active = models.BooleanField(_("نشط"), default=True)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("موقع عمل")
        verbose_name_plural = _("مواقع العمل")
        ordering = ["name_ar"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uniq_worksite_code"),
        ]

    def __str__(self):
        return f"{self.name_ar} ({self.code})"

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def effective_radius(self):
        """النطاق المقبول = نصف القطر + الهامش."""
        return self.radius_meters + self.tolerance_meters


class SiteAssignment(CompanyScopedModel):
    """
    إسناد موظف لموقع — بلا حد للعدد (ق-62).

    فالفني يزور ثلاثة مواقع، والإداري موقعًا واحدًا.
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="site_assignments", verbose_name=_("الموظف"))
    site = models.ForeignKey(
        WorkSite, on_delete=models.CASCADE,
        related_name="assignments", verbose_name=_("الموقع"))

    is_primary = models.BooleanField(
        _("الموقع الأساسي"), default=False,
        help_text=_("موقعه المعتاد — للتقارير والافتراضات"))

    effective_from = models.DateField(_("ساري من"), null=True, blank=True)
    effective_to = models.DateField(_("ساري حتى"), null=True, blank=True)

    class Meta:
        verbose_name = _("إسناد موقع")
        verbose_name_plural = _("إسنادات المواقع")
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "site"], name="uniq_site_assignment"),
        ]

    def __str__(self):
        return f"{self.employment.employee_no} @ {self.site.code}"


class PunchDevice(CompanyScopedModel):
    """
    جهاز بصمة مرتبط بموقع.

    الجهاز في مكان ثابت — فبصمته تعني الحضور فيه بلا حاجة لـGPS.
    """

    device_code = models.CharField(_("رمز الجهاز"), max_length=60)
    name_ar = models.CharField(_("الاسم"), max_length=120)
    # الموقع اختياري: الجهاز مثبَّت في مكانه والبصمة عليه دليل
    # الحضور. والنطاق يخصّ البصمة من الجوال بالـGPS (ق-62).
    site = models.ForeignKey(
        WorkSite, on_delete=models.SET_NULL, related_name="devices",
        null=True, blank=True, verbose_name=_("الموقع"))

    api_key_hash = models.CharField(
        _("مفتاح الجهاز"), max_length=128, blank=True, db_index=True,
        help_text=_("مجزَّأ — الجهاز يرسل به بصماته. والتجزئة تتجاوز "
                    "64 حرفًا، فالطول يتّسع لها"))

    last_seen_at = models.DateTimeField(_("آخر اتصال"), null=True, blank=True)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("جهاز بصمة")
        verbose_name_plural = _("أجهزة البصمة")
        constraints = [
            models.UniqueConstraint(
                fields=["company", "device_code"], name="uniq_punch_device"),
        ]

    def __str__(self):
        return f"{self.name_ar} @ {self.site.code}"
