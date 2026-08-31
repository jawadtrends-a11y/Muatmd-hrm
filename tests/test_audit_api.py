"""حرّاس API سجل العمليات (ق-44)."""
from datetime import date
from decimal import Decimal as D

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.services.audit import log_create
from apps.core.tenancy.context import account_scope
from apps.employees.services.advances import approve_advance, create_advance
from apps.employees.services.assets import assign_asset, return_asset
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent, PayrollSettings

IBAN = "SA6080000247608010330101"


@pytest.fixture
def env(db):
    r = provision_account(slug="aud-api", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}
        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1099887766", mobile="0509887766", force=True)
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="201",
            join_date=date(2021, 1, 1), iban=IBAN,
            salary_lines=[(comps["BASIC"], D("9000"))])
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp, "person": p,
               "settings": PayrollSettings.objects.get(company=comp)}


def _client(env, role_code, username="u", scope=Scope.COMPANY):
    u = User.objects.create_user(username=username, password="x")
    with account_scope(env["account_id"]):
        role = Role.objects.get(account_id=env["account_id"], code=role_code)
        m = AccountMembership.objects.create(
            user=u, account_id=env["account_id"], active_company=env["comp"])
        RoleAssignment.objects.create(membership=m, role=role,
                                      company=env["comp"], scope=scope.value)
    c = Client()
    c.force_login(u)
    return c


@pytest.mark.django_db(transaction=True)
def test_object_history(env):
    """السجل يُعرض في مكان التعديل — شاشة الموظف تناديه بمعرّفه."""
    with account_scope(env["account_id"]):
        log_create(instance=env["emp"], actor=env["person"], label="201")
    c = _client(env, "hr_manager")
    d = c.get(f"/api/audit/employment/{env['emp'].id}/").json()
    assert d["count"] == 1
    assert d["entries"][0]["actor"] == env["person"].display_name


@pytest.mark.django_db(transaction=True)
def test_unknown_object_type_rejected(env):
    """لا يمر نوع غير مُعلَن — حماية من الاستعلام العشوائي."""
    c = _client(env, "hr_manager")
    r = c.get("/api/audit/secret_table/1/")
    assert r.status_code == 400
    assert "allowed" in r.json()


@pytest.mark.django_db(transaction=True)
def test_field_labels_in_arabic(env):
    """أسماء الحقول تُعرض بالعربية لا بأسماء الأعمدة التقنية."""
    from apps.core.services.audit import log_change, snapshot
    with account_scope(env["account_id"]):
        before = snapshot(env["emp"])
        env["emp"].include_in_wps = True
        env["emp"].save()
        log_change(instance=env["emp"], before=before, actor=env["person"])
    c = _client(env, "hr_manager")
    d = c.get(f"/api/audit/employment/{env['emp'].id}/").json()
    labels = {ch["field_label"] for e in d["entries"] for ch in e["changes"]}
    assert "في حماية الأجور" in labels


@pytest.mark.django_db(transaction=True)
def test_advance_approval_logged(env):
    with account_scope(env["account_id"]):
        adv = create_advance(employment=env["emp"], amount=D("6000"),
                             settings_obj=env["settings"],
                             start_year=2026, start_month=4,
                             installments_count=6)
        approve_advance(advance=adv, approved_by_person=env["person"])
    c = _client(env, "hr_manager")
    d = c.get(f"/api/audit/advance/{adv.id}/").json()
    assert d["count"] == 1
    assert "اعتماد سلفة" in d["entries"][0]["summary"]


@pytest.mark.django_db(transaction=True)
def test_asset_lifecycle_logged(env):
    """التسليم والاسترجاع كلاهما يُسجَّل."""
    with account_scope(env["account_id"]):
        a = assign_asset(employment=env["emp"], name_ar="حاسب",
                         value=D("4500"))
        return_asset(asset=a)
    c = _client(env, "hr_manager")
    d = c.get(f"/api/audit/asset/{a.id}/").json()
    assert d["count"] == 2


@pytest.mark.django_db(transaction=True)
def test_feed_lists_recent(env):
    with account_scope(env["account_id"]):
        log_create(instance=env["emp"], actor=env["person"])
    c = _client(env, "hr_manager")
    d = c.get("/api/audit/").json()
    assert d["count"] >= 1
    assert "object_type" in d["entries"][0]


@pytest.mark.django_db(transaction=True)
def test_feed_filter_by_type(env):
    with account_scope(env["account_id"]):
        log_create(instance=env["emp"], actor=env["person"])
        log_create(instance=env["person"], actor=env["person"])
    c = _client(env, "hr_manager")
    d = c.get("/api/audit/?object_type=person").json()
    assert all(e["object_type"] == "person" for e in d["entries"])


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_read_audit(env):
    """ق-44: السجل لموظف ومدير الموارد فقط."""
    emp_c = _client(env, "employee", "emp1", Scope.OWN)
    assert emp_c.get("/api/audit/").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_audit_isolated_between_accounts(env):
    other = provision_account(slug="aud-api-o", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(other.account_id):
        from apps.employees.services.hiring import create_person as cp
        p2, _ = cp(account=Account.objects.get(id=other.account_id),
                   first_name_ar="آخر", family_name_ar="شخص",
                   gender="male", nationality_code="SA",
                   id_type="national_id", id_number="1055443322",
                   mobile="0505443322", force=True)
        log_create(instance=p2, actor=p2)

    c = _client(env, "hr_manager")
    d = c.get(f"/api/audit/person/{p2.id}/").json()
    assert d["count"] == 0
