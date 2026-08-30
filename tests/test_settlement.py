"""حرّاس مسير المستحقات — تسوية نهاية الخدمة (ق-21، ق-41، ق-42)."""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.advances import approve_advance, create_advance
from apps.employees.services.assets import assign_asset
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    PayComponent, PayrollRunType, PayrollSettings, Payslip,
)
from apps.payroll.services.eosb import EOSBBasisNotSet
from apps.payroll.services.gosi_seed import sync_gosi_rates
from apps.payroll.services.settlement import (
    SettlementError, compute_settlement, create_settlement_run,
)

IBAN = "SA6080000247608010330101"


@pytest.fixture
def env(db):
    sync_gosi_rates()
    r = provision_account(slug="set-test", display_name_ar="حساب",
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
               "emp": emp, "person": p, "settings": st, "comps": comps}


def _settle(env, reason="employer_death", end=date(2026, 6, 15), **kw):
    return compute_settlement(
        employment=env["emp"], termination_date=end, reason_code=reason,
        settings_obj=env["settings"], **kw)


# ══════════ الأساس ══════════

@pytest.mark.django_db(transaction=True)
def test_basis_must_be_set_first(env):
    """ق-21: الصمت في أجر المكافأة قرار مالي لم يتخذه أحد."""
    with account_scope(env["account_id"]):
        env["settings"].eosb_wage_basis = "not_set"
        env["settings"].save()
        with pytest.raises(EOSBBasisNotSet):
            _settle(env)


@pytest.mark.django_db(transaction=True)
def test_unknown_reason_rejected(env):
    with account_scope(env["account_id"]):
        with pytest.raises(SettlementError):
            _settle(env, reason="made_up")


# ══════════ المكافأة ══════════

@pytest.mark.django_db(transaction=True)
def test_full_entitlement_reason(env):
    with account_scope(env["account_id"]):
        r = _settle(env, reason="employer_death")
        eosb = [l for l in r.lines if l.code == "EOSB"][0]
        assert eosb.amount > 0
        assert r.trace["eosb"]["ratio"] == "1"


@pytest.mark.django_db(transaction=True)
def test_resignation_prorated(env):
    """م/85: الاستقالة نسبة حسب المدة."""
    with account_scope(env["account_id"]):
        full = _settle(env, reason="employer_death")
        resign = _settle(env, reason="resignation")
        full_eosb = [l for l in full.lines if l.code == "EOSB"][0].amount
        res_eosb = [l for l in resign.lines if l.code == "EOSB"][0].amount
        assert res_eosb < full_eosb


@pytest.mark.django_db(transaction=True)
def test_article_80_no_award(env):
    with account_scope(env["account_id"]):
        r = _settle(env, reason="article_80")
        assert not [l for l in r.lines if l.code == "EOSB"]
        assert any("لا مكافأة" in w for w in r.warnings)


@pytest.mark.django_db(transaction=True)
def test_unlawful_termination_adds_compensation(env):
    """ق-27: تعويض م/77 بند مستقل."""
    with account_scope(env["account_id"]):
        r = _settle(env, reason="unlawful_termination")
        codes = {l.code for l in r.lines}
        assert "EOSB" in codes and "COMP_77" in codes


@pytest.mark.django_db(transaction=True)
def test_agreed_compensation_wins(env):
    """ق-27: الاتفاق يسبق الحد النظامي."""
    with account_scope(env["account_id"]):
        r = _settle(env, reason="unlawful_termination",
                    agreed_compensation=D("50000"))
        comp = [l for l in r.lines if l.code == "COMP_77"][0]
        assert comp.amount == D("50000.00")


# ══════════ بدل الإجازات (ق-42) ══════════

@pytest.mark.django_db(transaction=True)
def test_leave_balance_uses_eosb_wage(env):
    """ق-42: بدل الإجازات على نفس أساس المكافأة."""
    with account_scope(env["account_id"]):
        r = _settle(env, leave_balance_days=D("20"))
        line = [l for l in r.lines if l.code == "LEAVE_BALANCE"][0]
        # أجر المكافأة = الأساسي وحده (9000) لأن السكن غير معلّم
        assert line.amount == D("6000.00")   # 20 × 300
        assert "نفس أساس المكافأة" in line.explanation


@pytest.mark.django_db(transaction=True)
def test_leave_balance_follows_flags(env):
    """تفعيل علم السكن يرفع بدل الإجازات والمكافأة معًا."""
    with account_scope(env["account_id"]):
        before = _settle(env, leave_balance_days=D("20"))
        env["comps"]["HOUSING"].is_eosb_subject = True
        env["comps"]["HOUSING"].save()
        after = _settle(env, leave_balance_days=D("20"))
        b = [l for l in before.lines if l.code == "LEAVE_BALANCE"][0]
        a = [l for l in after.lines if l.code == "LEAVE_BALANCE"][0]
        assert a.amount > b.amount


@pytest.mark.django_db(transaction=True)
def test_no_leave_line_when_zero(env):
    with account_scope(env["account_id"]):
        r = _settle(env, leave_balance_days=D("0"))
        assert not [l for l in r.lines if l.code == "LEAVE_BALANCE"]


# ══════════ راتب الشهر ══════════

@pytest.mark.django_db(transaction=True)
def test_month_salary_prorated(env):
    with account_scope(env["account_id"]):
        r = _settle(env, end=date(2026, 6, 15))
        line = [l for l in r.lines if l.code == "MONTH_SALARY"][0]
        assert line.amount == D("5625.00")   # 15 × 375


