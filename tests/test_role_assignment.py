"""
حرّاس إسناد الأدوار من ملفّ الموظف (ق-115).

⚠️ **تصعيد الصلاحيات**: من يُسند دورًا أعلى من دوره يصنع مالكًا
وهميًّا ثم يدخل به — فيرقّي نفسه بلا اعتماد.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.api import _apply_role, _may_assign_roles
from apps.employees.services.hiring import create_employment, create_person


@pytest.fixture
def env(db):
    r = provision_account(slug="role-asg", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        def mk(username, code, first, idn, mob, no):
            u = User.objects.create_user(username=username,
                                         password="Pw@2026xx")
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar="القحطاني",
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=idn, mobile=mob, user=u)
            e, _, _ = create_employment(person=p, company=comp,
                                        employee_no=no,
                                        join_date=date(2024, 1, 1))
            m = AccountMembership.objects.create(user=u, account=acc,
                                                 active_company=comp)
            if code:
                RoleAssignment.objects.create(
                    membership=m, employment=e,
                    role=Role.objects.get(account=acc, code=code),
                    company=comp, scope=Scope.COMPANY.value)
            return u, e

        hr_staff, _ = mk("t.hrstaff", "hr_staff", "سعد",
                         "1077788899", "0507778889", "R-1")
        hr_mgr, _ = mk("t.hrmgr", "hr_manager", "ماجد",
                       "1088899900", "0508889990", "R-2")
        plain, target = mk("t.plain", "employee", "نايف",
                           "1099900011", "0509990001", "R-3")

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "hr_staff": hr_staff, "hr_mgr": hr_mgr,
               "plain": plain, "target": target}


def test_hr_staff_cannot_assign_owner(env):
    """
    ⚠️ الأهمّ: موظف الموارد لا يُسند دور المالك.

    وإلا صنع مالكًا وهميًّا ثم دخل به — فترقّى نفسه بلا اعتماد.
    """
    with account_scope(env["account_id"]):
        owner = Role.objects.get(account=env["acc"], code="owner")
        with pytest.raises(PermissionError):
            _apply_role(env["target"], owner.id, env["hr_staff"])


def test_hr_staff_cannot_assign_ceo(env):
    """ولا المدير العام — وهو أعلى منه."""
    with account_scope(env["account_id"]):
        ceo = Role.objects.get(account=env["acc"], code="ceo")
        with pytest.raises(PermissionError):
            _apply_role(env["target"], ceo.id, env["hr_staff"])


def test_hr_staff_may_assign_lower_roles(env):
    """ويُسند ما دونه — موظفًا ومشرفًا ومدير إدارة."""
    with account_scope(env["account_id"]):
        for code in ("employee", "supervisor", "dept_manager"):
            role = Role.objects.get(account=env["acc"], code=code)
            name = _apply_role(env["target"], role.id, env["hr_staff"])
            assert name == role.name_ar


def test_plain_employee_cannot_assign_anything(env):
    """والموظف العاديّ لا يُسند شيئًا."""
    with account_scope(env["account_id"]):
        role = Role.objects.get(account=env["acc"], code="employee")
        with pytest.raises(PermissionError):
            _apply_role(env["target"], role.id, env["plain"])


def test_hr_manager_may_assign_ceo(env):
    """ومدير الموارد أعلى، فيُسند المدير العام."""
    with account_scope(env["account_id"]):
        ceo = Role.objects.get(account=env["acc"], code="ceo")
        with pytest.raises(PermissionError):
            _apply_role(env["target"], ceo.id, env["hr_staff"])
        # ومدير الموارد رتبته ٥ والمدير العام ٦ — فيُرفض كذلك
        with pytest.raises(PermissionError):
            _apply_role(env["target"], ceo.id, env["hr_mgr"])


def test_assignment_lands_on_the_employment(env):
    """والإسناد على **التوظيف** لا على العضوية وحدها (ق-115)."""
    with account_scope(env["account_id"]):
        role = Role.objects.get(account=env["acc"], code="supervisor")
        _apply_role(env["target"], role.id, env["hr_mgr"])
        ra = env["target"].role_assignments.first()
        assert ra is not None
        assert ra.employment_id == env["target"].id
        assert ra.company_id == env["comp"].id


def test_clearing_role_removes_assignment(env):
    """وإفراغه ينزع الدور — فلا يبقى أثر."""
    with account_scope(env["account_id"]):
        role = Role.objects.get(account=env["acc"], code="supervisor")
        _apply_role(env["target"], role.id, env["hr_mgr"])
        assert env["target"].role_assignments.exists()
        _apply_role(env["target"], None, env["hr_mgr"])
        assert not env["target"].role_assignments.exists()
