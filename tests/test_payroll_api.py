"""حرّاس API الرواتب."""
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope


def _user(username, account_id, role_code, scope=Scope.COMPANY):
    u = User.objects.create_user(username=username, password="x")
    with account_scope(account_id):
        comp = Company.objects.filter(account_id=account_id).first()
        role = Role.objects.get(account_id=account_id, code=role_code)
        m = AccountMembership.objects.create(
            user=u, account_id=account_id, active_company=comp)
        RoleAssignment.objects.create(membership=m, role=role,
                                      company=comp, scope=scope.value)
    c = Client()
    c.force_login(u)
    return c


@pytest.fixture
def acct(db):
    return provision_account(
        slug="pay-api", display_name_ar="حساب رواتب",
        company_name_ar="شركة رواتب", is_sandbox=True)


@pytest.fixture
def hr(acct):
    return _user("pay.hr", acct.account_id, "hr_manager")


def _post(c, url, payload):
    return c.post(url, data=json.dumps(payload),
                  content_type="application/json")


def _put(c, url, payload):
    return c.put(url, data=json.dumps(payload),
                 content_type="application/json")


# ══════════ أسباب انتهاء العلاقة ══════════

@pytest.mark.django_db(transaction=True)
def test_termination_reasons_from_official_source(hr):
    d = hr.get("/api/payroll/termination-reasons/").json()
    assert d["total"] == 16
    assert "وزارة الموارد البشرية" in d["source"]
    unlawful = [r for r in d["reasons"]
                if r["code"] == "unlawful_termination"][0]
    assert unlawful["requires_compensation_77"] is True


# ══════════ الإعدادات ══════════

@pytest.mark.django_db(transaction=True)
def test_settings_defaults(hr):
    s = hr.get("/api/payroll/settings/").json()
    assert s["payroll_days_per_month"] == 30
    assert s["eosb_wage_basis"] == "not_set"
    assert s["eosb_basis_required"] is True


@pytest.mark.django_db(transaction=True)
def test_settings_update(hr):
    _put(hr, "/api/payroll/settings/", {"eosb_wage_basis": "flagged"})
    s = hr.get("/api/payroll/settings/").json()
    assert s["eosb_wage_basis"] == "flagged"
    assert s["eosb_basis_required"] is False


# ══════════ حاسبة نهاية الخدمة ══════════

@pytest.mark.django_db(transaction=True)
def test_calculator_blocked_before_basis_set(hr):
    """ق-21: الصمت في أجر المكافأة قرار مالي لم يتخذه أحد."""
    r = _post(hr, "/api/payroll/eosb/calculate/", {
        "join_date": "2019-01-01", "end_date": "2026-01-01",
        "eosb_wage": "12000", "reason_code": "mutual_agreement"})
    assert r.status_code == 409
    assert r.json()["code"] == "eosb_basis_not_set"


@pytest.mark.django_db(transaction=True)
def test_calculator_matches_official_amounts(hr):
    """ق-25: مطابقة الحاسبة الحكومية."""
    _put(hr, "/api/payroll/settings/", {"eosb_wage_basis": "flagged"})
    d = _post(hr, "/api/payroll/eosb/calculate/", {
        "join_date": "2019-01-01", "end_date": "2026-01-01",
        "eosb_wage": "12000", "reason_code": "mutual_agreement"}).json()
    assert d["service_days"] == 2520
    assert d["net_award"] == "54000.00"
    assert len(d["explanation"]) >= 8


@pytest.mark.django_db(transaction=True)
def test_calculator_returns_article_77_separately(hr):
    """ق-26: تعويض م/77 بند مستقل لا يُدمج."""
    _put(hr, "/api/payroll/settings/", {"eosb_wage_basis": "flagged"})
    d = _post(hr, "/api/payroll/eosb/calculate/", {
        "join_date": "2019-01-01", "end_date": "2026-01-01",
        "eosb_wage": "12000", "reason_code": "unlawful_termination"}).json()
    assert d["net_award"] == "54000.00"
    assert d["compensation_article_77"]["amount"] == "42000.00"
    assert d["total_due"] == "96000.00"


@pytest.mark.django_db(transaction=True)
def test_calculator_no_article_77_for_other_reasons(hr):
    _put(hr, "/api/payroll/settings/", {"eosb_wage_basis": "flagged"})
    d = _post(hr, "/api/payroll/eosb/calculate/", {
        "join_date": "2019-01-01", "end_date": "2026-01-01",
        "eosb_wage": "12000", "reason_code": "resignation"}).json()
    assert d["compensation_article_77"] is None


@pytest.mark.django_db(transaction=True)
def test_calculator_rejects_unknown_reason(hr):
    _put(hr, "/api/payroll/settings/", {"eosb_wage_basis": "flagged"})
    r = _post(hr, "/api/payroll/eosb/calculate/", {
        "join_date": "2019-01-01", "end_date": "2026-01-01",
        "eosb_wage": "12000", "reason_code": "made_up"})
    assert r.status_code == 400
    assert len(r.json()["available_reasons"]) == 16


# ══════════ المكوّنات والأعلام ══════════

@pytest.mark.django_db(transaction=True)
def test_components_listed_with_flags(hr):
    comps = hr.get("/api/payroll/components/").json()
    basic = [c for c in comps if c["code"] == "BASIC"][0]
    assert basic["is_gosi_subject"] and basic["is_eosb_subject"]
    assert basic["is_system"]


@pytest.mark.django_db(transaction=True)
def test_flag_exclusion_warns_not_blocks(hr):
    """ق-23: تحذير لا منع."""
    comps = hr.get("/api/payroll/components/").json()
    housing = [c for c in comps if c["code"] == "HOUSING"][0]
    _put(hr, f"/api/payroll/components/{housing['id']}/flags/",
         {"is_eosb_subject": True})
    d = _put(hr, f"/api/payroll/components/{housing['id']}/flags/",
             {"is_eosb_subject": False}).json()
    assert d["is_eosb_subject"] is False, "مُنع الاستثناء"
    assert len(d["warnings"]) == 1
    assert "القضاء العمالي" in d["warnings"][0]


# ══════════ الصلاحيات والعزل ══════════

@pytest.mark.django_db(transaction=True)
def test_employee_cannot_view_payroll(acct):
    emp = _user("pay.emp", acct.account_id, "employee", Scope.OWN)
    assert emp.get("/api/payroll/settings/").status_code == 403
    assert emp.get("/api/payroll/components/").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_hr_staff_cannot_edit_structures(acct):
    """ق-10: موظف الموارد ينشئ المسير ولا يعدّل الهياكل."""
    staff = _user("pay.staff", acct.account_id, "hr_staff")
    assert staff.get("/api/payroll/components/").status_code == 200
    r = _post(staff, "/api/payroll/components/",
              {"code": "X", "name_ar": "تجربة"})
    assert r.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_components_isolated_between_accounts(acct, hr):
    other = provision_account(
        slug="pay-other", display_name_ar="آخر",
        company_name_ar="شركة أخرى", is_sandbox=True)
    comps = hr.get("/api/payroll/components/").json()
    with account_scope(other.account_id):
        from apps.payroll.models import PayComponent
        other_ids = set(PayComponent.objects.filter(
            company_id=other.company_id).values_list("id", flat=True))
    assert not {c["id"] for c in comps} & other_ids
