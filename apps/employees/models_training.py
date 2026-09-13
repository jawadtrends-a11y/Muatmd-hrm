"""
التدريب والدورات (ق-149).

**الموارد تعرّف الدورات المتاحة** (اسم · جهة · مدّة · تكلفة)،
**والمدير يرشّح منها** → وتعتمد الموارد.

⚠️ **والموظف يطلب دورةً غير متوفّرة** — فتُدرَس وتُضاف أو تُرفض
(قرار جواد).

⚠️⚠️ **وميزانية التدريب ثلاثية المصدر**: ميزانية الموظف إن
أُدخلت، فميزانية مرتبته، فبلا سقف — **والفارغ لا يعني صفرًا**.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class CourseDeliveryMode(models.TextChoices):
    ONSITE = "onsite", _("حضوريّ")
    ONLINE = "online", _("عن بُعد")
    HYBRID = "hybrid", _("مدمج")


class TrainingCourse(CompanyScopedModel):
    """
    دورةٌ تعرّفها الموارد.

    ⚠️ **والمستعملة تُعطَّل ولا تُحذف**: ترشيحاتٌ تشير إليها،
    وحذفها يترك سجلًّا بلا دورة.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("الدورة"), max_length=200)
    provider = models.CharField(_("الجهة"), max_length=150, blank=True)
    description = models.TextField(_("الوصف"), blank=True)

    duration_hours = models.PositiveSmallIntegerField(
        _("المدّة (ساعة)"), null=True, blank=True)
    cost = models.DecimalField(
        _("التكلفة"), max_digits=12, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)])
    delivery_mode = models.CharField(
        _("نمط التقديم"), max_length=10,
        choices=CourseDeliveryMode.choices,
        default=CourseDeliveryMode.ONSITE)

    is_active = models.BooleanField(_("متاحة"), default=True)

    class Meta:
        verbose_name = _("دورة تدريبية")
        verbose_name_plural = _("الدورات التدريبية")
        ordering = ["name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_course_company_code"),
        ]

    def __str__(self):
        return self.name_ar


class NominationState(models.TextChoices):
    PENDING = "pending", _("بانتظار اعتماد الموارد")
    APPROVED = "approved", _("معتمد")
    REJECTED = "rejected", _("مرفوض")
    ATTENDED = "attended", _("حضر")
    NO_SHOW = "no_show", _("لم يحضر")
    CANCELLED = "cancelled", _("أُلغي")


class TrainingNomination(CompanyScopedModel):
    """
    ترشيحُ موظفٍ لدورة.

    ⚠️ **والمدير يرشّح والموارد تعتمد** — فترشيحٌ بلا مراجعة يصرف
    ميزانيةً بلا ضابط.
    """
    course = models.ForeignKey(
        TrainingCourse, on_delete=models.PROTECT,
        related_name="nominations", verbose_name=_("الدورة"))
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="training_nominations", verbose_name=_("الموظف"))

    scheduled_on = models.DateField(_("موعد الدورة"), null=True,
                                    blank=True)
    #: التكلفة المحتسَبة — **تُجمَّد عند الترشيح**
    #
    # ⚠️ فتغيّر سعر الدورة بعدها لا يغيّر ما احتُسب على الميزانية.
    cost = models.DecimalField(
        _("التكلفة المحتسَبة"), max_digits=12, decimal_places=2,
        null=True, blank=True)

    state = models.CharField(_("الحالة"), max_length=12,
                             choices=NominationState.choices,
                             default=NominationState.PENDING,
                             db_index=True)
    nominated_by_employment_id = models.BigIntegerField(null=True,
                                                        blank=True)
    decided_by_person_id = models.BigIntegerField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(_("سبب القرار"), max_length=255,
                                     blank=True)

    # ── النتيجة ──
    score = models.DecimalField(
        _("الدرجة"), max_digits=5, decimal_places=2,
        null=True, blank=True)
    passed = models.BooleanField(_("اجتاز"), null=True, blank=True)
    certificate_url = models.CharField(_("الشهادة"), max_length=500,
                                       blank=True)
    completed_on = models.DateField(_("تاريخ الإتمام"), null=True,
                                    blank=True)
    result_note = models.CharField(_("ملاحظة النتيجة"), max_length=255,
                                   blank=True)

    class Meta:
        verbose_name = _("ترشيح تدريب")
        verbose_name_plural = _("ترشيحات التدريب")
        ordering = ["-scheduled_on", "-id"]
        indexes = [
            models.Index(fields=["company", "state"],
                         name="idx_nomination_company_state"),
            models.Index(fields=["employment", "state"],
                         name="idx_nomination_emp_state"),
        ]

    def __str__(self):
        return f"{self.employment_id} → {self.course_id}"

    @property
    def counts_against_budget(self):
        """
        ⚠️ **وما يُحسب على الميزانية**: المعتمَد وما بعده.

        فالمرفوض والملغى لا يُنقصان شيئًا، **والمعتمَد يُحسب ولو
        لم يحضر** — فالمقعد حُجز ودُفع.
        """
        return self.state in (NominationState.APPROVED,
                              NominationState.ATTENDED,
                              NominationState.NO_SHOW)


class TrainingRequest(CompanyScopedModel):
    """
    طلبُ موظفٍ لدورةٍ **غير متوفّرة** (قرار جواد).

    فالمتاح يُرشَّح له، **وغير المتاح يُطلب ويُدرَس**.
    """
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="training_requests", verbose_name=_("الموظف"))

    course_name = models.CharField(_("الدورة المطلوبة"), max_length=200)
    provider = models.CharField(_("الجهة المقترحة"), max_length=150,
                                blank=True)
    estimated_cost = models.DecimalField(
        _("التكلفة التقديرية"), max_digits=12, decimal_places=2,
        null=True, blank=True)
    justification = models.TextField(_("مبرّر الطلب"))
    reference_url = models.CharField(_("رابط الدورة"), max_length=500,
                                     blank=True)

    state = models.CharField(_("الحالة"), max_length=12,
                             choices=NominationState.choices,
                             default=NominationState.PENDING,
                             db_index=True)
    decided_by_person_id = models.BigIntegerField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    #: إن قُبل وأُضيف للكتالوج
    created_course = models.ForeignKey(
        TrainingCourse, on_delete=models.SET_NULL, null=True,
        blank=True, related_name="from_requests")

    class Meta:
        verbose_name = _("طلب تدريب")
        verbose_name_plural = _("طلبات التدريب")
        ordering = ["-id"]

    def __str__(self):
        return f"{self.employment_id} — {self.course_name}"
