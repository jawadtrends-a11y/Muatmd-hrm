"""
الهيكل التنظيمي: الفروع، الأقسام، مراكز التكلفة، المسميات، العطل.

ملاحظات نظامية:
  • كل فرع قد يكون منشأة مستقلة في قوى والتأمينات — لذلك يحمل
    أرقامه الخاصة، وهذا ما يجعل نطاقات تُحتسب لكل منشأة على حدة.
  • المسمى الوظيفي يحمل الرمز المهني المعتمد — أساس التوطين.

قرار المالك (محسوم): العطل تديرها الشركة وحدها. لا جدول عطل على
مستوى المنصة، ولا اقتراحات من السوبر أدمن، ولا استيراد. قرار
الشركة في عطلها مستقل تمامًا.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import CompanyScopedModel


class Branch(CompanyScopedModel):
    """فرع — قد يكون منشأة مستقلة نظاميًا."""

    code = models.CharField(_("الرمز"), max_length=30)
    name_ar = models.CharField(_("الاسم"), max_length=150)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=150, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=150, blank=True)
    city = models.CharField(_("المدينة"), max_length=80, blank=True)
    address = models.TextField(_("العنوان"), blank=True)

    mol_establishment_no = models.CharField(
        _("رقم منشأة قوى"), max_length=20, blank=True,
        help_text=_("إن كان الفرع منشأة مستقلة — يؤثر على احتساب نطاقات"))
    gosi_establishment_no = models.CharField(
        _("رقم منشأة التأمينات"), max_length=20, blank=True)

    is_active = models.BooleanField(_("نشط"), default=True, db_index=True)

    class Meta:
        verbose_name = _("فرع")
        verbose_name_plural = _("الفروع")
        ordering = ["name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_branch_code_per_company"),
        ]

    def __str__(self):
        return self.name_ar


class Department(CompanyScopedModel):
    """قسم — شجرة بعمق غير محدود."""

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT,
                               null=True, blank=True,
                               related_name="departments",
                               verbose_name=_("الفرع"))
    parent = models.ForeignKey("self", on_delete=models.PROTECT,
                               null=True, blank=True,
                               related_name="children",
                               verbose_name=_("القسم الأعلى"))
    code = models.CharField(_("الرمز"), max_length=30)
    name_ar = models.CharField(_("الاسم"), max_length=150)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=150, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=150, blank=True)

    # مسار الشجرة "1/5/12" — يجلب كل الفروع باستعلام واحد
    path = models.CharField(_("المسار"), max_length=255, blank=True, db_index=True)
    depth = models.PositiveSmallIntegerField(_("العمق"), default=0)

    manager_employment_id = models.BigIntegerField(
        _("مدير القسم"), null=True, blank=True,
        help_text=_("يُربط بنموذج Employment في السبرنت 7"))
    is_active = models.BooleanField(_("نشط"), default=True, db_index=True)

    class Meta:
        verbose_name = _("قسم")
        verbose_name_plural = _("الأقسام")
        ordering = ["path", "name_ar"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_department_code_per_company"),
        ]

    def __str__(self):
        return self.name_ar

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        new_path = f"{self.parent.path}/{self.id}" if self.parent else str(self.id)
        new_depth = (self.parent.depth + 1) if self.parent else 0
        if self.path != new_path or self.depth != new_depth:
            Department.objects.filter(pk=self.pk).update(
                path=new_path, depth=new_depth)
            self.path, self.depth = new_path, new_depth

    @property
    def descendants(self):
        return Department.objects.filter(path__startswith=f"{self.path}/")


class CostCenter(CompanyScopedModel):
    code = models.CharField(_("الرمز"), max_length=30)
    name_ar = models.CharField(_("الاسم"), max_length=150)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=150, blank=True)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("مركز تكلفة")
        verbose_name_plural = _("مراكز التكلفة")
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code"],
                                    name="uq_costcenter_code_per_company"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name_ar}"


class JobTitle(CompanyScopedModel):
    """مسمى وظيفي بالرمز المهني — أساس احتساب التوطين."""

    name_ar = models.CharField(_("المسمى"), max_length=150)
    name_en = models.CharField(_("المسمى بالإنجليزية"), max_length=150, blank=True)
    name_ur = models.CharField(_("المسمى بالأوردو"), max_length=150, blank=True)
    mol_occupation_code = models.CharField(
        _("الرمز المهني"), max_length=20, blank=True, db_index=True,
        help_text=_("الرمز المعتمد لدى وزارة الموارد البشرية"))
    is_saudization_reserved = models.BooleanField(
        _("مقصورة على السعوديين"), default=False)
    is_active = models.BooleanField(_("نشط"), default=True)

    class Meta:
        verbose_name = _("مسمى وظيفي")
        verbose_name_plural = _("المسميات الوظيفية")
        ordering = ["name_ar"]

    def __str__(self):
        return self.name_ar


class Holiday(CompanyScopedModel):
    """
    عطلة — تديرها الشركة بالكامل.

    قرار المالك: لا تدخّل من المنصة إطلاقًا. الشركة تنشئ عطلها
    وتحدد تواريخها ومددها بحرية كاملة، بما فيها عطل الأعياد.
    """

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE,
                               null=True, blank=True, related_name="holidays",
                               verbose_name=_("الفرع"),
                               help_text=_("فارغ = كل الشركة"))
    name_ar = models.CharField(_("الاسم"), max_length=150)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=150, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=150, blank=True)
    start_date = models.DateField(_("من"), db_index=True)
    end_date = models.DateField(_("إلى"))
    is_paid = models.BooleanField(_("مدفوعة"), default=True)
    note = models.TextField(_("ملاحظة"), blank=True)

    class Meta:
        verbose_name = _("عطلة")
        verbose_name_plural = _("العطل")
        ordering = ["start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="chk_holiday_dates"),
        ]

    def __str__(self):
        return f"{self.name_ar} ({self.start_date})"

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1
