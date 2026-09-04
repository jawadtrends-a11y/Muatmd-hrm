"""
الأدوار وعضوية المستخدمين.

الصلاحيات ثابتة في الكتالوج، والأدوار بيانات مرنة يضبطها العميل.
راجع الوثيقة المعمارية (2) القسم 6.
"""
from django.conf import settings
from django.db import models

from apps.core.models import CompanyScopedModel
from django.utils.translation import gettext_lazy as _

from apps.core.access.catalog import Scope


class RoleCode(models.TextChoices):
    OWNER           = "owner",           _("مالك الحساب")
    CEO             = "ceo",             _("المدير العام")
    HR_MANAGER      = "hr_manager",      _("مدير الموارد البشرية")
    HR_STAFF        = "hr_staff",        _("موظف موارد بشرية")
    DEPT_MANAGER    = "dept_manager",    _("مدير إدارة")
    SUPERVISOR      = "supervisor",      _("مشرف")
    EMPLOYEE        = "employee",        _("موظف")


class ApproverScope(CompanyScopedModel):
    """
    تخصيص أنواع الطلبات لمعتمِد بعينه (ق-74).

    فمدير الموارد قد يجعل موظفًا يعتمد الإجازات وآخر السلف —
    والدرجة تبقى واحدة في السلسلة.

    والطلب يظهر لكل من في الدرجة، والقرار لمن خُصّص له وحده:
    فالمتابعة حق الجميع، والقرار مسؤولية مَن كُلّف.

    وغياب التخصيص لا يعطّل: من لا تخصيص له يعتمد كل الأنواع —
    فالتخصيص استثناء لا شرط.
    """

    membership = models.ForeignKey(
        "accounts.AccountMembership", on_delete=models.CASCADE,
        related_name="approver_scopes", verbose_name=_("العضوية"))
    request_type = models.CharField(
        _("نوع الطلب"), max_length=30,
        help_text=_("رمز النوع كما في كتالوج الطلبات"))

    note = models.CharField(_("ملاحظة"), max_length=200, blank=True)
    created_by_person_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("تخصيص اعتماد")
        verbose_name_plural = _("تخصيصات الاعتماد")
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "company", "request_type"],
                name="uq_approver_scope"),
        ]
        indexes = [
            models.Index(fields=["company", "request_type"]),
        ]

    def __str__(self):
        return f"{self.membership_id} — {self.request_type}"


class Role(models.Model):
    """
    دور داخل حساب. الأدوار النظامية (account=NULL) قوالب مشتركة،
    ويمكن للعميل إنشاء أدوار خاصة به.
    """
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE,
        null=True, blank=True, related_name="roles",
        verbose_name=_("الحساب"),
        help_text=_("فارغ = دور نظامي مشترك"),
    )
    code = models.CharField(_("الرمز"), max_length=40)
    name_ar = models.CharField(_("الاسم"), max_length=120)
    name_en = models.CharField(_("الاسم بالإنجليزية"), max_length=120, blank=True)
    name_ur = models.CharField(_("الاسم بالأوردو"), max_length=120, blank=True)
    default_scope = models.CharField(
        _("النطاق الافتراضي"), max_length=20,
        choices=[(s.value, s.value) for s in Scope], default=Scope.OWN.value,
    )
    is_system = models.BooleanField(
        _("دور نظامي"), default=False,
        help_text=_("لا يُحذف ولا تُعدّل صلاحياته الأساسية"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("دور")
        verbose_name_plural = _("الأدوار")
        constraints = [
            models.UniqueConstraint(
                fields=["account", "code"], name="uq_role_code_per_account",
            ),
            models.UniqueConstraint(
                fields=["code"], condition=models.Q(account__isnull=True),
                name="uq_system_role_code",
            ),
        ]

    def __str__(self):
        return self.name_ar

    @property
    def permission_keys(self):
        return set(self.permissions.values_list("permission_key", flat=True))


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    permission_key = models.CharField(max_length=80)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission_key"], name="uq_role_permission",
            ),
        ]

    def __str__(self):
        return f"{self.role.code}: {self.permission_key}"


