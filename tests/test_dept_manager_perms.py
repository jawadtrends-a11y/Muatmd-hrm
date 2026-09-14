"""
حرّاس صلاحيات مدير الإدارة (ق-160).

**سؤال جواد:** «ليش ما تكون المزايا متوازنة مع ما يختاره مدير
الحساب بدون مطاردة كل احتمال؟ — فالعميل يفضّل أن يكون محصورًا
بنظامه الداخليّ لا برغبتنا».

⚠️⚠️ **فالقائمة قابلةٌ للضبط، والضمانة في النطاق**: فمهما مُنح
مديرُ الإدارة، **يُطبَّق على فريقه وحده**.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.access.gate import (
    DEFAULT_DEPT_MANAGER_PERMISSIONS, Gate, dept_manager_permissions)
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.organization.models import Department
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="dmp-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        def hire(fn, ln, nid, mob, no, username, role_code):
            p, _ = create_person(
                account=acc, first_name_ar=fn, family_name_ar=ln,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("9000"))])
            u = User.objects.create_user(username=username, password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, employment=e,
                role=Role.objects.get(account=acc, code=role_code),
                company=comp, scope=Scope.OWN.value)
            return u, e

        # ⚠️ **موظفٌ عاديّ** — ثم نُسنده مديرًا لإدارة
        mgr_u, mgr_e = hire("ثامر", "الحارثي", "1066001100",
                            "0506601100", "M-1", "dmp.mgr", "employee")
        _, staff_e = hire("منى", "السالم", "1066002200",
                          "0506602200", "M-2", "dmp.staff", "employee")

        dept = Department.objects.create(
            account=acc, company=comp, code="OPS2", name_ar="التشغيل")
        staff_e.department = dept
        staff_e.save(update_fields=["department"])

        yield {"account_id": r.account_id, "comp": comp, "dept": dept,
               "mgr_user": mgr_u, "mgr_emp": mgr_e,
               "staff_emp": staff_e}


def _make_manager(env):
    env["dept"].manager_employment_id = env["mgr_emp"].id
    env["dept"].save(update_fields=["manager_employment_id"])


def test_plain_employee_has_no_team_permissions(env):
    """وموظفٌ عاديٌّ بلا إدارة لا يملك صلاحيات الفريق."""
    with account_scope(env["account_id"]):
        d = Gate.check(env["mgr_user"], "requests.approve")
        assert d.allowed is False, "مُنحت بلا إدارة"


def test_department_manager_gains_permissions(env):
    """
    ⚠️⚠️ الأهمّ: **ومديرُ الإدارة يكتسب صلاحيات فريقه** (قرار
    جواد).

    فإسنادُه مديرًا **قرارٌ تنظيميّ يحمل أثره** — ومن أُسنِد بلا
    صلاحية لا يرى من يديرهم.
    """
    with account_scope(env["account_id"]):
        _make_manager(env)
        for key in DEFAULT_DEPT_MANAGER_PERMISSIONS:
            d = Gate.check(env["mgr_user"], key)
            assert d.allowed is True, f"لم يكتسب {key}"


def test_gained_scope_is_team_only(env):
    """
    ⚠️⚠️ **والضمانة في النطاق لا في القائمة**: فمهما مُنح، يُطبَّق
    **على فريقه وحده** — ومديرُ قسمٍ لا يرى الشركة.
    """
    with account_scope(env["account_id"]):
        _make_manager(env)
        d = Gate.check(env["mgr_user"], "employees.view")
        assert d.allowed is True
        assert d.scope is Scope.TEAM, f"نطاقٌ أوسع: {d.scope}"


def test_company_can_extend_the_list(env):
    """
    ⚠️ **والعميل يزيد بحرّية** (قرار جواد): فشركةٌ بلا موظف موارد
    **تستأمن مديرها على ما تشاء** — ومطاردةُ كل احتمالٍ عبث.
    """
    with account_scope(env["account_id"]):
        _make_manager(env)
        assert Gate.check(env["mgr_user"], "payroll.view").allowed is False

        env["comp"].dept_manager_permissions = [
            "employees.view", "payroll.view"]
        env["comp"].save(update_fields=["dept_manager_permissions"])

        d = Gate.check(env["mgr_user"], "payroll.view")
        assert d.allowed is True, "لم تُطبَّق الزيادة"
        # ⚠️ **وبنطاق الفريق** — فيرى رواتب فريقه لا الشركة
        assert d.scope is Scope.TEAM


def test_company_can_shrink_the_list(env):
    """وينقص كذلك — فالقائمة ليست حدًّا أدنى مفروضًا."""
    with account_scope(env["account_id"]):
        _make_manager(env)
        env["comp"].dept_manager_permissions = ["employees.view"]
        env["comp"].save(update_fields=["dept_manager_permissions"])

        assert Gate.check(env["mgr_user"], "employees.view").allowed
        assert not Gate.check(env["mgr_user"],
                              "requests.approve").allowed


def test_empty_means_default_not_nothing(env):
    """
    ⚠️⚠️ **وفارغٌ يعني الافتراض لا «بلا شيء»**: فشركةٌ لم تضبطه
    **يبقى مديرها بلا صلاحية** — وذاك ليس ما أرادت.
    """
    with account_scope(env["account_id"]):
        env["comp"].dept_manager_permissions = []
        env["comp"].save(update_fields=["dept_manager_permissions"])
        got = dept_manager_permissions(env["comp"].id)
        assert got == frozenset(DEFAULT_DEPT_MANAGER_PERMISSIONS)


def test_unknown_key_is_dropped(env):
    """
    ⚠️ **ومفتاحٌ مخترَع يُسقط**: فالكتالوج يرفعه استثناءً —
    **وخطأٌ في الضبط يُسقط النظام كلّه**.
    """
    with account_scope(env["account_id"]):
        env["comp"].dept_manager_permissions = [
            "employees.view", "totally.invented"]
        env["comp"].save(update_fields=["dept_manager_permissions"])

        got = dept_manager_permissions(env["comp"].id)
        assert "totally.invented" not in got
        assert "employees.view" in got


def test_existing_role_scope_is_not_lowered(env):
    """
    ⚠️ **ولا يفقد ما عنده**: فمن دوره يمنحه نطاقًا أوسع **يبقى
    عليه** — والاكتساب زيادةٌ لا استبدال.
    """
    from apps.accounts.models_access import RoleAssignment

    with account_scope(env["account_id"]):
        _make_manager(env)
        acc = Account.objects.get(id=env["account_id"])
        a = RoleAssignment.objects.filter(
            membership__user=env["mgr_user"]).first()
        a.role = Role.objects.get(account=acc, code="hr_manager")
        a.scope = Scope.COMPANY.value
        a.save(update_fields=["role", "scope"])

        d = Gate.check(env["mgr_user"], "employees.view")
        assert d.scope is Scope.COMPANY, f"هبط النطاق: {d.scope}"


def test_workspace_lists_gained_permissions(env):
    """
    **وتظهر في قائمة صلاحياته** — وإلا ظهر البند في القائمة
    وحُجب عند الفتح، أو العكس.
    """
    with account_scope(env["account_id"]):
        _make_manager(env)
        keys = Gate.accessible_permissions(env["mgr_user"])
        for k in DEFAULT_DEPT_MANAGER_PERMISSIONS:
            assert k in keys, f"ناقصة من القائمة: {k}"
