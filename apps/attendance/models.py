"""
الحضور والانصراف.

مبدأ معماري حاكم: البصمات الخام لا تُمس ولا تُعدَّل ولا تُحذف —
هي مصدر الحقيقة. السجل اليومي مُشتق ويمكن إعادة بنائه بالكامل،
فعند تغيير سياسة نعيد المعالجة ولا نفقد شيئًا.

قرار مثبَّت (ق-13): الحضور المتداخل عبر شركات الحساب الواحد حالة
صحيحة ومقصودة — الشخص قد يعمل حضوريًا في شركة وعن بُعد في أخرى.
ممنوع إضافة أي تحقق أو تحذير أو قيد تفرد على ذلك.
"""
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class Shift(CompanyScopedModel):
    """وردية عمل."""

    code = models.CharField(_("الرمز"), max_length=30)
    name_ar = models.CharField(_("الاسم"), max_length=120)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=120, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=120, blank=True)

    start_time = models.TimeField(_("بداية الدوام"))
    end_time = models.TimeField(_("نهاية الدوام"))
    crosses_midnight = models.BooleanField(
        _("تمتد لليوم التالي"), default=False,
        help_text=_("ورديات ليلية تبدأ مساءً وتنتهي صباحًا"))
    break_minutes = models.PositiveSmallIntegerField(
        _("دقائق الاستراحة"), default=60)

    grace_in_minutes = models.PositiveSmallIntegerField(
        _("سماح التأخير"), default=0)
    grace_out_minutes = models.PositiveSmallIntegerField(
        _("سماح الانصراف المبكر"), default=0)

    working_days = ArrayField(
        models.PositiveSmallIntegerField(),
        verbose_name=_("أيام العمل"), default=list,
        help_text=_("0=الأحد … 6=السبت"))
    is_flexible = models.BooleanField(
        _("دوام مرن"), default=False,
        help_text=_("يُحتسب بإجمالي الساعات لا بوقت الحضور"))
    is_active = models.BooleanField(_("نشطة"), default=True)

    class Meta:
        verbose_name = _("وردية")
        verbose_name_plural = _("الورديات")
        ordering = ["start_time"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_shift_code_per_company"),
        ]

    def __str__(self):
        return self.name_ar


class ShiftAssignment(CompanyScopedModel):
    """إسناد وردية لموظف بتاريخ سريان."""

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="shift_assignments", verbose_name=_("الموظف"))
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT,
                              related_name="assignments",
                              verbose_name=_("الوردية"))
    effective_from = models.DateField(_("سريان من"), db_index=True)
    effective_to = models.DateField(_("سريان إلى"), null=True, blank=True)

    class Meta:
        verbose_name = _("إسناد وردية")
        verbose_name_plural = _("إسنادات الورديات")
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "effective_from"],
                name="uq_shift_assignment_per_date"),
        ]


class PunchSource(models.TextChoices):
    DEVICE = "device", _("جهاز بصمة")
    MOBILE = "mobile", _("تطبيق جوال")
    WEB = "web", _("المتصفح")
    WHATSAPP = "whatsapp", _("واتساب")
    MANUAL = "manual", _("إدخال يدوي")


