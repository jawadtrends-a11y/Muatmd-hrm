"""
حرّاس الأدوار المخصّصة (ق-127).

⚠️ **تصعيد الصلاحيات**: من ينشئ دورًا أوسع من دوره ثم يُسنده لنفسه
يترقّى بلا اعتماد — وهي ثغرةٌ كلاسيكية في أنظمة الصلاحيات.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.access.gate import Gate
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="cr-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        def hire(first, nid, mob, no, code, scope):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar="السالم",
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=TODAY - timedelta(days=200),
                salary_lines=[(basic, Decimal("8000"))])
            u = User.objects.create_user(username=f"cr.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, employment=e,
                role=Role.objects.get(account=acc, code=code),
                company=comp, scope=scope)
            return u

        mgr = hire("خالد", "1044455567", "0504445556", "CR-1",
                   "hr_manager", Scope.COMPANY.value)
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "mgr": mgr}


def _client(user):
    from django.test import Client

    c = Client()
    c.force_login(user)
    return c


def test_system_roles_cannot_be_deleted(env):
    """
    ⚠️ الدور الأساسيّ لا يُحذف.

    فالكود يشير إليه برمزه، وحذفه يترك النظام بلا دورٍ أساسيّ —
    ومن كان عليه بلا صلاحيات.
    """
    with account_scope(env["account_id"]):
        role = Role.objects.filter(account=env["acc"],
                                   is_system=True).first()
        assert role is not None
        c = _client(env["mgr"])
        r = c.delete(f"/api/access/roles/{role.id}/manage/")
        assert r.status_code == 409, r.content


def test_cannot_grant_what_you_do_not_have(env):
    """
    ⚠️⚠️ الأهمّ: **لا يُمنح ما لا يُملَك**.

    فمن ينشئ دورًا فيه صلاحيةٌ ليست له، ثم يُسنده لنفسه، يترقّى
    بلا اعتماد.
    """
    import json

    with account_scope(env["account_id"]):
        c = _client(env["mgr"])
        mine = Gate.accessible_permissions(env["mgr"])
        r = c.post("/api/access/roles/create/", data=json.dumps({
            "code": "escalated", "name_ar": "دور مدسوس",
            "permissions": sorted(mine)[:2] + ["not.a.real.permission"],
        }), content_type="application/json")
        assert r.status_code == 403, r.content
        assert not Role.objects.filter(account=env["acc"],
                                       code="escalated").exists()


def test_custom_role_is_created_with_its_permissions(env):
    """وما يملكه يمنحه — والدور يُنشأ بصلاحياته."""
    import json

    with account_scope(env["account_id"]):
        c = _client(env["mgr"])
        keys = sorted(Gate.accessible_permissions(env["mgr"]))[:3]
        r = c.post("/api/access/roles/create/", data=json.dumps({
            "code": "shift_lead", "name_ar": "مشرف وردية",
            "default_scope": "department", "permissions": keys,
        }), content_type="application/json")
        assert r.status_code == 201, r.content

        role = Role.objects.get(account=env["acc"], code="shift_lead")
        assert not role.is_system, "المخصّص ليس أساسيًّا"
        assert set(role.permission_keys) >= set(keys)


def test_assigned_role_cannot_be_deleted(env):
    """
    والمسنَد لموظفٍ لا يُحذف — فحذفه يترك من عليه بلا صلاحيات.
    """
    import json

    with account_scope(env["account_id"]):
        c = _client(env["mgr"])
        keys = sorted(Gate.accessible_permissions(env["mgr"]))[:2]
        c.post("/api/access/roles/create/", data=json.dumps({
            "code": "temp_role", "name_ar": "مؤقّت", "permissions": keys,
        }), content_type="application/json")
        role = Role.objects.get(account=env["acc"], code="temp_role")

        m = AccountMembership.objects.get(user=env["mgr"])
        RoleAssignment.objects.create(
            membership=m, role=role, company=env["comp"],
            scope=Scope.OWN.value)

        r = c.delete(f"/api/access/roles/{role.id}/manage/")
        assert r.status_code == 409, r.content


def test_duplicate_code_is_refused(env):
    """ورمزٌ مستعمل يُرفض — فالكود يشير بالرمز."""
    import json

    with account_scope(env["account_id"]):
        c = _client(env["mgr"])
        keys = sorted(Gate.accessible_permissions(env["mgr"]))[:2]
        body = json.dumps({"code": "employee", "name_ar": "مكرّر",
                           "permissions": keys})
        r = c.post("/api/access/roles/create/", data=body,
                   content_type="application/json")
        assert r.status_code == 409, r.content
