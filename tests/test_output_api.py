"""حرّاس API المخرجات: الشاشات والملفات والقسائم."""
from datetime import date
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
from apps.payroll.models import (
    BankTemplate, PayComponent, PayrollRunType, Payslip,
)
from apps.payroll.services.engine import (
    approve_run, calculate_run, create_run, submit_run,
)
from apps.payroll.services.gosi_seed import sync_gosi_rates

IBAN = "SA6080000247608010330101"


@pytest.fixture
def env(db):
    sync_gosi_rates()
    r = provision_account(slug="out-api", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}

        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            full_name_en="SAAD ALQAHTANI", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1099887766", mobile="0509887766",
            gosi_scheme_code="traditional", force=True)
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="201",
            join_date=date(2021, 1, 1), iban=IBAN, bank_code="RJHI",
            salary_lines=[(comps["BASIC"], D("9000")),
                          (comps["HOUSING"], D("2250"))])
        emp.is_gosi_registered = True
        emp.include_in_wps = True
        emp.save()

        run = create_run(company=comp, run_type=PayrollRunType.REGULAR,
                         year=2026, month=3)
        calculate_run(run)
        run.refresh_from_db()

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp, "person": p, "run": run}


def _client(env, role_code, username="u", scope=Scope.COMPANY, person=None):
    u = User.objects.create_user(username=username, password="x")
    with account_scope(env["account_id"]):
        role = Role.objects.get(account_id=env["account_id"], code=role_code)
        m = AccountMembership.objects.create(
            user=u, account_id=env["account_id"],
            active_company=env["comp"])
        RoleAssignment.objects.create(membership=m, role=role,
                                      company=env["comp"], scope=scope.value)
        if person is not None:
            person.user = u
            person.save()
    c = Client()
    c.force_login(u)
    return c


def _approve(env):
    with account_scope(env["account_id"]):
        run = env["run"]
        submit_run(run)
        run.refresh_from_db()
        approve_run(run, env["person"])
        run.refresh_from_db()
        run.payment_date = date(2026, 3, 25)
        run.save()
        return run


# ══════════ شاشات المسير ══════════

@pytest.mark.django_db(transaction=True)
def test_run_overview(env):
    c = _client(env, "hr_manager")
    d = c.get(f"/api/payroll/runs/{env['run'].id}/overview/").json()
    assert d["summary"]["employee_count"] == 1
    assert d["can_submit"] is True
    assert d["can_export"] is False
    assert len(d["available_tabs"]) == 6


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("tab", ["summary", "payslips", "excluded",
                                 "adjustments", "gosi", "comparison"])
def test_each_tab_returns_data(env, tab):
    c = _client(env, "hr_manager")
    r = c.get(f"/api/payroll/runs/{env['run'].id}/tab/{tab}/")
    assert r.status_code == 200
    assert r.json()["tab"] == tab


@pytest.mark.django_db(transaction=True)
def test_unknown_tab_rejected(env):
    c = _client(env, "hr_manager")
    r = c.get(f"/api/payroll/runs/{env['run'].id}/tab/whatever/")
    assert r.status_code == 400
    assert len(r.json()["available"]) == 6


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_view_run(env):
    emp_c = _client(env, "employee", "emp1", Scope.OWN)
    assert emp_c.get(
        f"/api/payroll/runs/{env['run'].id}/overview/").status_code == 403


# ══════════ ملفات البنوك ══════════

@pytest.mark.django_db(transaction=True)
def test_bank_templates_listed(env):
    c = _client(env, "hr_manager")
    d = c.get("/api/payroll/bank-templates/").json()
    ncb = [t for t in d if t["code"] == "NCB"][0]
    assert ncb["column_count"] == 11
    assert ncb["is_builtin"] is True


@pytest.mark.django_db(transaction=True)
def test_bank_preview_blocked_before_approval(env):
    c = _client(env, "hr_manager")
    with account_scope(env["account_id"]):
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
    r = c.get(f"/api/payroll/runs/{env['run'].id}/bank/{tpl.id}/preview/")
    assert r.status_code == 409
    assert r.json()["code"] == "not_exportable"


@pytest.mark.django_db(transaction=True)
def test_bank_preview_after_approval(env):
    run = _approve(env)
    c = _client(env, "hr_manager")
    with account_scope(env["account_id"]):
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
    d = c.get(f"/api/payroll/runs/{run.id}/bank/{tpl.id}/preview/").json()
    assert d["ready"] is True
    assert d["row_count"] == 1
    assert d["filename"] == "NCB_For_25-03-2026.csv"


