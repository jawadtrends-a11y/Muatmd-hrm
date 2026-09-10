"""
قوالب الخطابات والشهادات (ق-128).

**الشركة تكتب قوالبها** — لا ننتظر منها طلبًا لكل صيغة، ولا هي
تنتظر منّا.

⚠️ **والمتغيّرات معلَنة لا حرّة**: قالبٌ يقرأ أي حقلٍ يكشف ما لا
يُكشف (رواتب غيره، بيانات محذوفة)، وينكسر كلّما تغيّر عمود. فكل
متغيّر يُعلَن بمصدره وصلاحيته — كنمط باني التقارير (ق-126).
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class LetterTemplate(CompanyScopedModel):
    """
    قالب خطابٍ تكتبه الشركة بمتغيّراته.

    ويُملأ ببيانات الموظف عند الإصدار، ويُصدَّر PDF بترويستها.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("اسم القالب"), max_length=150)
    name_en = models.CharField(_("بالإنجليزية"), max_length=150, blank=True)

    #: نصّ القالب بمتغيّراته {{employee_name}}
    body_ar = models.TextField(_("نصّ الخطاب"))
    body_en = models.TextField(_("النصّ بالإنجليزية"), blank=True)

    #: عنوان الخطاب المطبوع
    heading_ar = models.CharField(_("العنوان"), max_length=200, blank=True)
    #: «إلى من يهمّه الأمر» أو جهةٌ يحدّدها الطالب
    addressee_ar = models.CharField(_("موجّه إلى"), max_length=200,
                                    blank=True)

    #: ⚠️ متغيّرٌ حسّاس يلزمه إقرار الطالب — كالراتب
    includes_salary = models.BooleanField(
        _("يتضمّن الراتب"), default=False,
        help_text=_("الطالب يختار إظهاره — ولا يُظهر إلا بطلبه"))

    valid_days = models.PositiveSmallIntegerField(
        _("مدّة الصلاحية (يومًا)"), default=30)
    is_active = models.BooleanField(_("مفعّل"), default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("قالب خطاب")
        verbose_name_plural = _("قوالب الخطابات")
        ordering = ["sort_order", "name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_lettertpl_company_code"),
        ]

    def __str__(self):
        return self.name_ar


class IssuedLetter(CompanyScopedModel):
    """
    خطابٌ صدر — بنصّه المجمَّد ورقمه.

    ⚠️ **النصّ يُجمَّد عند الإصدار**: تعديل القالب بعده لا يغيّر
    ما بيد الموظف، ومن راجع بعد سنة يرى ما صدر فعلًا لا ما صار
    القالب عليه.
    """
    template = models.ForeignKey(
        LetterTemplate, on_delete=models.PROTECT,
        related_name="issued", verbose_name=_("القالب"))
    employment = models.ForeignKey(
        "employees.Employment", on_delete=models.PROTECT,
        related_name="letters", verbose_name=_("الموظف"))
    request_id = models.BigIntegerField(null=True, blank=True)

    letter_no = models.CharField(_("رقم الخطاب"), max_length=40, unique=True)
    heading_ar = models.CharField(_("العنوان"), max_length=200, blank=True)
    addressee_ar = models.CharField(_("موجّه إلى"), max_length=200,
                                    blank=True)
    body_ar = models.TextField(_("النصّ المجمَّد"))

    issued_on = models.DateField(_("تاريخ الإصدار"), db_index=True)
    valid_until = models.DateField(_("صالح حتى"), null=True, blank=True)
    issued_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("خطاب صادر")
        verbose_name_plural = _("الخطابات الصادرة")
        ordering = ["-issued_on", "-id"]
        indexes = [
            models.Index(fields=["employment", "issued_on"],
                         name="idx_letter_emp_date"),
        ]

    def __str__(self):
        return self.letter_no
