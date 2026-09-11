"""
السياسات وإقرار الموظفين بها (ق-129).

⚠️ **سياسةٌ بلا إقرارٍ موثَّق لا يُحتجّ بها**: المنشأة تقول «نبّهنا»
والموظف يقول «لم أعلم» — والإقرار بختم وقته هو الحجّة.

**والنسخة الجديدة تُبطل الإقرار القديم**: من أقرّ بنسخةٍ لا يُعدّ
مُقرًّا بما عُدّل بعدها.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class PolicyAudience(models.TextChoices):
    ALL = "all", _("جميع الموظفين")
    DEPARTMENT = "department", _("إدارة بعينها")
    BRANCH = "branch", _("فرع بعينه")


class Policy(CompanyScopedModel):
    """
    سياسةٌ تكتبها الشركة وتنشرها لفئة.

    ⚠️ **والنسخة رقمٌ يتغيّر بالتعديل الجوهريّ** — لا بكل حفظ.
    فرفعها يُبطل الإقرارات، وتصحيحُ حرفٍ لا يستحقّ إعادة توقيع
    المنشأة كلّها.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    title_ar = models.CharField(_("العنوان"), max_length=200)
    title_en = models.CharField(_("بالإنجليزية"), max_length=200, blank=True)
    body_ar = models.TextField(_("النصّ"))

    version = models.PositiveSmallIntegerField(_("النسخة"), default=1)
    effective_from = models.DateField(_("سريان من"))

    audience = models.CharField(
        _("الفئة"), max_length=20, choices=PolicyAudience.choices,
        default=PolicyAudience.ALL)
    department_id = models.BigIntegerField(null=True, blank=True)
    branch_id = models.BigIntegerField(null=True, blank=True)

    requires_ack = models.BooleanField(
        _("يلزمه إقرار"), default=True,
        help_text=_("مطفأ = تُنشر للاطّلاع بلا توقيع"))

    is_published = models.BooleanField(_("منشورة"), default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("سياسة")
        verbose_name_plural = _("السياسات")
        ordering = ["-effective_from", "title_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_policy_company_code"),
        ]

    def __str__(self):
        return f"{self.title_ar} (v{self.version})"


class PolicyAcknowledgement(CompanyScopedModel):
    """
    إقرارُ موظفٍ بنسخةٍ من سياسة.

    ⚠️ **بالنسخة لا بالسياسة**: فمن أقرّ بالأولى لا يُعدّ مُقرًّا
    بالثانية — وإلا احتجّت المنشأة بتوقيعٍ على نصٍّ لم يره.

    ويُحفظ **ختم الوقت وعنوان الجهاز**: فالإقرار حجّةٌ تُراجَع.
    """
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name="acks",
        verbose_name=_("السياسة"))
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.CASCADE,
        related_name="policy_acks", verbose_name=_("الموظف"))

    version = models.PositiveSmallIntegerField(_("النسخة المقَرّ بها"))
    acknowledged_at = models.DateTimeField(_("وقت الإقرار"),
                                           auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = _("إقرار سياسة")
        verbose_name_plural = _("إقرارات السياسات")
        ordering = ["-acknowledged_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "employment", "version"],
                name="uq_ack_policy_emp_version"),
        ]

    def __str__(self):
        return f"إقرار {self.employment_id} — {self.policy_id} v{self.version}"
