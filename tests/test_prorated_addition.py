"""
حارس فرق إضافة الموظفين — بالأيام لا بالأشهر (ق-108).

⚠️ ماليّ: من أضاف موظفًا وبقي ٨٧ يومًا يدفع عنها بالضبط — لا عن
ثلاثة أشهر مقرّبة ولا عن سنة كاملة.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models_billing import Plan, PlanPriceTier
from apps.accounts.models_billing_v2 import BillingCycle
from apps.accounts.services import billing_v2 as b


@pytest.fixture
def plan(db):
    p = Plan.objects.create(code="t-basic", name_ar="اختبار",
                            base_fee_monthly=Decimal("0"),
                            min_billable_employees=1, trial_days=14)
    PlanPriceTier.objects.create(
        plan=p, from_employees=1, to_employees=25,
        price_per_employee_monthly=Decimal("15"),
        price_per_employee_yearly=Decimal("180"))
    PlanPriceTier.objects.create(
        plan=p, from_employees=26, to_employees=None,
        price_per_employee_monthly=Decimal("12"),
        price_per_employee_yearly=Decimal("144"))
    return p


class _Sub:
    def __init__(self, plan, cycle, employees, start, end):
        self.plan = plan
        self.cycle = cycle
        self.subscribed_employees = employees
        self.current_period_start = start
        self.current_period_end = end


def test_annual_addition_is_by_days(plan):
    """سنويّ ١٨٠ للموظف، وبقي ٨٧ يومًا → ٤٢.٩٠ لا ٤٥ ولا ١٨٠."""
    sub = _Sub(plan, BillingCycle.ANNUAL, 20,
               date(2026, 1, 1), date(2027, 1, 1))
    r = b.prorated_addition(subscription=sub, added=1,
                            as_of=date(2026, 10, 6))
    assert r["days_remaining"] == 87
    assert Decimal(r["amount"]) == Decimal("42.90")


def test_monthly_addition_is_by_days(plan):
    """شهريّ ١٥، ثلاثة موظفين، ١٦ يومًا من ٣١ → ٢٣.٢٣."""
    sub = _Sub(plan, BillingCycle.MONTHLY, 20,
               date(2026, 10, 1), date(2026, 11, 1))
    r = b.prorated_addition(subscription=sub, added=3,
                            as_of=date(2026, 10, 16))
    assert r["days_remaining"] == 16
    assert Decimal(r["amount"]) == Decimal("23.23")


def test_crossing_a_cheaper_tier_uses_it(plan):
    """
    من عبَر حدّ شريحة أرخص يستفيد منها فورًا.

    ٢٥ موظفًا + ١ = ٢٦ → الشريحة الثانية (١٤٤ لا ١٨٠)، فالفرق
    ليس سعر موظف واحد بل فرق الإجماليّين.
    """
    sub = _Sub(plan, BillingCycle.ANNUAL, 25,
               date(2026, 1, 1), date(2027, 1, 1))
    r = b.prorated_addition(subscription=sub, added=1,
                            as_of=date(2026, 1, 1))
    # 26×144 = 3744 ، و25×180 = 4500 → الفرق سالب: أرخص بعد العبور
    assert Decimal(r["amount"]) < 0


def test_no_remaining_days_is_refused(plan):
    """فترة منتهية لا تُحتسب عليها إضافة — يُجدَّد أولًا."""
    sub = _Sub(plan, BillingCycle.ANNUAL, 20,
               date(2025, 1, 1), date(2026, 1, 1))
    with pytest.raises(b.BillingError):
        b.prorated_addition(subscription=sub, added=1,
                            as_of=date(2026, 6, 1))


def test_zero_or_negative_addition_is_refused(plan):
    sub = _Sub(plan, BillingCycle.MONTHLY, 5,
               date(2026, 10, 1), date(2026, 11, 1))
    with pytest.raises(b.BillingError):
        b.prorated_addition(subscription=sub, added=0,
                            as_of=date(2026, 10, 5))


# ══════════ عرض السعر (ق-108) ══════════

def test_quote_is_unit_times_employees(plan):
    """سعر واحد للموظف بلا شرائح: ٢٠ × ١٥ = ٣٠٠."""
    q = b.quote(plan=plan, employees=20, cycle=BillingCycle.MONTHLY,
                vat_rate=0.15)
    assert Decimal(q["subscription"]) == Decimal("300.00")
    assert Decimal(q["vat"]) == Decimal("45.00")
    assert Decimal(q["total"]) == Decimal("345.00")


def test_setup_fee_is_once_and_not_in_renewal(plan):
    """
    ⚠️ رسم الإعداد **مرّة واحدة**: يدخل الفاتورة الأولى ولا يدخل
    التجديد — ومن يكرّره يُطالب العميل بما لم يشترِه.
    """
    Plan.objects.filter(id=plan.id).update(setup_fee=Decimal("500"))
    plan.refresh_from_db()
    q = b.quote(plan=plan, employees=20, cycle=BillingCycle.MONTHLY,
                with_setup=True, vat_rate=0.15)
    assert Decimal(q["setup_fee"]) == Decimal("500.00")
    assert Decimal(q["total"]) == Decimal("920.00")
    assert Decimal(q["renewal_total"]) == Decimal("345.00"), \
        "رسم الإعداد تكرّر في التجديد"


def test_quote_without_setup_excludes_it(plan):
    """من لم يختره لا يُحاسَب عليه."""
    Plan.objects.filter(id=plan.id).update(setup_fee=Decimal("500"))
    plan.refresh_from_db()
    q = b.quote(plan=plan, employees=10, cycle=BillingCycle.MONTHLY,
                with_setup=False, vat_rate=0.15)
    assert Decimal(q["setup_fee"]) == Decimal("0")
    assert Decimal(q["total"]) == Decimal("172.50")


def test_quote_refuses_zero_employees(plan):
    with pytest.raises(b.BillingError):
        b.quote(plan=plan, employees=0, cycle=BillingCycle.MONTHLY)


def test_vat_comes_from_platform_settings(plan, db):
    """
    النسبة من إعدادات المنصّة لا ثابتًا في الكود — فتغييرها قرار
    نظاميّ يقع، وثابتٌ مدفون يحتاج نشرًا.
    """
    from apps.accounts.models_platform import get_settings
    st = get_settings()
    st.vat_rate = Decimal("5")
    st.save(update_fields=["vat_rate"])
    q = b.quote(plan=plan, employees=10, cycle=BillingCycle.MONTHLY)
    assert Decimal(q["vat"]) == Decimal("7.50"), q
    st.vat_rate = Decimal("15")
    st.save(update_fields=["vat_rate"])
