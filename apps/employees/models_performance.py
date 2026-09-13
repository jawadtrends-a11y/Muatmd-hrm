"""
تقييم الأداء (ق-146).

**أربع طبقات** (قرار جواد):

١. **مدير الإدارة يضع مؤشّرات إدارته** — وتعتمدها الموارد.
٢. **المشرف يُدخل الفعليّ** لمن تحته، والمدير للمشرفين —
   وتعتمده الموارد.
٣. **الموظف يقيّم نفسه ويقيّم مديريه** — ⚠️ **وتقييم المديرين
   مجهول**: فلو رآه المدير باسم صاحبه لم يصدق أحد.
٤. ⚠️ **والأثر تقريرٌ فقط** — لا مال.

**والمقياس يُختار لكل مؤشّر**: نسبةً أو سُلّمًا أو عددًا.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class KPIScale(models.TextChoices):
    PERCENT = "percent", _("نسبة مئوية")
    SCALE_5 = "scale_5", _("سُلّم من ١ إلى ٥")
    COUNT = "count", _("عدد")


class KPIDirection(models.TextChoices):
    HIGHER = "higher", _("الأعلى أفضل")
    LOWER = "lower", _("الأقلّ أفضل")


class KPIKind(models.TextChoices):
    QUANTITATIVE = "quantitative", _("كمّيّ")
    BEHAVIORAL = "behavioral", _("سلوكيّ")


class ApprovalState(models.TextChoices):
    DRAFT = "draft", _("مسودّة")
    PENDING = "pending", _("بانتظار اعتماد الموارد")
    APPROVED = "approved", _("معتمد")
    REJECTED = "rejected", _("مرفوض")


class ReviewCycle(CompanyScopedModel):
    """
    دورةُ تقييمٍ بمدًى زمنيّ.

    ⚠️ **والمغلقة لا تُعدَّل**: فنتيجةٌ صدرت ثم تغيّرت لا يُوثَق
    بها.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("الدورة"), max_length=120)
    start_date = models.DateField(_("من"))
    end_date = models.DateField(_("إلى"))

    is_open = models.BooleanField(_("مفتوحة"), default=True)
    self_review_enabled = models.BooleanField(
        _("تقييم ذاتيّ"), default=True)
    upward_review_enabled = models.BooleanField(
        _("تقييم المديرين"), default=True,
        help_text=_("⚠️ مجهولٌ دائمًا — ولا يُنسب لصاحبه"))

    class Meta:
        verbose_name = _("دورة تقييم")
        verbose_name_plural = _("دورات التقييم")
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_cycle_company_code"),
        ]

    def __str__(self):
        return self.name_ar


class KPI(CompanyScopedModel):
    """
    مؤشّرُ أداءٍ تضعه إدارةٌ بعينها.

    ⚠️ **ولا يُستعمل قبل اعتماد الموارد**: فمؤشّرٌ يضعه مديرٌ
    ويقيس به فريقه بلا مراجعة يصير حكمًا بلا ضابط.
    """
    department = models.ForeignKey(
        "organization.Department", on_delete=models.CASCADE,
        related_name="kpis", verbose_name=_("الإدارة"))
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("المؤشّر"), max_length=200)
    description = models.TextField(_("التعريف"), blank=True)

    kind = models.CharField(_("النوع"), max_length=15,
                            choices=KPIKind.choices,
                            default=KPIKind.QUANTITATIVE)
    scale = models.CharField(_("المقياس"), max_length=12,
                             choices=KPIScale.choices,
                             default=KPIScale.PERCENT)
    direction = models.CharField(_("الاتجاه"), max_length=10,
                                 choices=KPIDirection.choices,
                                 default=KPIDirection.HIGHER)
    unit = models.CharField(_("الوحدة"), max_length=40, blank=True)

    #: هدفٌ افتراضيّ — يُعدَّل عند الإسناد
    default_target = models.DecimalField(
        _("الهدف الافتراضيّ"), max_digits=12, decimal_places=2,
        null=True, blank=True)

    state = models.CharField(_("الحالة"), max_length=12,
                             choices=ApprovalState.choices,
                             default=ApprovalState.DRAFT, db_index=True)
    approved_by_person_id = models.BigIntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    created_by_employment_id = models.BigIntegerField(null=True,
                                                      blank=True)
    is_active = models.BooleanField(_("مفعّل"), default=True)

    class Meta:
        verbose_name = _("مؤشّر أداء")
        verbose_name_plural = _("مؤشّرات الأداء")
        ordering = ["department", "name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_kpi_company_code"),
        ]
        indexes = [
            models.Index(fields=["company", "state"],
                         name="idx_kpi_company_state"),
        ]

    def __str__(self):
        return self.name_ar

    @property
    def is_usable(self):
        """⚠️ **المعتمَد وحده يُقاس به**."""
        return self.state == ApprovalState.APPROVED and self.is_active


