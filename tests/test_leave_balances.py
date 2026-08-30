"""حرّاس أرصدة الإجازات: الاستحقاق والاحتساب والترحيل (ق-32، ق-33)."""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import LeaveEntitlement, LeaveType
from apps.leaves.services.balances import (
    LeaveError, accrue, annual_days_for, balance_summary, carry_forward,
    check_eligibility, compute_leave_days, consume,
)
from apps.organization.services.structure import create_holiday


@pytest.fixture
def env(db):
    r = provision_account(slug="bal-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556")
        emp, _, _ = create_employment(person=p, company=comp,
                                       employee_no="E-1",
                                       join_date=date(2020, 1, 1))
        yield {
            "account_id": r.account_id, "acc": acc, "comp": comp, "emp": emp,
            "annual": LeaveType.objects.get(company=comp, code="ANNUAL"),
            "hajj": LeaveType.objects.get(company=comp, code="HAJJ"),
            "iddah": LeaveType.objects.get(company=comp, code="IDDAH"),
            "unpaid": LeaveType.objects.get(company=comp, code="UNPAID"),
        }


# ══════════ الاستحقاق (ق-33) ══════════

@pytest.mark.django_db(transaction=True)
def test_annual_rises_after_five_years(env):
    with account_scope(env["account_id"]):
        assert annual_days_for(env["emp"], env["annual"],
                               date(2021, 6, 1)) == D("21")
        assert annual_days_for(env["emp"], env["annual"],
                               date(2026, 6, 1)) == D("30")


@pytest.mark.django_db(transaction=True)
def test_individual_entitlement_overrides_default(env):
    """ق-33: الرصيد فردي بأي رقم — 45 مثلًا."""
    with account_scope(env["account_id"]):
        LeaveEntitlement.objects.create(
            account=env["acc"], company=env["comp"], employment=env["emp"],
            leave_type=env["annual"], days_per_year=D("45"),
            effective_from=date(2026, 1, 1))
        assert annual_days_for(env["emp"], env["annual"],
                               date(2026, 6, 1)) == D("45")


@pytest.mark.django_db(transaction=True)
def test_entitlement_below_statutory_rejected(env):
    """ق-34: منع صارم."""
    from django.core.exceptions import ValidationError
    with account_scope(env["account_id"]):
        with pytest.raises(ValidationError):
            LeaveEntitlement(
                account=env["acc"], company=env["comp"],
                employment=env["emp"], leave_type=env["annual"],
                days_per_year=D("15"),
                effective_from=date(2026, 1, 1)).save()


# ══════════ احتساب الأيام (ق-33) ══════════

@pytest.mark.django_db(transaction=True)
def test_holidays_extend_leave_weekends_counted(env):
    """
    ق-33: العطل تُمدّد الإجازة ولا تُخصم، والراحة الأسبوعية تُحتسب.
    """
    with account_scope(env["account_id"]):
        create_holiday(company=env["comp"], name_ar="عيد",
                       start_date=date(2026, 4, 5), end_date=date(2026, 4, 8))
        c = compute_leave_days(company=env["comp"], leave_type=env["annual"],
                               start_date=date(2026, 4, 1), requested_days=10)
        assert c.charged_days == D("10")
        assert c.extended_days == 4, "العطل لم تُمدّد"
        assert c.end_date == date(2026, 4, 14)
        assert all(x["reason"] == "عطلة" for x in c.excluded)


@pytest.mark.django_db(transaction=True)
def test_weekend_extends_when_company_chooses(env):
    """ق-32: الشركة تعدّل — الراحة تُمدّد بدل أن تُحتسب."""
    with account_scope(env["account_id"]):
        env["annual"].weekend_treatment = "extends"
        env["annual"].save()
        c = compute_leave_days(company=env["comp"], leave_type=env["annual"],
                               start_date=date(2026, 4, 1), requested_days=5)
        assert c.charged_days == D("5")
        assert c.extended_days > 0
        assert any(x["reason"] == "راحة أسبوعية" for x in c.excluded)