class AttendancePunch(CompanyScopedModel):
    """
    بصمة خام — لا تُعدَّل ولا تُحذف أبدًا.

    مصدر الحقيقة. السجل اليومي يُشتق منها ويمكن إعادة بنائه.
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="punches", verbose_name=_("الموظف"))
    punched_at = models.DateTimeField(_("وقت البصمة"), db_index=True)
    source = models.CharField(_("المصدر"), max_length=20,
                              choices=PunchSource.choices)
    device_id = models.CharField(_("معرّف الجهاز"), max_length=60, blank=True)
    external_ref = models.CharField(
        _("المرجع الخارجي"), max_length=120, blank=True,
        help_text=_("مفتاح فريد يمنع تكرار البصمة عند إعادة الإرسال"))
    latitude = models.DecimalField(_("خط العرض"), max_digits=10,
                                   decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(_("خط الطول"), max_digits=10,
                                    decimal_places=7, null=True, blank=True)
    raw_payload = models.JSONField(_("البيانات الخام"), default=dict, blank=True)

    class Meta:
        verbose_name = _("بصمة")
        verbose_name_plural = _("البصمات")
        ordering = ["-punched_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "external_ref"],
                condition=models.Q(external_ref__gt=""),
                name="uq_punch_external_ref"),
        ]
        indexes = [
            models.Index(fields=["employment", "punched_at"]),
            models.Index(fields=["company", "punched_at"]),
        ]

    def __str__(self):
        return f"{self.employment.employee_no} @ {self.punched_at}"


class DayStatus(models.TextChoices):
    PRESENT = "present", _("حاضر")
    ABSENT = "absent", _("غائب")
    LEAVE = "leave", _("إجازة")
    HOLIDAY = "holiday", _("عطلة")
    WEEKEND = "weekend", _("راحة أسبوعية")
    PARTIAL = "partial", _("حضور جزئي")
    NOT_SCHEDULED = "not_scheduled", _("خارج جدول العمل")


class AttendanceDay(CompanyScopedModel):
    """
    السجل اليومي المُحتسب — مُشتق من البصمات ويُعاد بناؤه.

    أي تعديل يدوي يُعلَّم ويُنسب لفاعله (سجل تدقيق).
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="attendance_days", verbose_name=_("الموظف"))
    work_date = models.DateField(_("التاريخ"), db_index=True)
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name="+")

    first_in = models.DateTimeField(_("أول حضور"), null=True, blank=True)
    last_out = models.DateTimeField(_("آخر انصراف"), null=True, blank=True)

    worked_minutes = models.PositiveIntegerField(_("دقائق العمل"), default=0)
    late_minutes = models.PositiveIntegerField(_("دقائق التأخير"), default=0)
    early_out_minutes = models.PositiveIntegerField(
        _("دقائق الانصراف المبكر"), default=0)
    overtime_minutes = models.PositiveIntegerField(
        _("دقائق العمل الإضافي"), default=0)
    approved_overtime_minutes = models.PositiveIntegerField(
        _("الإضافي المعتمد"), default=0,
        help_text=_("لا يدخل المسير إلا بعد الاعتماد"))

    status = models.CharField(_("الحالة"), max_length=20,
                              choices=DayStatus.choices, db_index=True)
    punch_count = models.PositiveSmallIntegerField(_("عدد البصمات"), default=0)

    is_manually_adjusted = models.BooleanField(_("عُدّل يدويًا"), default=False)
    adjusted_by_person = models.ForeignKey(
        "employees.Person", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="adjusted_attendance_days")
    adjustment_note = models.TextField(_("سبب التعديل"), blank=True)
    computed_at = models.DateTimeField(_("وقت الاحتساب"), null=True, blank=True)

    class Meta:
        verbose_name = _("سجل حضور يومي")
        verbose_name_plural = _("سجلات الحضور اليومية")
        ordering = ["-work_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "work_date"],
                name="uq_attendance_day"),
        ]
        indexes = [
            models.Index(fields=["company", "work_date", "status"]),
        ]

    def __str__(self):
        return f"{self.employment.employee_no} — {self.work_date}"


class AttendanceMonthlySummary(CompanyScopedModel):
    """
    ملخص شهري مُجمَّع مسبقًا.

    محرك الرواتب يقرأ صفًا واحدًا لكل موظف لا 600 بصمة — شرط
    تحمّل ذروة الرواتب (الوثيقة المعمارية 2 القسم 3).
    """

    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="attendance_summaries")
    period_year = models.PositiveSmallIntegerField(_("السنة"))
    period_month = models.PositiveSmallIntegerField(_("الشهر"))

    worked_days = models.DecimalField(_("أيام العمل"), max_digits=6,
                                      decimal_places=2, default=0)
    unpaid_absent_days = models.DecimalField(
        _("أيام الغياب بلا أجر"), max_digits=6, decimal_places=2, default=0)
    paid_leave_days = models.DecimalField(
        _("أيام الإجازة المدفوعة"), max_digits=6, decimal_places=2, default=0)
    late_minutes = models.PositiveIntegerField(_("دقائق التأخير"), default=0)
    approved_overtime_minutes = models.PositiveIntegerField(
        _("الإضافي المعتمد"), default=0)

    is_final = models.BooleanField(
        _("نهائي"), default=False,
        help_text=_("يُقفل عند اعتماد المسير"))
    computed_at = models.DateTimeField(_("وقت الاحتساب"), null=True, blank=True)

    class Meta:
        verbose_name = _("ملخص حضور شهري")
        verbose_name_plural = _("ملخصات الحضور الشهرية")
        constraints = [
            models.UniqueConstraint(
                fields=["employment", "period_year", "period_month"],
                name="uq_attendance_summary"),
        ]


# مواقع العمل والبصمة بالنطاق (ق-62)
from apps.attendance.models_sites import (  # noqa: E402,F401
    PunchDevice, PunchMethod, SiteAssignment, WorkSite,
)
