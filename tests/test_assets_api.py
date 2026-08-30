"""حرّاس API السلف والعهد والوثائق ومسير المستحقات."""
import json
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent, PayrollSettings
from apps.payroll.services.gosi_seed import sync_gosi_rates

IBAN = "SA6080000247608010330101"


@pytest.fixture
def env(db):
    sync_gosi_rates()
    r = provision_account(slug="ast-api", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}
        st = PayrollSettings.objects.get(company=comp)
        st.eosb_wage_basis = "flagged"
        st.save()

        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1099887766", mobile="0509887766", force=True)
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="201",
            join_date=date(2019, 1, 1), iban=IBAN,
            salary_lines=[(comps["BASIC"], D("9000")),
                          (comps["HOUSING"], D("2250"))])
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp, "person": p, "settings": st}


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


def _post(c, url, d):
    return c.post(url, data=json.dumps(d), content_type="application/json")


def _put(c, url, d):
    return c.put(url, data=json.dumps(d), content_type="application/json")


# ══════════ السلف ══════════

@pytest.mark.django_db(transaction=True)
def test_create_and_approve_advance(env):
    c = _client(env, "hr_manager")
    r = _post(c, "/api/advances/", {
        "employment_id": env["emp"].id, "amount": "6000",
        "start_year": 2026, "start_month": 4, "installments_count": 6})
    assert r.status_code == 201
    adv_id = r.json()["id"]
    assert r.json()["installment_amount"] == "1000.00"

    r2 = _put(c, f"/api/advances/{adv_id}/approve/", {})
    assert r2.json()["status"] == "active"


@pytest.mark.django_db(transaction=True)
def test_advances_disabled_returns_409(env):
    """ق-41: شركة تُطفئ نظام السلف."""
    with account_scope(env["account_id"]):
        env["settings"].advances_enabled = False
        env["settings"].save()
    c = _client(env, "hr_manager")
    r = c.get("/api/advances/")
    assert r.status_code == 409
    assert r.json()["code"] == "advances_disabled"


@pytest.mark.django_db(transaction=True)
def test_eligibility_shows_limits(env):
    with account_scope(env["account_id"]):
        env["settings"].advance_max_amount = D("5000")
        env["settings"].save()
    c = _client(env, "hr_manager")
    d = c.get(f"/api/employees/{env['emp'].id}/advance-eligibility/"
              "?amount=6000").json()
    assert d["allowed"] is False
    assert d["max_allowed"] == "5000.00"


@pytest.mark.django_db(transaction=True)
def test_advance_over_limit_rejected(env):
    with account_scope(env["account_id"]):
        env["settings"].advance_max_amount = D("5000")
        env["settings"].save()
    c = _client(env, "hr_manager")
    r = _post(c, "/api/advances/", {
        "employment_id": env["emp"].id, "amount": "9000",
        "start_year": 2026, "start_month": 4})
    assert r.status_code == 400
    assert r.json()["code"] == "not_eligible"


@pytest.mark.django_db(transaction=True)
def test_advance_schedule(env):
    c = _client(env, "hr_manager")
    adv_id = _post(c, "/api/advances/", {
        "employment_id": env["emp"].id, "amount": "3000",
        "start_year": 2026, "start_month": 4,
        "installments_count": 3}).json()["id"]
    d = c.get(f"/api/advances/{adv_id}/schedule/").json()
    assert d["outstanding"] == "3000.00"
    assert d["installments"] == []


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_create_advance(env):
    emp_c = _client(env, "employee", "emp1", Scope.OWN)
    r = _post(emp_c, "/api/advances/", {
        "employment_id": env["emp"].id, "amount": "1000",
        "start_year": 2026, "start_month": 4})
    assert r.status_code == 403


# ══════════ العهد ══════════

@pytest.mark.django_db(transaction=True)
def test_assign_and_return_asset(env):
    c = _client(env, "hr_manager")
    r = _post(c, "/api/assets/", {
        "employment_id": env["emp"].id, "name_ar": "حاسب محمول",
        "value": "4500", "category": "device", "serial_number": "SN-1"})
    assert r.status_code == 201
    asset_id = r.json()["id"]

    d = _put(c, f"/api/assets/{asset_id}/return/", {}).json()
    assert d["status"] == "returned"
    assert d["is_outstanding"] is False


@pytest.mark.django_db(transaction=True)
def test_lost_asset_stays_outstanding(env):
    c = _client(env, "hr_manager")
    asset_id = _post(c, "/api/assets/", {
        "employment_id": env["emp"].id, "name_ar": "هاتف",
        "value": "1500"}).json()["id"]
    d = _put(c, f"/api/assets/{asset_id}/return/",
             {"status": "lost", "condition_note": "فُقد"}).json()
    assert d["is_outstanding"] is True


@pytest.mark.django_db(transaction=True)
def test_clearance_lists_outstanding(env):
    """كشف السلف والعهد قبل نهاية الخدمة."""
    c = _client(env, "hr_manager")
    adv_id = _post(c, "/api/advances/", {
        "employment_id": env["emp"].id, "amount": "6000",
        "start_year": 2026, "start_month": 4}).json()["id"]
    _put(c, f"/api/advances/{adv_id}/approve/", {})
    _post(c, "/api/assets/", {
        "employment_id": env["emp"].id, "name_ar": "حاسب", "value": "4500"})

    d = c.get(f"/api/employees/{env['emp'].id}/clearance/").json()
    assert d["advances"]["total_outstanding"] == "6000.00"
    assert d["assets"]["total_value"] == "4500.00"


