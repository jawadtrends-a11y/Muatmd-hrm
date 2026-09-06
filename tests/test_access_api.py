"""حرّاس API إدارة الصلاحيات."""
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import PERMISSIONS, Scope
from apps.core.tenancy.context import account_scope


def _user(username, account_id, role_code, scope, owner=False):
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


def _client(u):
    c = Client(); c.force_login(u); return c


@pytest.fixture
def acct(db):
    return provision_account(
        slug="api-test", display_name_ar="حساب API",
        company_name_ar="شركة API", is_sandbox=True,
    )


@pytest.mark.django_db(transaction=True)
def test_catalog_lists_all_permissions(acct):
    u = _user("api.hr", acct.account_id, "hr_manager", Scope.COMPANY)
    d = _client(u).get("/api/access/permissions/").json()
    assert d["total"] == len(PERMISSIONS)


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_view_catalog(acct):
    """الموظف بلا access.view — يُرفض."""
    u = _user("api.emp", acct.account_id, "employee", Scope.OWN)
    assert _client(u).get("/api/access/permissions/").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_edit_roles(acct):
    u = _user("api.emp2", acct.account_id, "employee", Scope.OWN)
    with account_scope(acct.account_id):
        rid = Role.objects.get(account_id=acct.account_id, code="employee").id
    r = _client(u).put(
        f"/api/access/roles/{rid}/permissions/",
        data=json.dumps({"permissions": ["employees.view"]}),
        content_type="application/json",
    )
    assert r.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_role_list_never_leaks_other_account(acct, rls_enforced):
    """أدوار حساب آخر لا تظهر إطلاقًا."""
    other = provision_account(
        slug="api-other", display_name_ar="آخر",
        company_name_ar="شركة أخرى", is_sandbox=True,
    )
    u = _user("api.iso", acct.account_id, "hr_manager", Scope.COMPANY)
    roles = _client(u).get("/api/access/roles/").json()
    from apps.accounts.services.roles import DEFAULT_ROLES
    assert len(roles) == len(DEFAULT_ROLES)
    with account_scope(other.account_id):
        other_ids = set(
            Role.objects.filter(account_id=other.account_id).values_list("id", flat=True)
        )
    assert not {r["id"] for r in roles} & other_ids


@pytest.mark.django_db(transaction=True)
def test_cannot_read_other_account_role_by_id(acct, rls_enforced):
    """طلب دور حساب آخر بمعرّفه صراحةً يرجع 404 لا بياناته."""
    other = provision_account(
        slug="api-other2", display_name_ar="آخر٢",
        company_name_ar="شركة أخرى٢", is_sandbox=True,
    )
    with account_scope(other.account_id):
        other_role_id = Role.objects.get(
            account_id=other.account_id, code="owner"
        ).id
    u = _user("api.iso2", acct.account_id, "hr_manager", Scope.COMPANY)
    assert _client(u).get(f"/api/access/roles/{other_role_id}/").status_code == 404


@pytest.mark.django_db(transaction=True)
def test_owner_protected_permissions_rejected_with_409(acct):
    u = _user("api.owner", acct.account_id, "owner", Scope.ACCOUNT, owner=True)
    with account_scope(acct.account_id):
        rid = Role.objects.get(account_id=acct.account_id, code="owner").id
    r = _client(u).put(
        f"/api/access/roles/{rid}/permissions/",
        data=json.dumps({"permissions": ["employees.view"]}),
        content_type="application/json",
    )
    assert r.status_code == 409
    assert r.json()["code"] == "protected_permission"


