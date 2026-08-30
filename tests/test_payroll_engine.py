"""
حرّاس محرك الرواتب — أخطر طبقة في النظام.

تمسّ فلوس الناس شهريًا. لا يُعتمد تغيير فيها قبل اجتيازها كاملة.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceMonthlySummary
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    PayComponent, PayrollRun, PayrollRunStatus, PayrollRunType,
    PayrollSettings, Payslip,
)
from apps.payroll.services.engine import (
    PayrollError, approve_run, calculate_run, create_run, submit_run,
    variance_report,
)
from apps.payroll.services.gosi_seed import sync_gosi_rates

IBAN = "SA0380000000608010167519"


@pytest.fixture
def env(db):
    sync_gosi_rates()
    r = provision_account(slug="eng-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}

        p1, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556",
            gosi_scheme_code="traditional")
        e1, _, _ = create_employment(
            person=p1, company=comp, employee_no="E-001",
            join_date=date(2020, 1, 1), iban=IBAN,
            salary_lines=[(comps["BASIC"], D("8000")),
                          (comps["HOUSING"], D("2000")),
                          (comps["TRANSPORT"], D("1000"))])
        e1.is_gosi_registered = True
        e1.include_in_wps = True
        e1.save()

        p2, _ = create_person(
            account=acc, first_name_ar="راشد", family_name_ar="خان",
            gender="male", nationality_code="PK", id_type="iqama",
            id_number="2011122233", mobile="0501112224")
        e2, _, _ = create_employment(
            person=p2, company=comp, employee_no="E-002",
            join_date=date(2023, 1, 1), iban=IBAN,
            salary_lines=[(comps["BASIC"], D("4000")),
                          (comps["HOUSING"], D("1000"))])

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "comps": comps, "saudi": e1, "expat": e2, "person": p1,
               "settings": PayrollSettings.objects.get(company=comp)}


def _run(env, year=2026, month=3):
    return create_run(company=env["comp"], run_type=PayrollRunType.REGULAR,
                      year=year, month=month)


def _summary(env, emp, **kw):
    defaults = {"account": env["acc"], "company": env["comp"],
                "worked_days": D("22"), "unpaid_absent_days": D("0"),
                "paid_leave_days": D("0"), "late_minutes": 0,
                "approved_overtime_minutes": 0}
    defaults.update(kw)
    return AttendanceMonthlySummary.objects.update_or_create(
        employment=emp, period_year=2026, period_month=3,
        defaults=defaults)[0]


# ══════════ الاحتساب الأساسي ══════════

@pytest.mark.django_db(transaction=True)
def test_basic_calculation(env):
    with account_scope(env["account_id"]):
        run = _run(env)
        res = calculate_run(run)
        assert res.calculated == 2 and res.failed == 0
        run.refresh_from_db()
        assert run.status == PayrollRunStatus.CALCULATED


@pytest.mark.django_db(transaction=True)
def test_gosi_deducted_for_registered_saudi(env):
    with account_scope(env["account_id"]):
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.gosi_subject_wage == D("10000.00")
        assert slip.gosi_employee_share == D("975.00")
        assert slip.net_pay == D("10025.00")


@pytest.mark.django_db(transaction=True)
def test_unregistered_employee_has_no_gosi(env):
    """ق-15: التوظيف مستقل عن التسجيل."""
    with account_scope(env["account_id"]):
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["expat"])
        assert slip.gosi_employee_share == D("0.00")
        assert slip.net_pay == D("5000.00")


@pytest.mark.django_db(transaction=True)
def test_accrual_date_drives_rates(env):
    """النسب تُقرأ بتاريخ الاستحقاق — إعادة الاحتساب ثابتة."""
    with account_scope(env["account_id"]):
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.calculation_trace["accrual_date"] == "2026-03-31"
        assert slip.calculation_trace["gosi"]["scheme"] == "traditional"


# ══════════ الصافي لا ينزل عن صفر (ق-37) ══════════

@pytest.mark.django_db(transaction=True)
def test_net_never_negative(env):
    with account_scope(env["account_id"]):
        _summary(env, env["saudi"], unpaid_absent_days=D("40"))
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.net_pay == D("0.00"), "الصافي سالب"
        assert slip.total_deductions == slip.gross_earnings


@pytest.mark.django_db(transaction=True)
def test_zero_net_excluded_from_wps(env):
    with account_scope(env["account_id"]):
        _summary(env, env["saudi"], unpaid_absent_days=D("40"))
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.include_in_wps is False


@pytest.mark.django_db(transaction=True)
def test_capping_is_transparent(env):
    """القص يظهر بندًا صريحًا وتنبيهًا — لا إخفاء."""
    with account_scope(env["account_id"]):
        _summary(env, env["saudi"], unpaid_absent_days=D("40"))
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.lines.filter(component_code="DED_CAP").exists()
        assert any("تتجاوز الاستحقاق" in w for w in slip.warnings)


# ══════════ أساس خصم الغياب (ق-36) ══════════

@pytest.mark.django_db(transaction=True)
def test_absence_deducted_from_gross_by_default(env):
    with account_scope(env["account_id"]):
        _summary(env, env["saudi"], unpaid_absent_days=D("3"))
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.calculation_trace["earnings"]["absence_base"] == "11000.00"
        assert slip.lines.get(component_code="ABSENCE").amount == D("1100.00")


@pytest.mark.django_db(transaction=True)
def test_company_can_exclude_allowance_from_absence_base(env):
    """ق-36: الشركة تستثني بدلًا بإطفاء العلم."""
    with account_scope(env["account_id"]):
        env["comps"]["TRANSPORT"].is_absence_base = False
        env["comps"]["TRANSPORT"].save()
        _summary(env, env["saudi"], unpaid_absent_days=D("3"))
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.calculation_trace["earnings"]["absence_base"] == "10000.00"


# ══════════ الغياب والإجازة بلا أجر منفصلان (ق-32) ══════════

@pytest.mark.django_db(transaction=True)
def test_absence_and_unpaid_leave_separate(env):
    with account_scope(env["account_id"]):
        _summary(env, env["saudi"], unpaid_absent_days=D("2"))
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.unpaid_absence_days == D("2")
        assert slip.unpaid_leave_days == D("0")
        assert slip.lines.filter(component_code="ABSENCE").exists()
        assert not slip.lines.filter(component_code="UNPAID_LEAVE").exists()


# ══════════ العمل الإضافي ══════════

@pytest.mark.django_db(transaction=True)
def test_only_approved_overtime_is_paid(env):
    with account_scope(env["account_id"]):
        _summary(env, env["saudi"], approved_overtime_minutes=600)
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        assert slip.overtime_minutes == 600
        # 10 ساعات × (45.83 ساعة الكامل + 16.67 نصف ساعة الأساسي) = 625
        assert slip.lines.get(component_code="OVERTIME").amount == D("625.00")


# ══════════ دورة المسير ══════════

@pytest.mark.django_db(transaction=True)
def test_duplicate_run_blocked(env):
    with account_scope(env["account_id"]):
        _run(env)
        with pytest.raises(PayrollError):
            _run(env)


@pytest.mark.django_db(transaction=True)
def test_run_lifecycle(env):
    with account_scope(env["account_id"]):
        run = _run(env)
        calculate_run(run)
        run.refresh_from_db()
        submit_run(run)
        run.refresh_from_db()
        assert run.status == PayrollRunStatus.SUBMITTED
        approve_run(run, env["person"])
        run.refresh_from_db()
        assert run.status == PayrollRunStatus.APPROVED


@pytest.mark.django_db(transaction=True)
def test_approved_run_cannot_be_recalculated(env):
    """المعتمد سجل مالي نهائي."""
    with account_scope(env["account_id"]):
        run = _run(env)
        calculate_run(run)
        run.refresh_from_db()
        submit_run(run)
        run.refresh_from_db()
        approve_run(run, env["person"])
        run.refresh_from_db()
        with pytest.raises(PayrollError):
            calculate_run(run)


@pytest.mark.django_db(transaction=True)
def test_cannot_submit_before_calculation(env):
    with account_scope(env["account_id"]):
        with pytest.raises(PayrollError):
            submit_run(_run(env))


@pytest.mark.django_db(transaction=True)
def test_recalculation_is_deterministic(env):
    """إعادة الاحتساب تعطي نفس الأرقام — شرط التدقيق."""
    with account_scope(env["account_id"]):
        run = _run(env)
        calculate_run(run)
        first = Payslip.objects.get(run=run, employment=env["saudi"]).net_pay
        run.status = PayrollRunStatus.DRAFT
        run.save()
        calculate_run(run)
        second = Payslip.objects.get(run=run, employment=env["saudi"]).net_pay
        assert first == second


# ══════════ كشف الفروقات ══════════

@pytest.mark.django_db(transaction=True)
def test_variance_detected(env):
    """شاشة المراجعة قبل الاعتماد تمنع أغلب كوارث الرواتب."""
    with account_scope(env["account_id"]):
        feb = create_run(company=env["comp"],
                         run_type=PayrollRunType.REGULAR, year=2026, month=2)
        calculate_run(feb)
        _summary(env, env["saudi"], unpaid_absent_days=D("10"))
        mar = _run(env)
        calculate_run(mar)
        mar.refresh_from_db()
        assert mar.variance_count >= 1
        assert any(r["employee_no"] == "E-001" for r in variance_report(mar))


# ══════════ الشفافية ══════════

@pytest.mark.django_db(transaction=True)
def test_every_line_explains_itself(env):
    """الموظف يعيد الحساب بورقة وقلم."""
    with account_scope(env["account_id"]):
        _summary(env, env["saudi"], unpaid_absent_days=D("2"),
                 approved_overtime_minutes=120)
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        for line in slip.lines.all():
            assert line.explanation, f"بند بلا شرح: {line.name_ar}"


@pytest.mark.django_db(transaction=True)
def test_calculation_trace_complete(env):
    with account_scope(env["account_id"]):
        run = _run(env)
        calculate_run(run)
        slip = Payslip.objects.get(run=run, employment=env["saudi"])
        for key in ("accrual_date", "salary_structure", "attendance",
                    "earnings", "gosi", "totals"):
            assert key in slip.calculation_trace, f"مفقود: {key}"


@pytest.mark.django_db(transaction=True)
def test_failure_does_not_stop_run(env):
    """فشل موظف لا يوقف الباقين."""
    with account_scope(env["account_id"]):
        p3, _ = create_person(
            account=env["acc"], first_name_ar="بلا", family_name_ar="راتب",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077766655", mobile="0507776665")
        create_employment(person=p3, company=env["comp"],
                          employee_no="E-003", join_date=date(2024, 1, 1))
        res = calculate_run(_run(env))
        assert res.calculated == 2 and res.failed == 1
        assert any(e["employee_no"] == "E-003" for e in res.errors)


@pytest.mark.django_db(transaction=True)
def test_payroll_isolated_between_accounts(env, rls_enforced_late):
    other = provision_account(slug="eng-other", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(env["account_id"]):
        calculate_run(_run(env))
    rls_enforced_late()
    with account_scope(other.account_id):
        assert Payslip.objects.count() == 0
        assert PayrollRun.objects.count() == 0