class AccountMembership(models.Model):
    """
    عضوية مستخدم في حساب — ما يقرأه AccountContextMiddleware.

    مستخدم واحد = حساب واحد. الوصول لعدة شركات يتم عبر
    company_ids داخل نفس الحساب، لا بعضويات متعددة.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="account_membership", verbose_name=_("المستخدم"),
    )
    account = models.ForeignKey(
        "accounts.Account", on_delete=models.CASCADE,
        related_name="memberships", verbose_name=_("الحساب"),
    )
    active_company = models.ForeignKey(
        "accounts.Company", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
        verbose_name=_("الشركة النشطة"),
    )
    is_founding_owner = models.BooleanField(
        _("المالك المؤسس"), default=False,
        help_text=_("أول مالك — لا تُنزع ملكيته إلا بحذفه نهائيًا "
                    "من الشركة، ويخلفه مالك آخر بنفس الحماية (ق-79)"))
    owner_since = models.DateTimeField(
        _("مالك منذ"), null=True, blank=True,
        help_text=_("ترتيب المنح — به يُعرف من يخلف المؤسس"))
    is_account_owner = models.BooleanField(
        _("مالك الحساب"), default=False,
        help_text=_("يتجاوز فحص الصلاحيات داخل حسابه"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("عضوية")
        verbose_name_plural = _("العضويات")

    def __str__(self):
        return f"{self.user} @ {self.account.slug}"

    @property
    def company_ids(self):
        """الشركات المصرّح بها — تُحقن في app.company_ids."""
        assignments = list(self.role_assignments.all())
        if any(a.scope == Scope.ACCOUNT.value for a in assignments) or self.is_account_owner:
            return list(self.account.companies.values_list("id", flat=True))
        ids = {a.company_id for a in assignments if a.company_id}
        if self.active_company_id:
            ids.add(self.active_company_id)
        return sorted(ids)


class RoleAssignment(models.Model):
    """إسناد دور لعضوية، بنطاق قد يضيّق النطاق الافتراضي للدور."""
    membership = models.ForeignKey(
        AccountMembership, on_delete=models.CASCADE, related_name="role_assignments",
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="assignments")
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE,
        null=True, blank=True, related_name="+",
        help_text=_("فارغ = يسري على كل شركات الحساب"),
    )
    scope = models.CharField(
        _("النطاق"), max_length=20,
        choices=[(s.value, s.value) for s in Scope],
    )
    scope_ref_id = models.BigIntegerField(
        null=True, blank=True,
        help_text=_("معرّف الفرع أو القسم عند تضييق النطاق"),
    )

    class Meta:
        verbose_name = _("إسناد دور")
        verbose_name_plural = _("إسنادات الأدوار")

    def __str__(self):
        return f"{self.membership} → {self.role.code} ({self.scope})"

class PermissionOverride(models.Model):
    """
    استثناء شخصي في الصلاحيات (ق-67).

    مدير الحساب يزيد أو ينقص صلاحيات **موظف بعينه** بلا تغيير دوره
    ولا التأثير على بقية أصحاب الدور نفسه. فالواقع المهني يكلّف
    موظفًا بمهمة إضافية بلا ترقية.

    والصلاحية الفعلية = صلاحيات الدور + الممنوح شخصيًا − المنزوع.

    والاستثناء يحمل نطاقًا لا صلاحية مجردة: منح employees.view بلا
    نطاق يُبقي الموظف على own فيرى نفسه فقط — أي منح بلا أثر.
    """

    membership = models.ForeignKey(
        AccountMembership, on_delete=models.CASCADE,
        related_name="permission_overrides",
    )
    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE,
        null=True, blank=True, related_name="+",
        help_text=_("فارغ = يسري على كل شركات الحساب"),
    )
    permission_key = models.CharField(_("الصلاحية"), max_length=60)
    granted = models.BooleanField(
        _("ممنوحة"), default=True,
        help_text=_("صح = تُضاف، خطأ = تُنزع ولو منحها الدور"),
    )
    scope = models.CharField(
        _("النطاق"), max_length=20,
        choices=[(s.value, s.value) for s in Scope],
        blank=True,
        help_text=_("عند المنح — يُهمل عند النزع"),
    )
    note = models.CharField(
        _("سبب الاستثناء"), max_length=200, blank=True,
        help_text=_("لماذا خُصّ هذا الموظف — للمراجعة لاحقًا"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("استثناء صلاحية")
        verbose_name_plural = _("استثناءات الصلاحيات")
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "company", "permission_key"],
                name="uq_override_per_member_company_perm",
            ),
        ]

    def __str__(self):
        sign = "+" if self.granted else "−"
        return f"{self.membership} {sign}{self.permission_key}"
