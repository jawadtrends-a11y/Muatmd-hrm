"""حرّاس API الموظفين — خصوصًا العزل المالي بين شركات المجموعة."""
import json
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.payroll.models import PayrollSettings
from apps.payroll.services.components import provision_default_components

IBAN = "SA0380000000608010167519"


@pytest.fixture
def env(db):
    r = provision_account(slug="empapi", display_name_ar="مجموعة",
                          company_name_ar="شركة أولى", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        c1 = Company.objects.get(id=r.company_id)
        c2 = Company.objects.create(account=acc, code="C2",
                                    legal_name_ar="شركة ثانية")
        provision_default_components(c2)
        PayrollSettings.objects.get_or_create(company=c2,
                                              defaults={"account": acc})
    return {"account_id": r.account_id, "c1": c1, "c2": c2, "acc": acc}


def _client(env, role_code, scope=Scope.ACCOUNT, username="u1"):
    u = User.objects.create_user(username=username, password="x")
    with account_scope(env["account_id"]):
        role = Role.objects.get(account_id=env["account_id"], code=role_code)
        m = AccountMembership.objects.create(
            user=u, account_id=env["account_id"], active_company=env["c1"])
        RoleAssignment.objects.create(membership=m, role=role,
                                      scope=scope.value)
    c = Client()
    c.force_login(u)
    c._membership = m
    return c


def _post(c, url, d):
    return c.post(url, data=json.dumps(d), content_type="application/json")


def _put(c, url, d):
    return c.put(url, data=json.dumps(d), content_type="application/json")


def _hire(c, **over):
    payload = {
        "first_name_ar": "محمد", "family_name_ar": "السالم",
        "gender": "male", "nationality_code": "SA",
        "id_type": "national_id", "id_number": "1055566677",
        "mobile": "0505556667", "employee_no": "E-100",
        "join_date": "2019-01-01", "iban": IBAN,
        "salary_lines": [{"code": "BASIC", "amount": "8000"},
                         {"code": "HOUSING", "amount": "2000"}],
    }
    payload.update(over)
    return _post(c, "/api/employees/", payload)


@pytest.mark.django_db(transaction=True)
def test_hire_creates_person_employment_and_structure(env):
    c = _client(env, "hr_manager")
    r = _hire(c)
    assert r.status_code == 201
    d = r.json()
    assert d["employment_id"] and d["person_id"] and d["structure_id"]


@pytest.mark.django_db(transaction=True)
def test_duplicate_id_returns_409(env):
    c = _client(env, "hr_manager")
    _hire(c)
    r = _hire(c, employee_no="E-200", mobile="0509999999")
    assert r.status_code == 409
    assert r.json()["code"] == "duplicate_person"


@pytest.mark.django_db(transaction=True)
def test_invalid_iban_rejected(env):
    c = _client(env, "hr_manager")
    r = _hire(c, iban="SA0000000000000000000000")
    assert r.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_registration_flags_drive_nitaqat(env):
    """ق-15: نطاقات تحتسب المسجّلين في قوى فقط."""
    c = _client(env, "hr_manager")
    emp_id = _hire(c).json()["employment_id"]

    d = c.get(f"/api/employees/{emp_id}/").json()
    assert d["employment"]["counts_in_nitaqat"] is False

    d = _put(c, f"/api/employees/{emp_id}/registration/",
             {"is_mol_registered": True}).json()
    assert d["counts_in_nitaqat"] is True


@pytest.mark.django_db(transaction=True)
def test_gosi_declared_wage_may_differ(env):
    """ق-15: الأجر المسجّل قد يخالف المدفوع — النظام يعكس الواقع."""
    c = _client(env, "hr_manager")
    emp_id = _hire(c).json()["employment_id"]
    _put(c, f"/api/employees/{emp_id}/registration/",
         {"is_gosi_registered": True, "gosi_declared_wage": "6000"})
    d = c.get(f"/api/employees/{emp_id}/").json()
    assert d["employment"]["gosi_declared_wage"] == "6000.00"


@pytest.mark.django_db(transaction=True)
def test_salary_history_preserved(env):
    """لا تعديل في المكان — كل تغيير سجل جديد."""
    c = _client(env, "hr_manager")
    emp_id = _hire(c).json()["employment_id"]
    _post(c, f"/api/employees/{emp_id}/salary/", {
        "effective_from": "2024-01-01", "reason": "annual_raise",
        "lines": [{"code": "BASIC", "amount": "9000"},
                  {"code": "HOUSING", "amount": "2250"}]})
    hist = c.get(f"/api/employees/{emp_id}/salary/").json()
    assert len(hist) == 2
    old = [h for h in hist if h["effective_from"] == "2019-01-01"][0]
    assert old["effective_to"] == "2023-12-31", "الهيكل السابق لم يُغلق"
    assert old["gross_monthly"] == "10000.00"


@pytest.mark.django_db(transaction=True)
def test_backdated_salary_rejected(env):
    c = _client(env, "hr_manager")
    emp_id = _hire(c).json()["employment_id"]
    r = _post(c, f"/api/employees/{emp_id}/salary/", {
        "effective_from": "2018-01-01",
        "lines": [{"code": "BASIC", "amount": "9000"}]})
    assert r.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_same_person_two_companies(env):
    """ق-4: شخص واحد، ارتباطان."""
    c = _client(env, "hr_manager")
    d = _hire(c).json()
    with account_scope(env["account_id"]):
        c._membership.active_company = env["c2"]
        c._membership.save()
    r = _post(c, "/api/employees/", {
        "person_id": d["person_id"], "employee_no": "X-77",
        "join_date": "2023-06-01",
        "salary_lines": [{"code": "BASIC", "amount": "4000"}]})
    assert r.status_code == 201


@pytest.mark.django_db(transaction=True)
def test_other_employments_carry_no_financial_data(env):
    """
    ق-3: العزل المالي المطلق — مديرة الموارد في شركة لا ترى راتبه
    في شركة أخرى، ولو كان نفس الحساب ونفس الشخص.
    """
    c = _client(env, "hr_manager")
    d = _hire(c).json()
    with account_scope(env["account_id"]):
        c._membership.active_company = env["c2"]
        c._membership.save()
    second = _post(c, "/api/employees/", {
        "person_id": d["person_id"], "employee_no": "X-77",
        "join_date": "2023-06-01",
        "salary_lines": [{"code": "BASIC", "amount": "4000"}]}).json()

    detail = c.get(f"/api/employees/{second['employment_id']}/").json()
    others = detail["other_employments"]
    assert len(others) == 1
    forbidden = {"salary", "gross", "amount", "wage", "raise", "iban"}
    for o in others:
        assert not (set(o.keys()) & forbidden), f"تسريب مالي: {o}"


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_list_all(env):
    emp = _client(env, "employee", Scope.OWN, username="emp1")
    r = emp.get("/api/employees/")
    assert r.status_code == 200
    assert r.json() == [], "الموظف يرى موظفين آخرين"


@pytest.mark.django_db(transaction=True)
def test_hr_staff_cannot_edit_salary(env):
    """ق-10: موظف الموارد يدير الملفات لا الهياكل."""
    hr = _client(env, "hr_manager")
    emp_id = _hire(hr).json()["employment_id"]
    staff = _client(env, "hr_staff", Scope.COMPANY, username="staff1")
    r = _post(staff, f"/api/employees/{emp_id}/salary/", {
        "effective_from": "2025-01-01",
        "lines": [{"code": "BASIC", "amount": "99000"}]})
    assert r.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_employees_isolated_between_accounts(env, rls_enforced_late):
    other = provision_account(slug="empapi-o", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    c = _client(env, "hr_manager")
    _hire(c)
    rls_enforced_late()
    from apps.employees.models import Employment
    with account_scope(other.account_id):
        assert Employment.objects.count() == 0