@pytest.mark.django_db(transaction=True)
def test_month_salary_can_be_excluded(env):
    """ق-21: الشركة تختار إبقاءه في المسير العام."""
    with account_scope(env["account_id"]):
        r = _settle(env, include_month_salary=False)
        assert not [l for l in r.lines if l.code == "MONTH_SALARY"]


# ══════════ الخصومات (ق-41) ══════════

@pytest.mark.django_db(transaction=True)
def test_outstanding_advance_deducted(env):
    with account_scope(env["account_id"]):
        adv = create_advance(employment=env["emp"], amount=D("6000"),
                             settings_obj=env["settings"],
                             start_year=2026, start_month=4,
                             installments_count=6)
        approve_advance(advance=adv, approved_by_person=env["person"])
        r = _settle(env)
        line = [l for l in r.lines if l.code.startswith("ADV_")][0]
        assert line.amount == D("6000.00")
        assert line.kind == "deduction"


@pytest.mark.django_db(transaction=True)
def test_unreturned_asset_deducted(env):
    """ق-41: قيمة العهدة غير المرجَعة تُخصم."""
    with account_scope(env["account_id"]):
        assign_asset(employment=env["emp"], name_ar="حاسب",
                     value=D("4500"))
        r = _settle(env)
        line = [l for l in r.lines if l.code.startswith("AST_")][0]
        assert line.amount == D("4500.00")


@pytest.mark.django_db(transaction=True)
def test_advances_disabled_skips_deduction(env):
    with account_scope(env["account_id"]):
        adv = create_advance(employment=env["emp"], amount=D("6000"),
                             settings_obj=env["settings"],
                             start_year=2026, start_month=4)
        approve_advance(advance=adv, approved_by_person=env["person"])
        env["settings"].advances_enabled = False
        env["settings"].save()
        r = _settle(env)
        assert not [l for l in r.lines if l.code.startswith("ADV_")]


# ══════════ الصافي لا ينزل عن صفر (ق-37) ══════════

@pytest.mark.django_db(transaction=True)
def test_net_never_negative(env):
    with account_scope(env["account_id"]):
        assign_asset(employment=env["emp"], name_ar="سيارة",
                     value=D("200000"), category="vehicle")
        r = _settle(env, reason="article_80", include_month_salary=False)
        assert r.net_due == D("0.00")
        assert any("تتجاوز المستحقات" in w for w in r.warnings)


# ══════════ حفظ المسير ══════════

@pytest.mark.django_db(transaction=True)
def test_settlement_run_created(env):
    with account_scope(env["account_id"]):
        run, slip, result = create_settlement_run(
            employment=env["emp"], termination_date=date(2026, 6, 15),
            reason_code="employer_death", settings_obj=env["settings"])
        assert run.run_type == PayrollRunType.SETTLEMENT
        assert run.employee_count == 1
        assert slip.net_pay == result.net_due
        assert slip.lines.count() == len(result.lines)


@pytest.mark.django_db(transaction=True)
def test_settlement_excluded_from_wps(env):
    """مسير المستحقات لا يدخل حماية الأجور تلقائيًا."""
    with account_scope(env["account_id"]):
        _, slip, _ = create_settlement_run(
            employment=env["emp"], termination_date=date(2026, 6, 15),
            reason_code="employer_death", settings_obj=env["settings"])
        assert slip.include_in_wps is False


@pytest.mark.django_db(transaction=True)
def test_duplicate_settlement_blocked(env):
    with account_scope(env["account_id"]):
        create_settlement_run(
            employment=env["emp"], termination_date=date(2026, 6, 15),
            reason_code="employer_death", settings_obj=env["settings"])
        with pytest.raises(SettlementError):
            create_settlement_run(
                employment=env["emp"], termination_date=date(2026, 6, 15),
                reason_code="employer_death", settings_obj=env["settings"])


@pytest.mark.django_db(transaction=True)
def test_every_line_explains_itself(env):
    with account_scope(env["account_id"]):
        assign_asset(employment=env["emp"], name_ar="حاسب", value=D("4500"))
        r = _settle(env, leave_balance_days=D("10"))
        for line in r.lines:
            assert line.explanation, f"بند بلا شرح: {line.name_ar}"


@pytest.mark.django_db(transaction=True)
def test_warns_near_higher_bracket(env):
    """
    عشرة أيام قد تضاعف الاستحقاق عند حدود م/85 — التنبيه يحمي
    الشركة من نزاع والموظف من ظلم توقيت.
    """
    with account_scope(env["account_id"]):
        # الخدمة من 2019-01-01 — قبل خمس سنوات بأيام
        near = compute_settlement(
            employment=env["emp"], termination_date=date(2023, 12, 20),
            reason_code="resignation", settings_obj=env["settings"])
        assert any("بُعد" in w for w in near.warnings)


@pytest.mark.django_db(transaction=True)
def test_no_warning_when_far_from_bracket(env):
    with account_scope(env["account_id"]):
        far = compute_settlement(
            employment=env["emp"], termination_date=date(2026, 8, 1),
            reason_code="resignation", settings_obj=env["settings"])
        assert not any("بُعد" in w for w in far.warnings)


@pytest.mark.django_db(transaction=True)
def test_no_bracket_warning_for_full_entitlement(env):
    """التنبيه للاستقالة وحدها — الحالات الكاملة لا تتأثر بالشرائح."""
    with account_scope(env["account_id"]):
        r = compute_settlement(
            employment=env["emp"], termination_date=date(2023, 12, 20),
            reason_code="employer_death", settings_obj=env["settings"])
        assert not any("بُعد" in w for w in r.warnings)
