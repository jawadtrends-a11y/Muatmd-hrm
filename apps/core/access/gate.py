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

        best = None
        for assignment in membership.role_assignments.select_related("role"):
            if permission_key not in assignment.role.permission_keys:
                continue
            scope = Scope(assignment.scope)
            if best is None or scope.rank > best.rank:
                best = scope

        if override is not None and override.granted:
            granted = Scope(override.scope) if override.scope else Scope.OWN
            if best is None or granted.rank > best.rank:
                best = granted

        if best is None:
            return Decision(False, Scope.OWN, "لا دور يمنح هذه الصلاحية")
        return Decision(True, best)

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
            return qs.filter(**{f"{prefix}department_id": emp.department_id})
        if d.scope is Scope.TEAM:
            # ق-75: النائب يرى مرؤوسي من ينوب عنه — طوال المدة
            # المقبولة لا قبلها ولا بعدها. فالإنابة تنقل المهام
            # فعلًا، ولا معنى لقبولها إن بقي الفريق محجوبًا.
            managers = [emp.id] + _delegated_manager_ids(emp)
            return qs.filter(
                **{f"{prefix}direct_manager_id__in": managers})
        return qs.filter(**{f"{prefix}id": emp.id})

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

        # علاقة واحدة صريحة بـEmployment
        from apps.employees.models import Employment
        links = [
            f.name for f in model._meta.get_fields()
            if getattr(f, "many_to_one", False)
            and getattr(f, "related_model", None) is Employment
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
    def accessible_permissions(cls, user) -> set:
        """كل الصلاحيات الفعّالة — تُستخدم في /me/workspace."""
        membership = cls._membership(user)
        if membership is None:
            return set()
        if membership.is_account_owner:
            return set(PERMISSION_KEYS)
        keys = set()
        for a in membership.role_assignments.select_related("role"):
            keys |= a.role.permission_keys

        # الاستثناءات الشخصية (ق-67) — تُضاف وتُنزع بعد الدور
        for o in membership.permission_overrides.all():
            if o.company_id not in (None, membership.active_company_id):
                continue
            if o.granted:
                keys.add(o.permission_key)
            else:
                keys.discard(o.permission_key)
        return keys
