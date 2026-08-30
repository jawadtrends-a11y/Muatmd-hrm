"""
حرّاس شاشات المسير (ق-40).

شاشات اطلاع لا تُصدَّر — ترجع JSON للواجهة مباشرة.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceMonthlySummary
from apps.core.tenancy.context import account_scope
from apps.employees.models import EmploymentStatus
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent, PayrollRunType
from apps.payroll.services.engine import calculate_run, create_run
from apps.payroll.services.gosi_seed import sync_gosi_rates
from apps.payroll.services.outputs import run_screens as rs

IBAN_A = "SA6080000247608010330101"
IBAN_B = "SA8510000012345678901234"  # صحيح رياضيًا (MOD-97)


@pytest.fixture
def env(db):
    sync_gosi_rates()
    r = provision_account(slug="scr-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}

        # سعودي مسجّل في التأمينات
        p1, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            full_name_en="SAAD ALQAHTANI", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1099887766", mobile="0509887766", force=True,
            gosi_scheme_code="traditional")
        saudi, _, _ = create_employment(
            person=p1, company=comp, employee_no="201",
            join_date=date(2021, 1, 1), iban=IBAN_B,
            salary_lines=[(comps["BASIC"], D("9000")),
                          (comps["HOUSING"], D("2250"))])
        saudi.is_gosi_registered = True
        saudi.include_in_wps = True
        saudi.save()

        # وافد غير مسجّل
        p2, _ = create_person(
            account=acc, first_name_ar="راشد", family_name_ar="خان",
            full_name_en="RASHID KHAN", gender="male",
            nationality_code="PK", id_type="iqama",
            id_number="2154967927", mobile="0504445556", force=True)
        expat, _, _ = create_employment(
            person=p2, company=comp, employee_no="118",
            join_date=date(2020, 1, 1), iban=IBAN_A,
            salary_lines=[(comps["BASIC"], D("2497")),
                          (comps["HOUSING"], D("633"))])
        expat.include_in_wps = True
        expat.save()

        # موقوف — يجب أن يظهر في المستبعدين
        p3, _ = create_person(
            account=acc, first_name_ar="فهد", family_name_ar="العتيبي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1055443322", mobile="0505443322", force=True)
        susp, _, _ = create_employment(
            person=p3, company=comp, employee_no="301",
            join_date=date(2022, 1, 1),
            salary_lines=[(comps["BASIC"], D("5000"))])
        susp.status = EmploymentStatus.SUSPENDED
        susp.save()

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "saudi": saudi, "expat": expat, "suspended": susp}


def _summary(env, emp, month, **kw):
    defaults = {"account": env["acc"], "company": env["comp"],
                "worked_days": D("22"), "unpaid_absent_days": D("0"),
                "approved_overtime_minutes": 0}
    defaults.update(kw)
    return AttendanceMonthlySummary.objects.update_or_create(
        employment=emp, period_year=2026, period_month=month,
        defaults=defaults)[0]


def _run(env, month, **summary_kw):
    if summary_kw:
        _summary(env, env["saudi"], month, **summary_kw)
    run = create_run(company=env["comp"], run_type=PayrollRunType.REGULAR,
                     year=2026, month=month)
    calculate_run(run)
    run.refresh_from_db()
    return run


# ══════════ الملخص ══════════

@pytest.mark.django_db(transaction=True)
def test_summary_headline_figures(env):
    with account_scope(env["account_id"]):
        run = _run(env, 3)
        s = rs.summary_tab(run)
        assert s["employee_count"] == 2
        assert s["headline"]["basic_total"] == "11497.00"
        assert s["headline"]["allowances_total"] == "2883.00"


@pytest.mark.django_db(transaction=True)
def test_summary_deduction_breakdown_with_percentages(env):
    """توزيع الحسومات بالنسب — للرسم الدائري."""
    with account_scope(env["account_id"]):
        run = _run(env, 3, unpaid_absent_days=D("3"))
        s = rs.summary_tab(run)
        types = {d["type"] for d in s["deduction_breakdown"]}
        assert "الغياب" in types and "التأمينات" in types
        total_pct = sum(float(d["percent"]) for d in s["deduction_breakdown"])
        assert 99.0 <= total_pct <= 101.0


@pytest.mark.django_db(transaction=True)
def test_summary_overtime_in_additions(env):
    with account_scope(env["account_id"]):
        run = _run(env, 3, approved_overtime_minutes=300)
        s = rs.summary_tab(run)
        assert D(s["headline"]["overtime_total"]) > 0
        assert any(a["type"] == "عمل إضافي"
                   for a in s["addition_breakdown"])


# ══════════ كشف الرواتب ══════════

@pytest.mark.django_db(transaction=True)
def test_payslips_tab_lists_all(env):
    with account_scope(env["account_id"]):
        run = _run(env, 3)
        rows = rs.payslips_tab(run)
        assert len(rows) == 2
        assert {r["employee_no"] for r in rows} == {"118", "201"}


@pytest.mark.django_db(transaction=True)
def test_payslips_tab_search(env):
    with account_scope(env["account_id"]):
        run = _run(env, 3)
        assert len(rs.payslips_tab(run, search="القحطاني")) == 1


# ══════════ المستبعدون ══════════

@pytest.mark.django_db(transaction=True)
def test_suspended_employee_excluded_with_reason(env):
    """الاستبعاد الصامت ممنوع — كل مستبعَد بسببه."""
    with account_scope(env["account_id"]):
        run = _run(env, 3)
        excluded = rs.excluded_tab(run)
        row = [x for x in excluded if x["employee_no"] == "301"]
        assert len(row) == 1
        assert "موقوف" in row[0]["reason"]


@pytest.mark.django_db(transaction=True)
def test_calculation_failures_appear_in_excluded(env):
    """من فشل احتسابه يظهر بسبب الفشل."""
    with account_scope(env["account_id"]):
        p4, _ = create_person(
            account=env["acc"], first_name_ar="بلا", family_name_ar="راتب",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077766655", mobile="0507776665", force=True)
        create_employment(person=p4, company=env["comp"],
                          employee_no="401", join_date=date(2024, 1, 1))
        run = _run(env, 3)
        assert any(x["employee_no"] == "401" for x in rs.excluded_tab(run))


# ══════════ الحسومات والإضافات ══════════

@pytest.mark.django_db(transaction=True)
def test_adjustments_show_explanation(env):
    """كل حسم يشرح احتسابه — «3 يوم × 375 ريال»."""
    with account_scope(env["account_id"]):
        run = _run(env, 3, unpaid_absent_days=D("3"))
        rows = rs.adjustments_tab(run)
        absence = [r for r in rows if r["reason"] == "خصم غياب"]
        assert absence and "يوم" in absence[0]["explanation"]


@pytest.mark.django_db(transaction=True)
def test_adjustments_exclude_fixed_components(env):
    """الأساسي والبدلات ليست حسومات ولا إضافات."""
    with account_scope(env["account_id"]):
        run = _run(env, 3)
        reasons = {r["reason"] for r in rs.adjustments_tab(run)}
        assert "الراتب الأساسي" not in reasons
        assert "بدل السكن" not in reasons


@pytest.mark.django_db(transaction=True)
def test_adjustments_filter_by_kind(env):
    with account_scope(env["account_id"]):
        run = _run(env, 3, unpaid_absent_days=D("2"))
        deductions = rs.adjustments_tab(run, kind="deduction")
        assert all(r["type"] == "استقطاع" for r in deductions)


# ══════════ التأمينات ══════════

@pytest.mark.django_db(transaction=True)
def test_gosi_tab_separates_nationalities(env):
    """
    الوافد لا يُخصم منه شيء — أي رقم غير صفري في خانته يكشف خطأً.
    """
    with account_scope(env["account_id"]):
        run = _run(env, 3)
        g = rs.gosi_tab(run)
        assert D(g["employee_saudi"]) > 0
        assert g["employee_non_saudi"] == "0.00"


@pytest.mark.django_db(transaction=True)
def test_gosi_total_due_is_sum(env):
    with account_scope(env["account_id"]):
        run = _run(env, 3)
        g = rs.gosi_tab(run)
        assert (D(g["total_due"]) ==
                D(g["employee_total"]) + D(g["employer_contribution"]))


# ══════════ المقارنة ══════════

@pytest.mark.django_db(transaction=True)
def test_comparison_flags_new_employee(env):
    with account_scope(env["account_id"]):
        _run(env, 2)
        run3 = _run(env, 3)
        # كلاهما موجود في الشهرين — لا جديد
        rows = rs.comparison_tab(run3)
        assert all(r["status"] != "جديد في المسير" for r in rows)


@pytest.mark.django_db(transaction=True)
def test_comparison_detects_change(env):
    with account_scope(env["account_id"]):
        _run(env, 2)
        run3 = _run(env, 3, unpaid_absent_days=D("5"))
        rows = rs.comparison_tab(run3)
        changed = [r for r in rows if r["employee_no"] == "201"]
        assert changed and D(changed[0]["difference"]) < 0


@pytest.mark.django_db(transaction=True)
def test_comparison_flags_departed(env):
    """من خرج من المسير يظهر صراحةً."""
    with account_scope(env["account_id"]):
        _run(env, 2)
        env["expat"].status = EmploymentStatus.SUSPENDED
        env["expat"].save()
        run3 = _run(env, 3)
        rows = rs.comparison_tab(run3)
        gone = [r for r in rows if r["employee_no"] == "118"]
        assert gone and gone[0]["status"] == "خرج من المسير"
        assert gone[0]["current_net"] is None


# ══════════ الأعداد ══════════

@pytest.mark.django_db(transaction=True)
def test_tab_counts(env):
    with account_scope(env["account_id"]):
        run = _run(env, 3, unpaid_absent_days=D("2"))
        counts = rs.tab_counts(run)
        assert counts["payslips"] == 2
        assert counts["excluded"] >= 1
        assert counts["adjustments"] >= 1


@pytest.mark.django_db(transaction=True)
def test_all_tabs_registered(env):
    """التبويبات الستة متاحة للواجهة."""
    assert set(rs.TABS) == {"summary", "payslips", "excluded",
                            "adjustments", "gosi", "comparison"}
