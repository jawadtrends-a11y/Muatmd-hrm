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


@dataclass(frozen=True)
class Decision:
    allowed: bool
    scope: Scope
    reason: str = ""

    def __bool__(self):
        return self.allowed


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

        best = None
        for assignment in membership.role_assignments.select_related("role"):
            if permission_key not in assignment.role.permission_keys:
                continue
            scope = Scope(assignment.scope)
            if best is None or scope.rank > best.rank:
                best = scope

        if best is None:
            return Decision(False, Scope.OWN, "لا دور يمنح هذه الصلاحية")
        return Decision(True, best)

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

        prefix = f"{employment_field}__" if employment_field else ""
        if d.scope is Scope.BRANCH:
            return qs.filter(**{f"{prefix}branch_id": emp.branch_id})
        if d.scope is Scope.DEPARTMENT:
            return qs.filter(**{f"{prefix}department_id": emp.department_id})
        if d.scope is Scope.TEAM:
            return qs.filter(**{f"{prefix}direct_manager_id": emp.id})
        return qs.filter(**{f"{prefix}id": emp.id})

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
        return keys
