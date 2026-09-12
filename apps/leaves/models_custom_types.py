"""
أنواع الطلبات المخصّصة (ق-142).

**الشركة تُنشئ نوع طلبٍ بحقوله** — «طلب سيارة»، «طلب إعارة جهاز»،
«طلب تدريب». فلا تنتظر منّا نوعًا لكل حاجة.

⚠️ **والحقول حرّةٌ أو معلَنة بحسب النوع** (قرار جواد): فحقلٌ حرّ
يكفي لسؤالٍ نصّيّ، وحقلٌ معلَن يلزم حين يُبنى عليه أثر.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class FieldKind(models.TextChoices):
    TEXT = "text", _("نصّ قصير")
    TEXTAREA = "textarea", _("نصّ طويل")
    NUMBER = "number", _("رقم")
    DATE = "date", _("تاريخ")
    TIME = "time", _("وقت")
    BOOL = "bool", _("نعم / لا")
    SELECT = "select", _("اختيار من قائمة")
    ATTACHMENT = "attachment", _("مرفق")


class CustomRequestType(CompanyScopedModel):
    """
    نوع طلبٍ تُنشئه الشركة.

    ⚠️ **ولا أثر آليًّا له**: يُقدَّم ويُعتمد ويُوثَّق — فالأثر
    يحتاج كودًا، وادّعاؤه يبيع وهمًا.
    """
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("اسم الطلب"), max_length=120)
    name_en = models.CharField(_("بالإنجليزية"), max_length=120, blank=True)
    hint_ar = models.CharField(_("التوضيح"), max_length=255, blank=True)
    icon = models.CharField(max_length=30, blank=True)

    requires_attachment = models.BooleanField(
        _("يلزمه مرفق"), default=False)

    #: ⚠️ **مرّةً في اليوم؟** — كقاعدة ق-134
    daily_unique = models.BooleanField(
        _("مرّة واحدة في اليوم"), default=False,
        help_text=_("يمنع طلبين في يومٍ واحد — إلا إن رُفض الأول"))

    is_active = models.BooleanField(_("مفعّل"), default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("نوع طلب مخصّص")
        verbose_name_plural = _("أنواع الطلبات المخصّصة")
        ordering = ["sort_order", "name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_customreqtype_company_code"),
        ]

    def __str__(self):
        return self.name_ar


class CustomRequestField(CompanyScopedModel):
    """
    حقلٌ في نوعٍ مخصّص.

    **والخيارات نصٌّ مفصولٌ بفواصل** — فقائمةٌ صغيرة لا تستحقّ
    جدولًا.
    """
    request_type = models.ForeignKey(
        CustomRequestType, on_delete=models.CASCADE,
        related_name="fields", verbose_name=_("النوع"))

    key = models.CharField(
        _("المفتاح"), max_length=40,
        help_text=_("بالإنجليزية بلا مسافات — يُحفظ به في الطلب"))
    label_ar = models.CharField(_("التسمية"), max_length=120)
    kind = models.CharField(_("النوع"), max_length=15,
                            choices=FieldKind.choices,
                            default=FieldKind.TEXT)
    is_required = models.BooleanField(_("إلزاميّ"), default=True)
    options = models.CharField(
        _("الخيارات"), max_length=500, blank=True,
        help_text=_("للاختيار من قائمة — مفصولةٌ بفواصل"))
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("حقل طلب مخصّص")
        verbose_name_plural = _("حقول الطلبات المخصّصة")
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["request_type", "key"],
                                    name="uq_customreqfield_type_key"),
        ]

    def __str__(self):
        return f"{self.request_type_id} — {self.key}"

    @property
    def option_list(self):
        return [o.strip() for o in (self.options or "").split(",")
                if o.strip()]