@pytest.mark.django_db(transaction=True)
def test_zero_days_rejected(env):
    with account_scope(env["account_id"]):
        with pytest.raises(LeaveError):
            compute_leave_days(company=env["comp"],
                               leave_type=env["annual"],
                               start_date=date(2026, 4, 1), requested_days=0)


# ══════════ الأرصدة (ق-32) ══════════

@pytest.mark.django_db(transaction=True)
def test_monthly_accrual_prorated(env):
    """الاستحقاق الشهري بالتناسب."""
    with account_scope(env["account_id"]):
        b = accrue(env["emp"], env["annual"], as_of=date(2026, 6, 30))
        assert D("14") < b.accrued < D("16")     # 30 ÷ 12 × 6 ≈ 15


@pytest.mark.django_db(transaction=True)
def test_annual_accrual_full_amount(env):
    with account_scope(env["account_id"]):
        env["annual"].accrual_method = "annual"
        env["annual"].save()
        b = accrue(env["emp"], env["annual"], as_of=date(2026, 6, 30))
        assert b.accrued == D("30")


@pytest.mark.django_db(transaction=True)
def test_consume_blocks_overdraft(env):
    with account_scope(env["account_id"]):
        accrue(env["emp"], env["annual"], as_of=date(2026, 6, 30))
        with pytest.raises(LeaveError):
            consume(env["emp"], env["annual"], D("100"), year=2026)


@pytest.mark.django_db(transaction=True)
def test_per_event_leave_has_no_balance_check(env):
    """إجازات الوقائع (حج، زواج) بلا رصيد — تُتتبع فقط."""
    with account_scope(env["account_id"]):
        b = consume(env["emp"], env["hajj"], D("10"), year=2026)
        assert b.consumed == D("10")


# ══════════ الترحيل (ق-32) ══════════

@pytest.mark.django_db(transaction=True)
def test_carry_forward_capped(env):
    """السياسة الافتراضية: ترحيل بحد 21 يومًا."""
    with account_scope(env["account_id"]):
        b = accrue(env["emp"], env["annual"], as_of=date(2026, 12, 31))
        b.accrued = D("40")
        b.save()
        res = carry_forward(env["emp"], env["annual"], 2026)
        assert res["carried"] == D("21.00")
        assert res["expired"] == D("19.00")


@pytest.mark.django_db(transaction=True)
def test_carry_forward_expire_policy(env):
    with account_scope(env["account_id"]):
        env["annual"].carry_forward_policy = "expire"
        env["annual"].save()
        b = accrue(env["emp"], env["annual"], as_of=date(2026, 12, 31))
        b.accrued = D("30")
        b.save()
        res = carry_forward(env["emp"], env["annual"], 2026)
        assert res["carried"] == D("0.00")


@pytest.mark.django_db(transaction=True)
def test_carry_forward_full_policy(env):
    with account_scope(env["account_id"]):
        env["annual"].carry_forward_policy = "full"
        env["annual"].save()
        b = accrue(env["emp"], env["annual"], as_of=date(2026, 12, 31))
        b.accrued = D("40")
        b.save()
        res = carry_forward(env["emp"], env["annual"], 2026)
        assert res["carried"] == D("40.00")


# ══════════ الأهلية ══════════

@pytest.mark.django_db(transaction=True)
def test_hajj_eligible_after_service_requirement(env):
    """خدمة 2020 تتجاوز 24 شهرًا — مؤهل."""
    with account_scope(env["account_id"]):
        assert check_eligibility(env["emp"], env["hajj"]) == []


@pytest.mark.django_db(transaction=True)
def test_hajj_blocked_for_new_employee(env):
    with account_scope(env["account_id"]):
        p2, _ = create_person(
            account=env["acc"], first_name_ar="فهد",
            family_name_ar="العتيبي", gender="male", nationality_code="SA",
            id_type="national_id", id_number="1099988877",
            mobile="0509998887")
        new_emp, _, _ = create_employment(
            person=p2, company=env["comp"], employee_no="E-2",
            join_date=date.today())
        errors = check_eligibility(new_emp, env["hajj"])
        assert errors and "شهر خدمة" in errors[0]


