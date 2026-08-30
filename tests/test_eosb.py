"""
مصفوفة اختبارات مكافأة نهاية الخدمة.

أخطر اختبارات المشروع — تُسأل عنها في المحاكم العمالية.
لا يُعتمد أي تعديل في الدالة قبل اجتيازها كاملة.

الأساس (ق-22): السنة 360 يومًا والشهر 30، بالتفكيك لا بالأيام الفعلية.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.payroll.services.eosb import (
    ALL_REASONS, EOSBBasisNotSet, EOSBError, FULL_ENTITLEMENT,
    NO_ENTITLEMENT, calculate_eosb, resignation_ratio, service_days_360,
    warn_on_component_exclusion,
)

W = D("12000")


def _eosb(jd, ed, code, wage=W, **kw):
    return calculate_eosb(join_date=jd, end_date=ed, eosb_wage=wage,
                          reason_code=code, **kw)


# ══════════ دالة المدة (ق-22) ══════════

def test_service_days_uses_360_decomposition():
    """التفكيك لا الأيام الفعلية — 7 سنوات = 2520 لا 2557."""
    assert service_days_360(date(2019, 1, 1), date(2026, 1, 1)) == 2520
    assert service_days_360(date(2021, 7, 1), date(2026, 1, 1)) == 1620


def test_service_days_matches_official_example():
    """مثال المرجع: 4 سنوات و6 شهور و15 يومًا = 1635 يومًا."""
    assert service_days_360(date(2020, 1, 1), date(2024, 7, 16)) == 1635


def test_service_days_handles_day_borrow():
    """اقتراض الأيام من الشهر يستخدم 30 لا عدد أيام الشهر الفعلي."""
    assert service_days_360(date(2025, 1, 20), date(2026, 1, 10)) == 350


# ══════════ الحالات الكاملة ══════════

@pytest.mark.parametrize("code", sorted(FULL_ENTITLEMENT))
def test_full_entitlement_reasons(code):
    r = _eosb(date(2019, 1, 1), date(2026, 1, 1), code)
    assert r.entitlement_ratio == D("1")
    assert r.net_award == D("54000.00")


@pytest.mark.parametrize("code", sorted(NO_ENTITLEMENT))
def test_no_entitlement_reasons(code):
    r = _eosb(date(2018, 1, 1), date(2026, 1, 1), code)
    assert r.net_award == D("0.00")


# ══════════ الاستقالة (م/85) ══════════

@pytest.mark.parametrize("years,expected_ratio", [
    (D("1.5"), D("0")),
    (D("2"), D("1") / D("3")),
    (D("4.99"), D("1") / D("3")),
    (D("5"), D("2") / D("3")),
    (D("9.99"), D("2") / D("3")),
    (D("10"), D("1")),
    (D("15"), D("1")),
])
def test_resignation_ratio_brackets(years, expected_ratio):
    assert resignation_ratio(years) == expected_ratio


def test_resignation_under_two_years_gets_nothing():
    r = _eosb(date(2024, 7, 1), date(2026, 1, 1), "resignation")
    assert r.net_award == D("0.00")


def test_resignation_three_years_gets_third():
    r = _eosb(date(2023, 1, 1), date(2026, 1, 1), "resignation")
    assert r.gross_award == D("18000.00")
    assert r.net_award == D("6000.00")


def test_resignation_seven_years_gets_two_thirds():
    r = _eosb(date(2019, 1, 1), date(2026, 1, 1), "resignation")
    assert r.gross_award == D("54000.00")
    assert r.net_award == D("36000.00")


def test_resignation_twelve_years_gets_full():
    r = _eosb(date(2014, 1, 1), date(2026, 1, 1), "resignation")
    assert r.entitlement_ratio == D("1")
    assert r.net_award == D("114000.00")


# ══════════ استثناءات المادة 87 ══════════

def test_female_marriage_gets_full_despite_short_service():
    """م/87: المرأة خلال 6 أشهر من الزواج — كاملة لا الثلث."""
    r = _eosb(date(2023, 1, 1), date(2026, 1, 1), "female_marriage")
    assert r.entitlement_ratio == D("1")
    assert r.net_award == D("18000.00")


def test_female_childbirth_gets_full():
    r = _eosb(date(2023, 1, 1), date(2026, 1, 1), "female_childbirth")
    assert r.net_award == D("18000.00")


def test_article_81_treated_as_full_entitlement():
    """م/81: ترك العمل لإخلال صاحب العمل — كاملة لا استقالة."""
    r = _eosb(date(2024, 1, 1), date(2026, 1, 1), "article_81")
    assert r.entitlement_ratio == D("1")


# ══════════ قاعدة المادة 84 ══════════

def test_first_five_years_half_month_each():
    r = _eosb(date(2021, 1, 1), date(2026, 1, 1), "unlawful_termination")
    assert r.service_years == D("5.00")
    assert r.net_award == D("30000.00")     # 5 × نصف شهر


def test_after_five_years_full_month_each():
    r = _eosb(date(2016, 1, 1), date(2026, 1, 1), "unlawful_termination")
    assert r.service_years == D("10.00")
    assert r.net_award == D("90000.00")     # 2.5 + 5 = 7.5 شهر


def test_partial_year_prorated():
    """أجزاء السنة بالتناسب — 6 أشهر = نصف سنة."""
    r = _eosb(date(2025, 7, 1), date(2026, 1, 1), "unlawful_termination")
    assert r.service_days == 180
    assert r.net_award == D("3000.00")      # 0.5 سنة × نصف شهر × 12000


# ══════════ الحماية والتحقق ══════════

def test_unknown_reason_rejected():
    """لا حالة مجهولة — كل سبب نظامي مذكور صراحةً (طلب المالك)."""
    with pytest.raises(EOSBError):
        _eosb(date(2020, 1, 1), date(2026, 1, 1), "something_else")


def test_official_ministry_reason_list():
    """ق-26: القائمة معتمدة حرفيًا من حاسبة الوزارة الرسمية."""
    assert len(ALL_REASONS) == 16
    for label in ALL_REASONS.values():
        assert label.strip(), "حالة بلا وصف نظامي"


def test_wage_basis_must_be_set_first():
    """ق-21: الصمت في أجر المكافأة قرار مالي لم يتخذه أحد."""
    with pytest.raises(EOSBBasisNotSet):
        _eosb(date(2020, 1, 1), date(2026, 1, 1), "resignation",
              wage_basis_set=False)


def test_end_before_start_rejected():
    with pytest.raises(EOSBError):
        _eosb(date(2026, 1, 1), date(2020, 1, 1), "resignation")


def test_unpaid_leave_excluded_only_if_company_chose():
    """ق-24: خيار الشركة — لا افتراض مفروض."""
    kept = _eosb(date(2019, 1, 1), date(2026, 1, 1), "unlawful_termination",
                 unpaid_leave_days=90, exclude_unpaid_leave=False)
    dropped = _eosb(date(2019, 1, 1), date(2026, 1, 1), "unlawful_termination",
                    unpaid_leave_days=90, exclude_unpaid_leave=True)
    assert kept.service_days == 2520
    assert dropped.service_days == 2430
    assert dropped.net_award < kept.net_award
    assert len(dropped.warnings) == 1


def test_explanation_printed_for_settlement_document():
    """شرح الاحتساب يُنهي أغلب النزاعات — يُطبع في مستند التسوية."""
    r = _eosb(date(2019, 1, 1), date(2026, 1, 1), "unlawful_termination")
    assert len(r.explanation) >= 8
    assert any("360" in line for line in r.explanation)
    assert r.reason_label == "إنهاء صاحب العمل للعقد لسبب غير مشروع"


def test_component_exclusion_warning(  ):
    """ق-23: تحذير لا منع."""
    msg = warn_on_component_exclusion("بدل السكن", "is_eosb_subject")
    assert "بدل السكن" in msg and "مكافأة نهاية الخدمة" in msg


# ══════════ مطابقة الحاسبة الرسمية (ق-25) ══════════

def test_matches_official_hrsd_calculator_mutual_agreement():
    """
    المرجع: حاسبة وزارة الموارد البشرية الرسمية.
    4 سنوات و6 أشهر و15 يومًا على أجر 3000 = 6812.50 ريال.
    """
    r = calculate_eosb(join_date=date(2020, 1, 1), end_date=date(2024, 7, 16),
                       eosb_wage=D("3000"), reason_code="mutual_agreement")
    assert r.service_days == 1635
    assert r.net_award == D("6812.50")


def test_matches_official_hrsd_calculator_resignation():
    """نفس المعطيات باستقالة = 2270.83 ريال (الثلث)."""
    r = calculate_eosb(join_date=date(2020, 1, 1), end_date=date(2024, 7, 16),
                       eosb_wage=D("3000"), reason_code="resignation")
    assert r.net_award == D("2270.83")


@pytest.mark.parametrize("start,end,expected", [
    (date(2021, 1, 1), date(2026, 1, 1), D("30000.00")),   # 5 سنوات
    (date(2019, 1, 1), date(2026, 1, 1), D("54000.00")),   # 7 سنوات
    (date(2016, 1, 1), date(2026, 1, 1), D("90000.00")),   # 10 سنوات
])
def test_round_years_give_round_amounts(start, end, expected):
    """
    ق-25: المدد المستديرة تخرج مستديرة.
    التقريب المرحلي كان يعطي 53,985 لسبع سنوات — خطأ يأكل من الحق.
    """
    r = calculate_eosb(join_date=start, end_date=end, eosb_wage=W,
                       reason_code="unlawful_termination")
    assert r.net_award == expected


# ══════════ تعويض المادة 77 (ق-26) ══════════

def test_article_77_indefinite_contract():
    """15 يومًا عن كل سنة — 7 سنوات على 12000 = 42,000."""
    from apps.payroll.services.eosb import (
        calculate_unlawful_termination_compensation as comp,
    )
    c = comp(monthly_wage=W, service_days=2520)
    assert c.amount == D("42000.00")
    assert not c.minimum_applied


def test_article_77_minimum_two_months():
    """الحد الأدنى أجر شهرين — يُطبَّق للمدد القصيرة."""
    from apps.payroll.services.eosb import (
        calculate_unlawful_termination_compensation as comp,
    )
    c = comp(monthly_wage=W, service_days=360)
    assert c.amount == D("24000.00")
    assert c.minimum_applied


def test_article_77_fixed_term_uses_remaining_period():
    """عقد محدد المدة: أجر المدة المتبقية."""
    from apps.payroll.services.eosb import (
        calculate_unlawful_termination_compensation as comp,
    )
    c = comp(monthly_wage=W, service_days=720,
             contract_type="fixed_term", remaining_contract_months=D("8"))
    assert c.amount == D("96000.00")


def test_article_77_fixed_term_requires_remaining_months():
    from apps.payroll.services.eosb import (
        calculate_unlawful_termination_compensation as comp,
    )
    with pytest.raises(EOSBError):
        comp(monthly_wage=W, service_days=720, contract_type="fixed_term")


def test_article_77_is_separate_from_eosb():
    """
    ق-26: التعويض بند مستقل لا يُدمج في المكافأة.
    طبيعته تعويض عن ضرر لا مكافأة عن مدة خدمة.
    """
    from apps.payroll.services.eosb import (
        calculate_unlawful_termination_compensation as comp,
    )
    r = calculate_eosb(join_date=date(2019, 1, 1), end_date=date(2026, 1, 1),
                       eosb_wage=W, reason_code="unlawful_termination")
    c = comp(monthly_wage=W, service_days=r.service_days)
    assert r.net_award == D("54000.00")
    assert c.amount == D("42000.00")
    assert r.net_award + c.amount == D("96000.00")


# ══════════ تعويض المادة 77 (ق-26 و ق-27) ══════════

from apps.payroll.services.eosb import (  # noqa: E402
    calculate_unlawful_termination_compensation as _comp,
)


def test_article_77_statutory_indefinite():
    c = _comp(monthly_wage=W, service_days=2520)
    assert c.amount == D("42000.00")
    assert not c.minimum_applied


def test_article_77_minimum_two_months():
    c = _comp(monthly_wage=W, service_days=360)
    assert c.amount == D("24000.00")
    assert c.minimum_applied


def test_article_77_fixed_term_remaining_period():
    c = _comp(monthly_wage=W, service_days=720,
              contract_type="fixed_term", remaining_contract_months=D("8"))
    assert c.amount == D("96000.00")


def test_article_77_fixed_term_requires_remaining_months():
    with pytest.raises(EOSBError):
        _comp(monthly_wage=W, service_days=720, contract_type="fixed_term")


def test_article_77_agreed_amount_wins():
    """ق-27: الاتفاق يسبق الحد النظامي."""
    c = _comp(monthly_wage=W, service_days=720, agreed_amount=D("50000"))
    assert c.amount == D("50000.00")


def test_article_77_low_agreed_amount_warns_not_blocks():
    """ق-20: تحذير لا منع — النظام لا يصحّح مدخلات الشركة."""
    c = _comp(monthly_wage=W, service_days=720, agreed_amount=D("10000"))
    assert c.amount == D("10000.00"), "رُفع المبلغ صامتًا"
    assert any("تنبيه" in line for line in c.explanation)


def test_article_77_separate_from_eosb():
    """التعويض بند مستقل لا يُدمج في المكافأة."""
    r = calculate_eosb(join_date=date(2019, 1, 1), end_date=date(2026, 1, 1),
                       eosb_wage=W, reason_code="unlawful_termination")
    c = _comp(monthly_wage=W, service_days=r.service_days)
    assert r.net_award == D("54000.00")
    assert c.amount == D("42000.00")