@pytest.mark.django_db(transaction=True)
def test_bank_download_returns_file(env):
    run = _approve(env)
    c = _client(env, "hr_manager")
    with account_scope(env["account_id"]):
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
    r = c.get(f"/api/payroll/runs/{run.id}/bank/{tpl.id}/download/")
    assert r.status_code == 200
    assert "attachment" in r["Content-Disposition"]
    assert b"RJHI" in r.content


@pytest.mark.django_db(transaction=True)
def test_export_requires_permission(env):
    _approve(env)
    staff = _client(env, "hr_staff", "staff1")
    assert staff.get("/api/payroll/bank-templates/").status_code == 200
    emp_c = _client(env, "employee", "emp2", Scope.OWN)
    assert emp_c.get("/api/payroll/bank-templates/").status_code == 403


# ══════════ حماية الأجور ══════════

@pytest.mark.django_db(transaction=True)
def test_wps_preview_report(env):
    run = _approve(env)
    c = _client(env, "hr_manager")
    d = c.get(f"/api/payroll/runs/{run.id}/wps/preview/").json()
    assert d["ready"] is True
    assert d["record_count"] == 1
    assert d["error_count"] == 0


@pytest.mark.django_db(transaction=True)
def test_wps_download(env):
    run = _approve(env)
    c = _client(env, "hr_manager")
    r = c.get(f"/api/payroll/runs/{run.id}/wps/download/")
    assert r.status_code == 200
    assert "WPS_202603.csv" in r["Content-Disposition"]


# ══════════ القسائم ══════════

@pytest.mark.django_db(transaction=True)
def test_payslip_hidden_before_approval(env):
    """ق-10: القسيمة لا تُعرض للموظف قبل اعتماد المسير."""
    with account_scope(env["account_id"]):
        slip = Payslip.objects.get(run=env["run"])
    c = _client(env, "employee", "emp3", Scope.OWN, person=env["person"])
    r = c.get(f"/api/payslips/{slip.id}/")
    assert r.status_code == 409
    assert r.json()["code"] == "run_not_approved"


@pytest.mark.django_db(transaction=True)
def test_payslip_visible_after_approval(env):
    _approve(env)
    with account_scope(env["account_id"]):
        slip = Payslip.objects.get(run=env["run"])
    c = _client(env, "employee", "emp4", Scope.OWN, person=env["person"])
    d = c.get(f"/api/payslips/{slip.id}/").json()
    assert d["totals"]["net"]
    assert d["labels"]["title"] == "قسيمة راتب"


@pytest.mark.django_db(transaction=True)
def test_payslip_locale_switch(env):
    _approve(env)
    with account_scope(env["account_id"]):
        slip = Payslip.objects.get(run=env["run"])
    c = _client(env, "hr_manager")
    en = c.get(f"/api/payslips/{slip.id}/?locale=en").json()
    ur = c.get(f"/api/payslips/{slip.id}/?locale=ur").json()
    assert en["labels"]["title"] == "Payslip"
    assert ur["labels"]["title"] == "تنخواہ کی پرچی"
    assert any(e["name"] == "Basic Salary" for e in en["earnings"])


@pytest.mark.django_db(transaction=True)
def test_payslip_hides_optional_by_default(env):
    """ق-39: القسيمة للراتب وحده."""
    _approve(env)
    with account_scope(env["account_id"]):
        slip = Payslip.objects.get(run=env["run"])
    c = _client(env, "hr_manager")
    d = c.get(f"/api/payslips/{slip.id}/").json()
    assert d["optional"] == {}


@pytest.mark.django_db(transaction=True)
def test_my_payslips_only_approved(env):
    c = _client(env, "employee", "emp5", Scope.OWN, person=env["person"])
    assert c.get("/api/me/payslips/").json() == []
    _approve(env)
    assert len(c.get("/api/me/payslips/").json()) == 1


@pytest.mark.django_db(transaction=True)
def test_outputs_isolated_between_accounts(env):
    other = provision_account(slug="out-other", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    c = _client(env, "hr_manager")
    with account_scope(other.account_id):
        from apps.payroll.models import PayrollRun
        other_run = create_run(
            company=Company.objects.get(id=other.company_id),
            run_type=PayrollRunType.REGULAR, year=2026, month=3)
    assert c.get(
        f"/api/payroll/runs/{other_run.id}/overview/").status_code == 404
