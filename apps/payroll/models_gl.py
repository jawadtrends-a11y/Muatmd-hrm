"""
القيد المحاسبيّ وتصديره (ق-152).

**لكل عميلٍ نظامه ودليل حساباته** — فالقيد عامٌّ وقالبُه يُخصَّص،
كقوالب البنوك.

⚠️⚠️ **ولا يُصدَّر قيدٌ غير متوازن**: فمدينٌ لا يساوي دائنًا
يُرفض في أيّ نظام محاسبيّ — **وتصديرُه يُضيّع وقت المحاسب في
البحث عن خطئنا**.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class GLGrouping(models.TextChoices):
    """
    مستوى تجميع القيد.

    ⚠️ **والموظف أدقّ لكنّه يُثقل**: مئة موظفٍ في عشرة بنود =
    ألف سطر. **والشركة أخفّ لكنّها تُضيّع التوزيع**.
    """
    COMPANY = "company", _("قيدٌ واحد للمسير")
    DEPARTMENT = "department", _("بالإدارة")
    COST_CENTER = "cost_center", _("بمركز التكلفة")
    EMPLOYEE = "employee", _("سطرٌ لكل موظف")


class GLAccountMap(CompanyScopedModel):
    """
    ربطُ بند أجرٍ بحسابيه.

    ⚠️ **وبندٌ بلا ربطٍ يُمنع التصدير**: فقيدٌ ناقصٌ أسوأ من قيدٍ
    لا يُصدَّر — والمحاسب يكتشفه بعد الترحيل.
    """
    component_code = models.CharField(_("رمز البند"), max_length=40)
    name_ar = models.CharField(_("البيان"), max_length=150, blank=True)

    debit_account = models.CharField(_("الحساب المدين"), max_length=40,
                                     blank=True)
    credit_account = models.CharField(_("الحساب الدائن"), max_length=40,
                                      blank=True)
    #: ⚠️ بنودٌ تُستثنى عمدًا — كتكلفة صاحب العمل إن رُحّلت بقيدٍ آخر
    is_excluded = models.BooleanField(_("مستثنى"), default=False)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("ربط حساب")
        verbose_name_plural = _("ربط الحسابات")
        ordering = ["component_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "component_code"],
                name="uq_glmap_company_code"),
        ]

    def __str__(self):
        return f"{self.component_code} → {self.debit_account}/{self.credit_account}"

    @property
    def is_ready(self):
        return self.is_excluded or bool(self.debit_account
                                        and self.credit_account)


class GLTemplate(CompanyScopedModel):
    """
    قالبُ تصديرٍ — **أعمدةٌ يرتّبها العميل**.

    فلكل نظامٍ محاسبيّ ترتيبُه وأسماء أعمدته.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("القالب"), max_length=120)
    target_system = models.CharField(
        _("النظام المستهدَف"), max_length=80, blank=True,
        help_text=_("أودو · SAP · مايكروسوفت — للتذكير لا للمنطق"))

    grouping = models.CharField(
        _("مستوى التجميع"), max_length=15,
        choices=GLGrouping.choices, default=GLGrouping.COMPANY)

    #: ترتيب الأعمدة وعناوينها — [{"field": "...", "header": "..."}]
    columns = models.JSONField(_("الأعمدة"), default=list)

    delimiter = models.CharField(_("الفاصل"), max_length=3, default=",")
    encoding = models.CharField(max_length=20, default="utf-8-sig")
    date_format = models.CharField(max_length=20, default="%Y-%m-%d")
    include_header = models.BooleanField(_("سطر العناوين"), default=True)

    is_active = models.BooleanField(_("مفعّل"), default=True)

    class Meta:
        verbose_name = _("قالب قيد محاسبيّ")
        verbose_name_plural = _("قوالب القيد المحاسبيّ")
        ordering = ["name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_gltemplate_company_code"),
        ]

    def __str__(self):
        return self.name_ar
