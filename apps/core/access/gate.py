"""
بوابة الصلاحيات المركزية.

قاعدة حاكمة: كل قراءة في النظام تمر بـGate.filter_queryset.
ممنوع Model.objects.filter() خامًا في أي view — اختبار CI يفرض ذلك.

البوابات الثلاث (الوثيقة المعمارية 3 القسم 2):
  1. الميزة (الباقة)    ← لاحقًا في السبرنت 4
  2. الصلاحية (الدور)   ← هنا
  3. النطاق (البيانات)  ← هنا + RLS
"""
from dataclasses import dataclass

from apps.core.access.catalog import PERMISSION_KEYS, Scope


class UnknownPermission(ValueError):
    """مفتاح غير مسجّل في الكتالوج — خطأ برمجي لا حالة تشغيل."""


class AmbiguousScopePath(ValueError):
    """أكثر من مسار محتمل للنطاق — خطأ برمجي يُكشف عند التطوير."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    scope: Scope
    reason: str = ""

    def __bool__(self):
        return self.allowed


# الصلاحية ونظيرتها الشاملة — من ملك الثانية تجاوز نطاق دوره
_WIDE_TWIN = {
    "employees.view": "employees.view_all",
    "attendance.view": "attendance.view_all",
    "leaves.view": "leaves.view_all",
    "leaves.approve": "leaves.approve_all",
    "requests.view": "requests.view_all",
    "requests.approve": "requests.approve_all",
}


def _delegated_manager_ids(employment):
    """
    من ينوب عنهم هذا الموظف اليوم (ق-75).

    تُقرأ عند كل فلترة نطاق team، فالإنابة تبدأ وتنتهي بتاريخها
    بلا تفعيل يدوي — والقراءة رخيصة (فهرس على deputy وstatus).
    """
    try:
        from apps.leaves.services.delegation import active_delegations_for
    except Exception:      # noqa: BLE001 — أثناء الهجرات قد لا يتوفر
        return []
    return [d.absentee_id for d in active_delegations_for(employment)]


#: ق-160: **افتراض صلاحيات مدير الإدارة** — والعميل يزيد وينقص.
#
# ⚠️ **فمطاردةُ كل احتمالٍ عبث**: والعميل يريد نظامه الداخليّ لا
# رغبتنا (قرار جواد).
#
# ⚠️⚠️ **والضمانة في النطاق لا في القائمة**: فمهما مُنح يُطبَّق
# **على فريقه وحده** — ومن مُنح `payroll.view` رأى رواتب فريقه لا
# الشركة.
DEFAULT_DEPT_MANAGER_PERMISSIONS = (
    "employees.view",
    "attendance.view",
    "leaves.view",
    "requests.view",
    "requests.approve",
    "requests.manage",
)


def dept_manager_permissions(company_id):
    """
    صلاحيات مدير الإدارة في هذه الشركة.

    ⚠️ **وفارغٌ يعني الافتراض** لا «بلا شيء»: فشركةٌ لم تضبطه
    **يبقى مديرها بلا صلاحية** — وذاك ليس ما أرادت.
    """
    from apps.accounts.models import Company
    from apps.core.access.catalog import PERMISSION_KEYS

    c = Company.objects.filter(id=company_id).only(
        "dept_manager_permissions").first()
    raw = (c.dept_manager_permissions if c else None) or None
    keys = raw or DEFAULT_DEPT_MANAGER_PERMISSIONS
    # ⚠️ **ومفتاحٌ مخترَع يُسقط**: فالكتالوج يرفعه استثناءً
    return frozenset(k for k in keys if k in PERMISSION_KEYS)


class Gate:
    """نقطة الفحص الوحيدة. لا يُفحص أي صلاحية خارجها."""

    @staticmethod
    def _membership(user):
        return getattr(user, "account_membership", None)

    @classmethod
    def _employment(cls, user):
        """
        الارتباط الوظيفي الحاكم للنطاق — في الشركة النشطة تحديدًا.

        العضوية تربط المستخدم بالحساب لا بملف موظف، فالارتباط
        يُجلب عبر الشخص. والشخص قد يعمل في أكثر من شركة بالحساب
        بمنصبين مختلفين — فنطاقه يتبع شركته النشطة لا أول ارتباط
        يُصادَف، ولا أوسع نطاق بين شركتيه.
        """
        membership = cls._membership(user)
        if membership is None or membership.active_company_id is None:
            return None
        person = getattr(user, "person", None)
        if person is None:
            return None
        from apps.employees.models import Employment, EmploymentStatus
        return Employment.objects.filter(
            person=person,
            company_id=membership.active_company_id,
            status=EmploymentStatus.ACTIVE,
        ).first()

    @classmethod
    def check(cls, user, permission_key: str) -> Decision:
        if permission_key not in PERMISSION_KEYS:
            raise UnknownPermission(
                f"صلاحية غير مسجّلة في الكتالوج: {permission_key}"
            )

        if not user or not getattr(user, "is_authenticated", False):
            return Decision(False, Scope.OWN, "غير مسجّل دخول")

        membership = cls._membership(user)
        if membership is None:
            return Decision(False, Scope.OWN, "لا عضوية في أي حساب")

        # مالك الحساب يتجاوز فحص الصلاحيات — داخل حسابه فقط.
        # العزل بين الحسابات يبقى مفروضًا بـRLS ولا يتجاوزه أحد.
        if membership.is_account_owner:
            return Decision(True, Scope.ACCOUNT, "مالك الحساب")

        # الاستثناء الشخصي يعلو على الدور (ق-67): مدير الحساب
        # يزيد أو ينقص لموظف بعينه بلا تغيير دوره.
        override = cls._override(membership, permission_key)
        if override is not None and not override.granted:
            return Decision(False, Scope.OWN, "منزوعة باستثناء شخصي")

        # ⚠️ ق-114: الدور يخصّ شركةً بعينها — والقراءة بلا ترشيح
        # تمنح صاحبَ دورٍ عالٍ في شركة صلاحياتِه في الشركات كلّها.
        # فمن هو «مدير موارد» في واحدة و«موظف» في أخرى كان يحمل
        # صلاحيات المدير فيهما.
        #
        # والدور بلا شركة (company_id=None) عامٌّ على الحساب —
        # كنمط الاستثناءات الشخصية أدناه.
        active = membership.active_company_id
        best = None
        for assignment in cls._active_assignments(membership):
            if permission_key not in assignment.role.permission_keys:
                continue
            scope = Scope(assignment.scope)
            if best is None or scope.rank > best.rank:
                best = scope

        if override is not None and override.granted:
            granted = Scope(override.scope) if override.scope else Scope.OWN
            if best is None or granted.rank > best.rank:
                best = granted

        # ق-160: ⚠️⚠️ **ومديرُ الإدارة يكتسب صلاحيات فريقه**
        # (قرار جواد): فإسنادُه مديرًا **قرارٌ تنظيميّ يحمل أثره**.
        #
        # ⚠️ **ونطاقها `team` دائمًا**: فهي على فريقه وحده — وهذه
        # هي الضمانة، لا حصرُ القائمة.
        if (active
                and permission_key in dept_manager_permissions(active)
                and cls._leads_a_department(membership)):
            team = Scope.TEAM
            if best is None or team.rank > best.rank:
                best = team

        if best is None:
            return Decision(False, Scope.OWN, "لا دور يمنح هذه الصلاحية")
        return Decision(True, best)

    @classmethod
    def _leads_a_department(cls, membership):
        """
        أيدير إدارةً؟

        ⚠️ **فالإسناد قرارٌ تنظيميّ يحمل أثره** — ومن أُسنِد
        مديرًا بلا صلاحية لا يرى من يديرهم (قرار جواد).
        """
        from apps.employees.models import Employment, EmploymentStatus
        from apps.organization.models import Department

        person = getattr(membership.user, "person", None)
        company_id = membership.active_company_id
        if person is None or company_id is None:
            return False

        mine = list(Employment.objects.filter(
            person=person, company_id=company_id,
            status=EmploymentStatus.ACTIVE).values_list("id", flat=True))
        if not mine:
            return False

        return Department.objects.filter(
            company_id=company_id,
            manager_employment_id__in=mine).exists()

    @classmethod
    def _override(cls, membership, permission_key):
        """
        استثناء هذه الصلاحية لهذه العضوية — أو None.

        الاستثناء المقيّد بشركة يسبق العام، فالشركة أخصّ.
        """
        rows = [
            o for o in membership.permission_overrides.all()
            if o.permission_key == permission_key
            and o.company_id in (None, membership.active_company_id)
        ]
        if not rows:
            return None
        rows.sort(key=lambda o: (o.company_id is None))
        return rows[0]

    @classmethod
    def require(cls, user, permission_key: str) -> Decision:
        """يرفع استثناءً بدل إرجاع قرار — للاستخدام في الخدمات."""
        from rest_framework.exceptions import PermissionDenied
        d = cls.check(user, permission_key)
        if not d.allowed:
            raise PermissionDenied(f"صلاحية مطلوبة: {permission_key} — {d.reason}")
        return d

    @classmethod
    def filter_queryset(cls, user, permission_key: str, qs, *, employment_field=None):
        """
        الفلترة الداخلية — الأمان الحقيقي.

        إخفاء الأزرار في الواجهة تجميل؛ الحماية الفعلية هنا وفي RLS.
        employment_field: مسار حقل الارتباط الوظيفي للتضييق حسب النطاق.
        """
        d = cls.check(user, permission_key)

        # المدى في اسم الصلاحية لا في نطاق خفيّ (ق-78):
        # من يملك «عرض كل موظفي المنشأة» يراهم كلهم مهما كان دوره،
        # فالمدير يقرأ الجملة ويعرف ما يمنحه بلا خطوة ثانية.
        wide = _WIDE_TWIN.get(permission_key)
        if wide and cls.check(user, wide).allowed:
            return qs

        if not d.allowed:
            return qs.none()

        if d.scope in (Scope.ACCOUNT, Scope.COMPANY):
            # RLS يتكفّل بالحدّين: الحساب مطلق، والشركة ضمن company_ids
            return qs

        emp = cls._employment(user)
        if emp is None:
            # لا ارتباط وظيفي: النطاقات الضيّقة بلا معنى → لا شيء
            return qs.none()

        prefix = cls._scope_prefix(qs, employment_field)
        if prefix is None:
            # جدول تنظيمي لا يخص موظفًا (الأقسام، الفروع، الأدوار،
            # قوالب البنوك...). النطاق الضيّق بلا معنى عليه،
            # والصلاحية وحدها حارسه.
            return qs

        if d.scope is Scope.BRANCH:
            return qs.filter(**{f"{prefix}branch_id": emp.branch_id})
        if d.scope is Scope.DEPARTMENT:
            # ق-159: ⚠️⚠️ **وإداراتُه التي يديرها معها** (قرار
            # جواد): فمن أُسند مديرًا لإدارةٍ **يرى موظفيها** ولو
            # لم تكن إدارته هو — **وبلا هذا يُسنَد مديرًا ولا يرى
            # أحدًا**.
            #
            # ⚠️ **والمدير المباشر شيءٌ آخر**: قد يكون المشرف لا
            # مدير الإدارة.
            dept_ids = cls._managed_department_ids(emp)
            return qs.filter(**{f"{prefix}department_id__in": dept_ids})
        if d.scope is Scope.TEAM:
            # ق-75: النائب يرى مرؤوسي من ينوب عنه — طوال المدة
            # المقبولة لا قبلها ولا بعدها. فالإنابة تنقل المهام
            # فعلًا، ولا معنى لقبولها إن بقي الفريق محجوبًا.
            managers = [emp.id] + _delegated_manager_ids(emp)
            return qs.filter(
                **{f"{prefix}direct_manager_id__in": managers})
        return qs.filter(**{f"{prefix}id": emp.id})

    @classmethod
    def _managed_department_ids(cls, emp):
        """
        إدارات الموظف: إدارتُه هو **وما يديره**.

        ⚠️ **فمديرُ إدارةٍ غير إدارته يراها** — وبلا هذا يُسنَد
        مديرًا ولا يصل موظفيه (قرار جواد).
        """
        from apps.organization.models import Department

        ids = {emp.department_id} if emp.department_id else set()
        ids |= set(Department.objects.filter(
            manager_employment_id=emp.id).values_list("id", flat=True))
        return list(ids) or [-1]

    # الحقول التي يُفلتر بها النطاق مباشرة على Employment
    _SCOPE_FIELDS = ("branch", "department", "direct_manager")

    @classmethod
    def _scope_prefix(cls, qs, employment_field):
        """
        يحدد المسار الذي يُطبَّق عليه النطاق.

        ثلاث حالات:
          • مُرِّر employment_field صراحةً → يُستخدم كما هو
          • الجدول هو Employment نفسه → بلا بادئة
          • الجدول يرتبط بـEmployment → تُشتق البادئة منه

        وما لا ينطبق عليه شيء من ذلك جدول تنظيمي، فيُرجَع None
        ويمرّ بلا فلترة نطاق.

        سبب الاشتقاق: مطالبة كل مستدعٍ بتمرير الحقل تعني أن نسيانه
        يرفع FieldError غامضًا من أعماق Django عند العميل. والنظام
        يحتسب ما يستطيع احتسابه.
        """
        if employment_field:
            return f"{employment_field}__"

        model = qs.model
        names = {f.name for f in model._meta.get_fields()}

        # الجدول نفسه يحمل حقول النطاق (Employment)
        if all(n in names for n in cls._SCOPE_FIELDS):
            return ""

        # علاقة واحدة صريحة بـEmployment — والوصفية تُستثنى.
        #
        # فحقل «مدير الموقع» يصف الموقع ولا يحدّد من يراه: اشتقاقه
        # كمسار نطاق جعل مدير الإدارة يرى المواقع التي هو مديرها
        # وحدها، وهي صفر.
        from apps.employees.models import Employment
        DESCRIPTIVE = {"site_manager", "manager_employment",
                       "created_by", "updated_by", "approved_by",
                       "adjusted_by", "uploaded_by", "direct_manager"}
        links = [
            f.name for f in model._meta.get_fields()
            if getattr(f, "many_to_one", False)
            and getattr(f, "related_model", None) is Employment
            and f.name not in DESCRIPTIVE
        ]
        if len(links) == 1:
            return f"{links[0]}__"
        if len(links) > 1:
            raise AmbiguousScopePath(
                f"{model.__name__} يرتبط بـEmployment بأكثر من مسار "
                f"({', '.join(links)}) — مرّر employment_field صراحةً"
            )
        return None

    @classmethod
    def _active_assignments(cls, membership):
        """
        إسنادات الدور السارية في الشركة النشطة (ق-115).

        **الدور على التوظيف**: من يعمل في شركتين له توظيفان
        فدوران مستقلّان، والشركة تأتي من التوظيف نفسه.

        ⚠️ **والتوظيف المنتهي لا يمنح شيئًا**: من أُنهيت خدمته
        تُنزع صلاحياته فورًا بلا تدخّل.

        والإسناد بلا توظيف (مالك الحساب قبل أن يُضيف نفسه) يبقى
        على العضوية، ويُرشَّح بحقل الشركة كالسابق.
        """
        from apps.employees.models import EmploymentStatus

        active = membership.active_company_id
        out = []
        for a in membership.role_assignments.select_related(
                "role", "employment"):
            emp = a.employment
            if emp is not None:
                if emp.status != EmploymentStatus.ACTIVE:
                    continue
                if emp.company_id != active:
                    continue
            elif a.company_id not in (None, active):
                continue
            out.append(a)
        return out

    @classmethod
    def accessible_permissions(cls, user) -> set:
        """كل الصلاحيات الفعّالة — تُستخدم في /me/workspace."""
        membership = cls._membership(user)
        if membership is None:
            return set()
        if membership.is_account_owner:
            return set(PERMISSION_KEYS)
        keys = set()
        for a in cls._active_assignments(membership):
            keys |= a.role.permission_keys

        # الاستثناءات الشخصية (ق-67) — تُضاف وتُنزع بعد الدور
        for o in membership.permission_overrides.all():
            if o.company_id not in (None, membership.active_company_id):
                continue
            if o.granted:
                keys.add(o.permission_key)
            else:
                keys.discard(o.permission_key)

        # ق-160: ⚠️ **وصلاحيات مدير الإدارة** — وإلا ظهر البند في
        # القائمة وحُجب عند الفتح، أو العكس.
        if membership.active_company_id and cls._leads_a_department(
                membership):
            keys |= dept_manager_permissions(
                membership.active_company_id)
        return keys