@pytest.mark.django_db(transaction=True)
def test_unknown_permission_rejected_with_400(acct):
    u = _user("api.hr2", acct.account_id, "hr_manager", Scope.COMPANY)
    with account_scope(acct.account_id):
        rid = Role.objects.get(account_id=acct.account_id, code="employee").id
    r = _client(u).put(
        f"/api/access/roles/{rid}/permissions/",
        data=json.dumps({"permissions": ["fake.permission"]}),
        content_type="application/json",
    )
    assert r.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_non_owner_role_freely_editable(acct):
    """النظام ينظّم ولا يصادر."""
    u = _user("api.hr3", acct.account_id, "hr_manager", Scope.COMPANY)
    with account_scope(acct.account_id):
        rid = Role.objects.get(account_id=acct.account_id, code="supervisor").id
    r = _client(u).put(
        f"/api/access/roles/{rid}/permissions/",
        data=json.dumps({"permissions": ["employees.view", "leaves.view"]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.json()["count"] == 2


# ══════════ نزع كل الصلاحيات دفعةً ══════════

@pytest.mark.django_db(transaction=True)
def test_empty_list_needs_explicit_confirm(acct):
    """
    ⚠️ نزع كل الصلاحيات دفعةً يحتاج تأكيدًا صريحًا.

    فمن يفتح شاشة الصلاحيات ويحفظ قبل أن تُحمَّل المفاتيح يمحوها
    كلها — فلا يرى المستخدم شيئًا في النظام ولا يعرف أحد السبب.
    وقد وقع فعلًا في التجربة.
    """
    from datetime import date

    from apps.accounts.models import Account
    from apps.core.access.gate import Gate
    from apps.employees.services.hiring import (create_employment,
                                                create_person)

    hr = _user("rev.hr", acct.account_id, "hr_manager", Scope.COMPANY)

    with account_scope(acct.account_id):
        acc = Account.objects.get(id=acct.account_id)
        comp = Company.objects.filter(account_id=acct.account_id).first()

        p, _ = create_person(
            account=acc, first_name_ar="عبدالعزيز",
            family_name_ar="العتيبي", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1055566677", mobile="0505556667")
        emp, _, _ = create_employment(person=p, company=comp,
                                      employee_no="S9",
                                      join_date=date(2023, 1, 1))

        target = User.objects.create_user(username="rev.sup",
                                          password="x")
        p.user = target
        p.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=target, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m,
            role=Role.objects.get(account=acc, code="supervisor"),
            company=comp, scope=Scope.TEAM.value)

    r = _client(hr).put(
        f"/api/access/members/{emp.id}/permissions/",
        data=json.dumps({"permissions": []}),
        content_type="application/json")

    assert r.status_code == 409, "مُحيت الصلاحيات بلا تأكيد"
    assert r.json().get("code") == "revoke_all_needs_confirm"

    with account_scope(acct.account_id):
        left = Gate.accessible_permissions(target)
    assert left, "نُزعت الصلاحيات رغم رفض الطلب"


@pytest.mark.django_db(transaction=True)
def test_confirmed_revoke_passes(acct):
    """
    ومن يقصد النزع يؤكّده فيمضي — فالحماية تنبيه لا منع (ق-88).
    """
    from datetime import date

    from apps.accounts.models import Account
    from apps.employees.services.hiring import (create_employment,
                                                create_person)

    hr = _user("rev2.hr", acct.account_id, "hr_manager", Scope.COMPANY)

    with account_scope(acct.account_id):
        acc = Account.objects.get(id=acct.account_id)
        comp = Company.objects.filter(account_id=acct.account_id).first()

        p, _ = create_person(
            account=acc, first_name_ar="سلطان",
            family_name_ar="الرشيدي", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1066677788", mobile="0506667778")
        emp, _, _ = create_employment(person=p, company=comp,
                                      employee_no="S8",
                                      join_date=date(2023, 1, 1))

        target = User.objects.create_user(username="rev2.sup",
                                          password="x")
        p.user = target
        p.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=target, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m,
            role=Role.objects.get(account=acc, code="supervisor"),
            company=comp, scope=Scope.TEAM.value)

    r = _client(hr).put(
        f"/api/access/members/{emp.id}/permissions/",
        data=json.dumps({"permissions": [], "confirm_revoke_all": True}),
        content_type="application/json")

    assert r.status_code == 200, r.content.decode()[:200]
