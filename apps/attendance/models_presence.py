"""
تتبّع التواجد في موقع العمل (ق-144).

**الشركة تعرف: أهو في موقعه أم لا** — لا أين كان بالضبط.

⚠️⚠️ **ولا تُحفظ الإحداثيّات**: حفظُ مسار الموظف الكامل تتبّعٌ لا
مراقبة حضور، وله بُعدٌ قانونيّ. **فالمحفوظ حكمٌ ثنائيّ**: داخل
النطاق أو خارجه (قرار جواد).

⚠️ **وأثناء الفترة فقط** — فخارجها وقتُه ملكُه. **وبعلمه**:
إشعارٌ ظاهر في شاشته لا تتبّعٌ خفيّ.

⚠️⚠️ **والخصم يُقترَح ولا يقع**: فساعة البريك مرنةٌ في كثيرٍ من
الشركات — **والموارد تعتمد أو تترك** (قرار جواد).
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class PresenceState(models.TextChoices):
    INSIDE = "inside", _("داخل الموقع")
    OUTSIDE = "outside", _("خارج الموقع")
    NO_SIGNAL = "no_signal", _("لا إشارة")


class PresencePing(CompanyScopedModel):
    """
    نبضةُ تواجدٍ واحدة.

    ⚠️ **بلا إحداثيّات** — والمسافة تقريبيّة للتوضيح لا للتتبّع.
    """
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="presence_pings")
    site = models.ForeignKey(
        "attendance.WorkSite", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="presence_pings")

    work_date = models.DateField(db_index=True)
    at = models.DateTimeField(_("الوقت"), db_index=True)
    state = models.CharField(_("الحالة"), max_length=12,
                             choices=PresenceState.choices)
    #: مسافةٌ تقريبيّة بالأمتار — للتوضيح لا للتتبّع
    distance_meters = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("نبضة تواجد")
        verbose_name_plural = _("نبضات التواجد")
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["employment", "work_date"],
                         name="idx_ping_emp_date"),
            models.Index(fields=["company", "work_date"],
                         name="idx_ping_company_date"),
        ]

    def __str__(self):
        return f"{self.employment_id} — {self.at} — {self.state}"


class PresenceDay(CompanyScopedModel):
    """
    خلاصةُ يومٍ — **وعليها يُقترَح الخصم**.

    ⚠️ **ولا يقع آليًّا**: فساعة البريك مرنة، والموارد تعتمد أو
    تترك.
    """
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="presence_days")
    work_date = models.DateField(db_index=True)

    inside_minutes = models.PositiveIntegerField(_("داخل"), default=0)
    outside_minutes = models.PositiveIntegerField(_("خارج"), default=0)
    no_signal_minutes = models.PositiveIntegerField(
        _("بلا إشارة"), default=0)

    #: بعد التسامح — وهو ما يُقترَح خصمه
    deductible_minutes = models.PositiveIntegerField(
        _("القابل للخصم"), default=0)
    suggested_amount = models.DecimalField(
        _("الخصم المقترَح"), max_digits=10, decimal_places=2,
        null=True, blank=True)

    # ── قرار الموارد ──
    is_reviewed = models.BooleanField(_("رُوجع"), default=False,
                                      db_index=True)
    approved_amount = models.DecimalField(
        _("المعتمَد"), max_digits=10, decimal_places=2,
        null=True, blank=True)
    reviewed_by_person_id = models.BigIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)
    is_applied = models.BooleanField(_("دخل المسير"), default=False,
                                     db_index=True)

    class Meta:
        verbose_name = _("تواجد يوم")
        verbose_name_plural = _("التواجد اليوميّ")
        ordering = ["-work_date"]
        constraints = [
            models.UniqueConstraint(fields=["employment", "work_date"],
                                    name="uq_presenceday_emp_date"),
        ]
        indexes = [
            models.Index(fields=["company", "is_reviewed", "is_applied"],
                         name="idx_presday_review"),
        ]

    def __str__(self):
        return f"{self.employment_id} — {self.work_date}"