class KPIAssignment(CompanyScopedModel):
    """
    مؤشّرٌ مُسنَدٌ لموظفٍ في دورةٍ — بهدفه ووزنه.

    ⚠️ **ومجموع الأوزان ١٠٠**: فوزنٌ ناقص يُظلم صاحبه، وزائدٌ
    يُجمّل نتيجته.
    """
    cycle = models.ForeignKey(
        ReviewCycle, on_delete=models.CASCADE,
        related_name="assignments", verbose_name=_("الدورة"))
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="kpi_assignments", verbose_name=_("الموظف"))
    kpi = models.ForeignKey(
        KPI, on_delete=models.PROTECT, related_name="assignments",
        verbose_name=_("المؤشّر"))

    target = models.DecimalField(
        _("المستهدَف"), max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)])
    weight = models.PositiveSmallIntegerField(
        _("الوزن %"), validators=[MinValueValidator(1)])

    # ── الفعليّ ──
    actual = models.DecimalField(
        _("الفعليّ"), max_digits=12, decimal_places=2,
        null=True, blank=True)
    entered_by_employment_id = models.BigIntegerField(null=True,
                                                      blank=True)
    entered_at = models.DateTimeField(null=True, blank=True)
    entry_note = models.CharField(_("ملاحظة الإدخال"), max_length=255,
                                  blank=True)

    # ── اعتماد الموارد ──
    #
    # ⚠️ **فالمدخَل لا يصير نتيجةً قبل مراجعته**.
    state = models.CharField(_("الحالة"), max_length=12,
                             choices=ApprovalState.choices,
                             default=ApprovalState.DRAFT, db_index=True)
    approved_by_person_id = models.BigIntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _("إسناد مؤشّر")
        verbose_name_plural = _("إسنادات المؤشّرات")
        ordering = ["cycle", "employment", "id"]
        constraints = [
            models.UniqueConstraint(fields=["cycle", "employment", "kpi"],
                                    name="uq_kpiassign_cycle_emp_kpi"),
        ]
        indexes = [
            models.Index(fields=["company", "state"],
                         name="idx_kpiassign_state"),
            models.Index(fields=["employment", "cycle"],
                         name="idx_kpiassign_emp_cycle"),
        ]

    def __str__(self):
        return f"{self.employment_id} — {self.kpi_id}"

    @property
    def score(self):
        """
        درجةُ المؤشّر من ١٠٠ — **بحسب مقياسه واتجاهه**.

        ⚠️ **والأقلّ أفضل يُقلب**: فمؤشّر «نسبة الأخطاء» يُقاس
        عكسًا، وحسابُه كغيره يقلب المعنى.
        """
        from decimal import Decimal

        if self.actual is None or not self.target:
            return None

        if self.kpi.scale == KPIScale.SCALE_5:
            raw = (self.actual / Decimal("5")) * Decimal("100")
        else:
            raw = (self.actual / self.target) * Decimal("100")

        if self.kpi.direction == KPIDirection.LOWER:
            if self.kpi.scale == KPIScale.SCALE_5:
                raw = Decimal("100") - raw
            else:
                raw = (self.target / max(self.actual, Decimal("0.01"))
                       ) * Decimal("100")

        return min(max(raw, Decimal("0")), Decimal("150"))


class ReviewKind(models.TextChoices):
    SELF = "self", _("تقييم ذاتيّ")
    UPWARD = "upward", _("تقييم المدير")


class PeerReview(CompanyScopedModel):
    """
    تقييمٌ ذاتيّ أو تقييمٌ للمدير.

    ⚠️⚠️ **وتقييم المدير مجهولٌ دائمًا**: لا يُحفظ اسم صاحبه في
    الجدول — **فلو رآه المدير باسمه لم يصدق أحد** (قرار جواد).

    والذاتيّ منسوبٌ لصاحبه، فهو عن نفسه.
    """
    cycle = models.ForeignKey(
        ReviewCycle, on_delete=models.CASCADE,
        related_name="peer_reviews")
    kind = models.CharField(_("النوع"), max_length=10,
                            choices=ReviewKind.choices)

    #: ⚠️ **للذاتيّ وحده** — والمجهول يتركه فارغًا
    author_employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="authored_reviews", null=True, blank=True,
        verbose_name=_("المقيِّم"))
    #: من يُقيَّم — الموظف نفسه، أو مديره
    subject_employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="received_reviews", verbose_name=_("المُقيَّم"))

    #: بصمةٌ تمنع التكرار بلا كشف الهوية
    #
    # ⚠️ **فبلا هذا يُقيَّم المدير مرّاتٍ من شخصٍ واحد** — والبصمة
    # تُطابق ولا تُفكّ.
    author_fingerprint = models.CharField(max_length=64, blank=True,
                                          db_index=True)

    score = models.PositiveSmallIntegerField(
        _("التقدير من ٥"), validators=[MinValueValidator(1)])
    strengths = models.TextField(_("نقاط القوّة"), blank=True)
    improvements = models.TextField(_("ما يُحسَّن"), blank=True)
    comment = models.TextField(_("ملاحظات"), blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("تقييم")
        verbose_name_plural = _("التقييمات")
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["cycle", "subject_employment", "kind"],
                         name="idx_peerreview_cycle_subj"),
        ]

    def __str__(self):
        return f"{self.kind} → {self.subject_employment_id}"


class BehaviorRating(CompanyScopedModel):
    """
    تقديرٌ سلوكيّ من المشرف — بجانب الأرقام.

    فالتزامٌ وتعاونٌ ومبادرةٌ لا تُقاس بمؤشّرٍ كمّيّ.
    """
    cycle = models.ForeignKey(
        ReviewCycle, on_delete=models.CASCADE,
        related_name="behavior_ratings")
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="behavior_ratings")
    kpi = models.ForeignKey(
        KPI, on_delete=models.PROTECT,
        related_name="behavior_ratings",
        limit_choices_to={"kind": KPIKind.BEHAVIORAL})

    score = models.PositiveSmallIntegerField(
        _("التقدير من ٥"), validators=[MinValueValidator(1)])
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)
    rated_by_employment_id = models.BigIntegerField(null=True, blank=True)
    rated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("تقدير سلوكيّ")
        verbose_name_plural = _("التقديرات السلوكية")
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "employment", "kpi"],
                name="uq_behavior_cycle_emp_kpi"),
        ]

    def __str__(self):
        return f"{self.employment_id} — {self.kpi_id}"