@pytest.mark.django_db(transaction=True)
def test_gender_restricted_leave(env):
    """العدّة للإناث — الذكر يُرفض."""
    with account_scope(env["account_id"]):
        errors = check_eligibility(env["emp"], env["iddah"])
        assert errors and "إناث" in errors[0]


@pytest.mark.django_db(transaction=True)
def test_once_per_service_enforced(env):
    with account_scope(env["account_id"]):
        consume(env["emp"], env["hajj"], D("10"), year=2026)
        errors = check_eligibility(env["emp"], env["hajj"])
        assert errors and "مرة واحدة" in errors[0]


@pytest.mark.django_db(transaction=True)
def test_balance_summary_lists_all_types(env):
    with account_scope(env["account_id"]):
        accrue(env["emp"], env["annual"], as_of=date(2026, 6, 30))
        summary = balance_summary(env["emp"], 2026)
        assert any(x["code"] == "ANNUAL" for x in summary)


# ══════════ التسويات اليدوية ══════════

@pytest.mark.django_db(transaction=True)
def test_adjustment_survives_accrual(env):
    """
    التسوية اليدوية قرار بشري لا تمحوه إعادة الاحتساب —
    نفس مبدأ التعديل اليدوي في الحضور.
    """
    from apps.leaves.services.balances import adjust_balance
    with account_scope(env["account_id"]):
        accrue(env["emp"], env["annual"], as_of=date(2026, 6, 30))
        adjust_balance(employment=env["emp"], leave_type=env["annual"],
                       days=D("5"), reason="منحة تقديرية",
                       adjusted_by_person=env["emp"].person, year=2026)
        b = accrue(env["emp"], env["annual"], as_of=date(2026, 7, 31))
        assert b.adjusted == D("5"), "التسوية مُحيت"
        assert b.available == b.accrued + b.adjusted


@pytest.mark.django_db(transaction=True)
def test_adjustment_requires_reason(env):
    from apps.leaves.services.balances import adjust_balance
    with account_scope(env["account_id"]):
        with pytest.raises(LeaveError):
            adjust_balance(employment=env["emp"], leave_type=env["annual"],
                           days=D("3"), reason="   ",
                           adjusted_by_person=env["emp"].person, year=2026)


@pytest.mark.django_db(transaction=True)
def test_adjustment_cannot_make_balance_negative(env):
    from apps.leaves.services.balances import adjust_balance
    with account_scope(env["account_id"]):
        accrue(env["emp"], env["annual"], as_of=date(2026, 6, 30))
        with pytest.raises(LeaveError):
            adjust_balance(employment=env["emp"], leave_type=env["annual"],
                           days=D("-999"), reason="خصم",
                           adjusted_by_person=env["emp"].person, year=2026)


@pytest.mark.django_db(transaction=True)
def test_negative_adjustment_allowed_within_balance(env):
    """الخصم مسموح ما دام الرصيد يحتمله — تصحيح خطأ إدخال مثلًا."""
    from apps.leaves.services.balances import adjust_balance
    with account_scope(env["account_id"]):
        accrue(env["emp"], env["annual"], as_of=date(2026, 6, 30))
        res = adjust_balance(
            employment=env["emp"], leave_type=env["annual"], days=D("-3"),
            reason="تصحيح خطأ إدخال",
            adjusted_by_person=env["emp"].person, year=2026)
        assert res["amount"] == "-3.00"


@pytest.mark.django_db(transaction=True)
def test_zero_adjustment_rejected(env):
    from apps.leaves.services.balances import adjust_balance
    with account_scope(env["account_id"]):
        with pytest.raises(LeaveError):
            adjust_balance(employment=env["emp"], leave_type=env["annual"],
                           days=D("0"), reason="لا شيء",
                           adjusted_by_person=env["emp"].person, year=2026)
