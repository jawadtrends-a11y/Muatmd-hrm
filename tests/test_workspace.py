"""حرّاس نقطة /me/workspace والـmiddleware."""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope


def _make_user(username, account_id, role_code, scope, owner=False):
    u = User.objects.create_user(username=username, password="x")
    with account_scope(account_id):
        comp = Company.objects.filter(account_id=account_id).first()
        role = Role.objects.get(account_id=account_id, code=role_code)
        m = AccountMembership.objects.create(
            user=u, account_id=account_id, active_company=comp,
            is_account_owner=owner,
        )
        RoleAssignment.objects.create(
            membership=m, role=role, company=comp, scope=scope.value,
        )
    return u


@pytest.fixture
def acct(db):
    return provision_account(
        slug="ws-test", display_name_ar="حساب الاختبار",
        company_name_ar="شركة الاختبار", is_sandbox=True,
    )


@pytest.mark.django_db(transaction=True)
def test_workspace_requires_auth(acct):
    assert Client().get("/api/me/workspace/").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_hr_manager_sees_payroll_nav(acct):
    u = _make_user("ws.hr", acct.account_id, "hr_manager", Scope.COMPANY)
    c = Client(); c.force_login(u)
    d = c.get("/api/me/workspace/").json()
    nav = [n["key"] for n in d["navigation"]]
    assert "payroll" in nav and "saudization" in nav and "access" in nav
    assert "payroll.approve" in d["permissions"]


@pytest.mark.django_db(transaction=True)
def test_employee_sees_minimal_nav(acct):
    """الموظف لا يرى الرواتب ولا التوطين ولا الصلاحيات."""
    u = _make_user("ws.emp", acct.account_id, "employee", Scope.OWN)
    c = Client(); c.force_login(u)
    d = c.get("/api/me/workspace/").json()
    nav = [n["key"] for n in d["navigation"]]
    assert "payroll" not in nav
    assert "saudization" not in nav
    assert "access" not in nav
    assert "payslips" in nav
    assert "payroll.approve" not in d["permissions"]


@pytest.mark.django_db(transaction=True)
def test_supervisor_sees_approvals_widget(acct):
    u = _make_user("ws.sup", acct.account_id, "supervisor", Scope.TEAM)
    c = Client(); c.force_login(u)
    d = c.get("/api/me/workspace/").json()
    widgets = [w["key"] for w in d["dashboard_widgets"]]
    assert "pending_approvals" in widgets
    assert "payroll_status" not in widgets
    assert "payslips.view_team" in d["permissions"]


@pytest.mark.django_db(transaction=True)
def test_owner_gets_all_permissions(acct):
    u = _make_user("ws.owner", acct.account_id, "owner", Scope.ACCOUNT, owner=True)
    c = Client(); c.force_login(u)
    d = c.get("/api/me/workspace/").json()
    from apps.core.access.catalog import PERMISSION_KEYS
    assert set(d["permissions"]) == PERMISSION_KEYS
    assert d["user"]["is_account_owner"] is True


@pytest.mark.django_db(transaction=True)
def test_workspace_never_leaks_other_account(acct):
    """مستخدم حساب لا يرى شركات حساب آخر إطلاقًا."""
    other = provision_account(
        slug="ws-other", display_name_ar="حساب آخر",
        company_name_ar="شركة أخرى", is_sandbox=True,
    )
    u = _make_user("ws.iso", acct.account_id, "hr_manager", Scope.COMPANY)
    c = Client(); c.force_login(u)
    d = c.get("/api/me/workspace/").json()
    assert d["account"]["id"] == acct.account_id
    assert all(x["id"] != other.company_id for x in d["companies"])


@pytest.mark.django_db(transaction=True)
def test_lookup_functions_bypass_rls_only_for_membership(acct):
    """
    دوال SECURITY DEFINER لا تُسرّب بيانات عمل — تعطيل RLS فيها
    محصور بجدول العضوية.
    """
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute("SELECT set_config('app.account_id','',TRUE)")
        cur.execute("SELECT prosecdef, proconfig FROM pg_proc "
                    "WHERE proname='app_lookup_membership'")
        secdef, config = cur.fetchone()
        assert secdef is True
        assert config and any("row_security=off" in c for c in config)
