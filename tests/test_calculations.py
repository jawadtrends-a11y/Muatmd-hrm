"""
حرّاس الدوال المالية.

أخطر اختبارات المشروع — تمسّ فلوس الناس وحقوقهم.
لا يُعتمد أي تغيير في هذه الدوال قبل اجتيازها كاملة.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.payroll.services.calculations import (
    GosiError, calculate_absence_deduction, calculate_gosi,
    calculate_overtime, daily_rate, hourly_rate, r2,
)
from apps.payroll.services.gosi_seed import sync_gosi_rates

AUG = date(2026, 8, 1)


@pytest.fixture
def rates(db):
    return sync_gosi_rates()


# ══════════ التأمينات ══════════

@pytest.mark.django_db
def test_saudi_traditional_rates(rates):
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="traditional", as_of=AUG)
    assert g.employee_share == D("975.00")
    assert g.employer_share == D("1175.00")
    assert g.warnings == []


@pytest.mark.django_db
def test_non_saudi_pays_nothing(rates):
    """أشيع خطأ في أنظمة السوق: خصم شيء من راتب الوافد."""
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="non_saudi", as_of=AUG)
    assert g.employee_share == D("0.00"), "خُصم من الوافد — مخالفة صريحة"
    assert g.employer_share == D("200.00")


@pytest.mark.django_db
def test_company_input_never_silently_corrected(rates):
    """
    ق-20: نحفظ مدخلات الشركة ولا نصحّحها.
    أجر خارج الحدود يُحتسب كما هو مع تحذير — لا تعديل صامت.
    """
    low = calculate_gosi(subject_wage=D("1000"),
                         scheme_code="traditional", as_of=AUG)
    assert low.subject_wage == D("1000.00"), "صُحّح الأجر صامتًا"
    assert low.employee_share == D("97.50")
    assert len(low.warnings) == 1

    high = calculate_gosi(subject_wage=D("50000"),
                          scheme_code="traditional", as_of=AUG)
    assert high.subject_wage == D("50000.00"), "قُصّ الأجر صامتًا"
    assert high.employee_share == D("4875.00")
    assert len(high.warnings) == 1


@pytest.mark.django_db
def test_within_limits_has_no_warnings(rates):
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="traditional", as_of=AUG)
    assert g.warnings == []
    assert g.breakdown["out_of_range"] is False


@pytest.mark.django_db
def test_rate_read_by_accrual_date_not_today(rates):
    """إعادة احتساب مسير قديم تعطي نفس الأرقام دائمًا."""
    old = calculate_gosi(subject_wage=D("10000"), scheme_code="new_scheme",
                         as_of=date(2024, 8, 1))
    new = calculate_gosi(subject_wage=D("10000"), scheme_code="new_scheme",
                         as_of=date(2027, 8, 1))
    assert old.employee_share == D("975.00")
    assert old.employee_share != new.employee_share


@pytest.mark.django_db
def test_new_scheme_not_effective_before_july_2024(rates):
    with pytest.raises(GosiError):
        calculate_gosi(subject_wage=D("10000"), scheme_code="new_scheme",
                       as_of=date(2024, 1, 1))


@pytest.mark.django_db
def test_breakdown_records_rate_version(rates):
    """كل احتساب يسجّل نسخة النسبة — للتدقيق."""
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="traditional", as_of=AUG)
    assert g.breakdown["rate_id"]
    assert g.breakdown["rate_effective_from"]
    assert g.breakdown["scheme"] == "traditional"


# ══════════ أجر الساعة واليوم ══════════

def test_hourly_rate_saudi_standard():
    assert hourly_rate(D("12000")) == D("50")
    assert daily_rate(D("12000")) == D("400")


def test_hourly_rate_rejects_zero():
    with pytest.raises(ValueError):
        hourly_rate(D("12000"), days_per_month=0)
    with pytest.raises(ValueError):
        hourly_rate(D("12000"), hours_per_day=D("0"))


# ══════════ العمل الإضافي ══════════

def test_overtime_default_basis():
    """قرار المالك: أجر ساعة الأجر الكامل + 50% من ساعة الأساسي."""
    o = calculate_overtime(overtime_minutes=600, basic_salary=D("8000"),
                           full_wage=D("12000"),
                           basis="full_plus_half_basic")
    assert o.hourly_amount == D("66.67")
    assert o.total == D("666.67")


def test_overtime_all_three_bases_differ():
    kw = dict(overtime_minutes=600, basic_salary=D("8000"),
              full_wage=D("12000"))
    a = calculate_overtime(basis="full_plus_half_basic", **kw).total
    b = calculate_overtime(basis="basic_x1_5", **kw).total
    c = calculate_overtime(basis="full_x1_5", **kw).total
    assert (a, b, c) == (D("666.67"), D("500.00"), D("750.00"))


def test_overtime_rejects_unknown_basis():
    with pytest.raises(ValueError):
        calculate_overtime(overtime_minutes=60, basic_salary=D("8000"),
                           full_wage=D("12000"), basis="whatever")


def test_overtime_explains_itself():
    """كل احتساب يشرح نفسه — يُنهي أغلب نزاعات الموظفين."""
    o = calculate_overtime(overtime_minutes=600, basic_salary=D("8000"),
                           full_wage=D("12000"),
                           basis="full_plus_half_basic")
    assert "ساعة" in o.explanation and "ريال" in o.explanation


# ══════════ خصم الغياب ══════════

def test_absence_uses_same_daily_rate():
    assert calculate_absence_deduction(
        unpaid_days=D("3"), monthly_wage=D("12000")) == D("1200.00")


def test_settings_days_per_month_respected():
    a = calculate_absence_deduction(unpaid_days=D("1"),
                                    monthly_wage=D("3000"), days_per_month=30)
    b = calculate_absence_deduction(unpaid_days=D("1"),
                                    monthly_wage=D("3000"), days_per_month=31)
    assert a == D("100.00") and b != a


def test_no_float_precision_loss():
    total = sum((r2(D("0.1")) for _ in range(10)), D("0"))
    assert total == D("1.00")


# ══════════ تحمّل الشركة لحصة الموظف (ق-29) ══════════

@pytest.mark.django_db
def test_default_deducts_from_employee(rates):
    """الافتراض: الخصم من الموظف — الوضع النظامي الطبيعي."""
    from apps.payroll.services.calculations import allocate_gosi
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="traditional", as_of=AUG)
    a = allocate_gosi(gosi_result=g)
    assert a.employee_deduction == D("975.00")
    assert a.company_absorbed == D("0")


@pytest.mark.django_db
def test_company_bears_employee_share(rates):
    """عند التحمّل: الخصم الفعلي صفر والشركة تستوعب الحصة."""
    from apps.payroll.services.calculations import allocate_gosi
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="traditional", as_of=AUG)
    a = allocate_gosi(gosi_result=g, company_bears_employee_share=True)
    assert a.employee_deduction == D("0")
    assert a.company_absorbed == D("975.00")


@pytest.mark.django_db
def test_remitted_amount_identical_either_way(rates):
    """المبلغ المورَّد للتأمينات لا يتغير — الفرق في من يتحمله."""
    from apps.payroll.services.calculations import allocate_gosi
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="traditional", as_of=AUG)
    a = allocate_gosi(gosi_result=g)
    b = allocate_gosi(gosi_result=g, company_bears_employee_share=True)
    assert a.total_remitted == b.total_remitted == D("2150.00")


@pytest.mark.django_db
def test_payslip_shows_borne_line_transparently(rates):
    """
    ق-29: الشفافية — الموظف يرى أن عليه حصة وأن الشركة تحملتها،
    لا يظن نفسه معفى من التأمينات.
    """
    from apps.payroll.services.calculations import allocate_gosi
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="traditional", as_of=AUG)
    a = allocate_gosi(gosi_result=g, company_bears_employee_share=True)
    codes = [l["code"] for l in a.payslip_lines]
    assert "GOSI_EMP" in codes, "بند الخصم مخفي"
    assert "GOSI_BORNE" in codes, "بند التحمّل مفقود"
    deduction = sum(l["amount"] for l in a.payslip_lines
                    if l["type"] == "deduction")
    offset = sum(l["amount"] for l in a.payslip_lines
                 if l["code"] == "GOSI_BORNE")
    assert deduction == offset, "الأثر الصافي ليس صفرًا"


@pytest.mark.django_db
def test_non_saudi_has_no_borne_line(rates):
    """الوافد بلا حصة أصلًا — لا بند تحمّل."""
    from apps.payroll.services.calculations import allocate_gosi
    g = calculate_gosi(subject_wage=D("10000"),
                       scheme_code="non_saudi", as_of=AUG)
    a = allocate_gosi(gosi_result=g, company_bears_employee_share=True)
    assert a.company_absorbed == D("0.00")
    assert "GOSI_BORNE" not in [l["code"] for l in a.payslip_lines]
