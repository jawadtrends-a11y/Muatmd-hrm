"""
توسعة ملف الموظف (ق-63).

**نضيف لا نعدّل** — ما بُني يبقى، والناقص يُضاف.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel, CompanyScopedModel


class RelationKind(models.TextChoices):
    SPOUSE = "spouse", _("زوج/زوجة")
    SON = "son", _("ابن")
    DAUGHTER = "daughter", _("ابنة")
    FATHER = "father", _("أب")
    MOTHER = "mother", _("أم")
    BROTHER = "brother", _("أخ")
    SISTER = "sister", _("أخت")
    OTHER = "other", _("أخرى")


class Dependent(AccountScopedModel):
    """
    تابع للموظف — **توثيق فقط** (ق-63).

    اسم وصلة قرابة ورقم هوية. لا احتساب مالي ولا ربط بالتأمين
    الطبي أو التذاكر — تلك تُبنى لاحقًا إن لزمت.
    """

    person = models.ForeignKey(
        "employees.Person", on_delete=models.CASCADE,
        related_name="dependents", verbose_name=_("الموظف"))

    full_name_ar = models.CharField(_("الاسم"), max_length=180)
    full_name_en = models.CharField(_("بالإنجليزية"), max_length=180,
                                    blank=True)
    relation = models.CharField(_("صلة القرابة"), max_length=20,
                                choices=RelationKind.choices)

    id_number = models.CharField(_("رقم الهوية"), max_length=20, blank=True)
    id_expiry_date = models.DateField(_("انتهاء الهوية"), null=True,
                                      blank=True)
    birth_date = models.DateField(_("تاريخ الميلاد"), null=True, blank=True)
    nationality_code = models.CharField(_("الجنسية"), max_length=2, blank=True)

    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("تابع")
        verbose_name_plural = _("التابعون")
        ordering = ["relation", "full_name_ar"]

    def __str__(self):
        return f"{self.full_name_ar} ({self.get_relation_display()})"


class EmergencyContact(AccountScopedModel):
    """رقم طوارئ — من يُتصل به عند الحاجة."""

    person = models.ForeignKey(
        "employees.Person", on_delete=models.CASCADE,
        related_name="emergency_contacts", verbose_name=_("الموظف"))

    full_name_ar = models.CharField(_("الاسم"), max_length=180)
    relation = models.CharField(_("الصلة"), max_length=60)
    mobile = models.CharField(_("الجوال"), max_length=20)
    phone = models.CharField(_("هاتف آخر"), max_length=20, blank=True)
    is_primary = models.BooleanField(_("الأساسي"), default=False)

    class Meta:
        verbose_name = _("رقم طوارئ")
        verbose_name_plural = _("أرقام الطوارئ")
        ordering = ["-is_primary", "full_name_ar"]

    def __str__(self):
        return f"{self.full_name_ar} — {self.relation}"


class JobGrade(CompanyScopedModel):
    """
    المرتبة الوظيفية — **اختيارية** (ق-63).

    تُملأ إن كانت الشركة تستخدم سلّمًا وظيفيًا، وتُترك فارغة
    إن لم تكن.
    """

    code = models.CharField(_("الرمز"), max_length=20)
    name_ar = models.CharField(_("الاسم"), max_length=120)
    name_en = models.CharField(_("بالإنجليزية"), max_length=120, blank=True)
    level = models.IntegerField(_("المستوى"), default=0)

    min_salary = models.DecimalField(
        _("أدنى راتب"), max_digits=12, decimal_places=2, null=True, blank=True)
    max_salary = models.DecimalField(
        _("أعلى راتب"), max_digits=12, decimal_places=2, null=True, blank=True)

    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("مرتبة وظيفية")
        verbose_name_plural = _("المراتب الوظيفية")
        ordering = ["level", "name_ar"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="uniq_job_grade"),
        ]

    def __str__(self):
        return self.name_ar


class JobStep(CompanyScopedModel):
    """الدرجة الوظيفية داخل المرتبة — اختيارية أيضًا."""

    grade = models.ForeignKey(
        JobGrade, on_delete=models.CASCADE, related_name="steps",
        verbose_name=_("المرتبة"))
    code = models.CharField(_("الرمز"), max_length=20)
    name_ar = models.CharField(_("الاسم"), max_length=120)
    step_number = models.IntegerField(_("رقم الدرجة"), default=0)
    salary = models.DecimalField(
        _("الراتب"), max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("درجة وظيفية")
        verbose_name_plural = _("الدرجات الوظيفية")
        ordering = ["step_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["grade", "code"], name="uniq_job_step"),
        ]

    def __str__(self):
        return f"{self.grade.name_ar} — {self.name_ar}"