# ══════════ الوثائق ══════════

@pytest.mark.django_db(transaction=True)
def test_add_document_and_expiry_alert(env):
    c = _client(env, "hr_manager")
    today = date.today()
    r = _post(c, "/api/documents/", {
        "employment_id": env["emp"].id, "document_type": "iqama",
        "document_number": "2154967927",
        "expiry_date": str(today + timedelta(days=10))})
    assert r.status_code == 201

    d = c.get("/api/documents/expiring/?within_days=60").json()
    assert d["total"] == 1
    assert d["documents"][0]["severity"] == "حرجة"


@pytest.mark.django_db(transaction=True)
def test_expired_document_flagged(env):
    c = _client(env, "hr_manager")
    _post(c, "/api/documents/", {
        "employment_id": env["emp"].id, "document_type": "passport",
        "expiry_date": str(date.today() - timedelta(days=5))})
    d = c.get("/api/documents/expiring/").json()
    assert d["documents"][0]["is_expired"] is True
    assert d["by_severity"]["منتهية"] == 1


@pytest.mark.django_db(transaction=True)
def test_invalid_document_dates_rejected(env):
    c = _client(env, "hr_manager")
    r = _post(c, "/api/documents/", {
        "employment_id": env["emp"].id, "document_type": "iqama",
        "issue_date": "2026-05-01", "expiry_date": "2026-01-01"})
    assert r.status_code == 400


# ══════════ مسير المستحقات ══════════

@pytest.mark.django_db(transaction=True)
def test_settlement_preview(env):
    c = _client(env, "hr_manager")
    d = _post(c, f"/api/employees/{env['emp'].id}/settlement/preview/", {
        "termination_date": "2026-06-15",
        "reason_code": "employer_death"}).json()
    assert d["reason_label"] == "وفاة صاحب العمل"
    assert D(d["net_due"]) > 0
    assert any(l["code"] == "EOSB" for l in d["lines"])


@pytest.mark.django_db(transaction=True)
def test_settlement_preview_unknown_reason(env):
    c = _client(env, "hr_manager")
    r = _post(c, f"/api/employees/{env['emp'].id}/settlement/preview/", {
        "termination_date": "2026-06-15", "reason_code": "made_up"})
    assert r.status_code == 400
    assert len(r.json()["available_reasons"]) == 16


@pytest.mark.django_db(transaction=True)
def test_settlement_blocked_without_basis(env):
    """ق-21: الصمت في أجر المكافأة قرار مالي لم يتخذه أحد."""
    with account_scope(env["account_id"]):
        env["settings"].eosb_wage_basis = "not_set"
        env["settings"].save()
    c = _client(env, "hr_manager")
    r = _post(c, f"/api/employees/{env['emp'].id}/settlement/preview/", {
        "termination_date": "2026-06-15",
        "reason_code": "employer_death"})
    assert r.status_code == 409
    assert r.json()["code"] == "eosb_basis_not_set"


@pytest.mark.django_db(transaction=True)
def test_settlement_create_then_duplicate_blocked(env):
    c = _client(env, "hr_manager")
    payload = {"termination_date": "2026-06-15",
               "reason_code": "employer_death"}
    r = _post(c, f"/api/employees/{env['emp'].id}/settlement/create/", payload)
    assert r.status_code == 201
    assert r.json()["run_no"].startswith("PT-")

    r2 = _post(c, f"/api/employees/{env['emp'].id}/settlement/create/", payload)
    assert r2.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_settlement_reasons_list(env):
    c = _client(env, "hr_manager")
    d = c.get("/api/settlement/reasons/").json()
    assert len(d) == 16
    unlawful = [x for x in d if x["code"] == "unlawful_termination"][0]
    assert unlawful["requires_compensation_77"] is True


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_preview_settlement(env):
    emp_c = _client(env, "employee", "emp2", Scope.OWN)
    r = _post(emp_c, f"/api/employees/{env['emp'].id}/settlement/preview/",
              {"termination_date": "2026-06-15",
               "reason_code": "employer_death"})
    assert r.status_code == 403


# ══════════ العزل ══════════

@pytest.mark.django_db(transaction=True)
def test_isolated_between_accounts(env):
    other = provision_account(slug="ast-other", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(other.account_id):
        from apps.employees.services.hiring import create_person as cp
        p2, _ = cp(account=Account.objects.get(id=other.account_id),
                   first_name_ar="آخر", family_name_ar="شخص",
                   gender="male", nationality_code="SA",
                   id_type="national_id", id_number="1055443322",
                   mobile="0505443322", force=True)
        e2, _, _ = create_employment(
            person=p2, company=Company.objects.get(id=other.company_id),
            employee_no="X1", join_date=date(2022, 1, 1))

    c = _client(env, "hr_manager")
    assert c.get(f"/api/employees/{e2.id}/clearance/").status_code == 404
