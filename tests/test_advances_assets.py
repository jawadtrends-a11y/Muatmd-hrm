"""حرّاس السلف والعهد والوثائق (ق-41)."""
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models_assets import (
    Advance, AdvanceStatus, Asset, AssetStatus, DocumentType,
    EmployeeDocument, RepaymentMethod,
)
from apps.employees.services.advances import (
    AdvanceError, AdvancesDisabled, approve_advance, check_eligibility,
    create_advance, due_installment, record_deduction, settle_on_termination,
    total_outstanding,
)
from apps.employees.services.assets import (
    AssetError, add_document, assets_settlement, assign_asset,
    deduct_unreturned, expiring_documents, outstanding_assets, return_asset,
)
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent, PayrollSettings

IBAN = "SA6080000247608010330101"


@pytest.fixture
def env(db):
    r = provision_account(slug="adv-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}
        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1099887766", mobile="0509887766", force=True)
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="201",
            join_date=date(2021, 1, 1), iban=IBAN,
            salary_lines=[(comps["BASIC"], D("8000")),
                          (comps["HOUSING"], D("2000"))])
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp, "person": p,
               "settings": PayrollSettings.objects.get(company=comp)}


def _advance(env, amount="6000", n=6, method=RepaymentMethod.EQUAL_INSTALLMENTS):
    return create_advance(
        employment=env["emp"], amount=amount, settings_obj=env["settings"],
        start_year=2026, start_month=3, repayment_method=method,
        installments_count=n)


# ══════════ تمكين النظام ══════════

@pytest.mark.django_db(transaction=True)
def test_advances_can_be_disabled_entirely(env):
    """ق-41: شركة لا تتعامل بالسلف تُطفئ النظام."""
    with account_scope(env["account_id"]):
        env["settings"].advances_enabled = False
        env["settings"].save()
        with pytest.raises(AdvancesDisabled):
            _advance(env)


# ══════════ الحدود ══════════

@pytest.mark.django_db(transaction=True)
def test_max_amount_enforced(env):
    with account_scope(env["account_id"]):
        env["settings"].advance_max_amount = D("5000")
        env["settings"].save()
        check = check_eligibility(employment=env["emp"], amount=D("6000"),
                                  settings_obj=env["settings"])
        assert not check.allowed
        assert "يتجاوز الحد" in check.reasons[0]


@pytest.mark.django_db(transaction=True)
def test_max_months_of_salary(env):
    """الحد بعدد الرواتب — راتبان = 20,000."""
    with account_scope(env["account_id"]):
        env["settings"].advance_max_months_of_salary = D("2")
        env["settings"].save()
        ok = check_eligibility(employment=env["emp"], amount=D("19000"),
                               settings_obj=env["settings"])
        assert ok.allowed
        bad = check_eligibility(employment=env["emp"], amount=D("25000"),
                                settings_obj=env["settings"])
        assert not bad.allowed


@pytest.mark.django_db(transaction=True)
def test_second_advance_blocked_while_outstanding(env):
    """ق-41: لا سلفة ثانية قبل سداد الأولى."""
    with account_scope(env["account_id"]):
        adv = _advance(env)
        approve_advance(advance=adv, approved_by_person=env["person"])
        check = check_eligibility(employment=env["emp"], amount=D("1000"),
                                  settings_obj=env["settings"])
        assert not check.allowed
        assert "سلفة قائمة" in check.reasons[0]


@pytest.mark.django_db(transaction=True)
def test_second_advance_allowed_when_setting_off(env):
    with account_scope(env["account_id"]):
        env["settings"].advance_block_if_outstanding = False
        env["settings"].save()
        adv = _advance(env)
        approve_advance(advance=adv, approved_by_person=env["person"])
        assert check_eligibility(employment=env["emp"], amount=D("1000"),
                                 settings_obj=env["settings"]).allowed


@pytest.mark.django_db(transaction=True)
def test_installments_limit(env):
    with account_scope(env["account_id"]):
        env["settings"].advance_max_installments = 6
        env["settings"].save()
        with pytest.raises(AdvanceError):
            _advance(env, n=24)


# ══════════ طرق السداد ══════════

@pytest.mark.django_db(transaction=True)
def test_equal_installments(env):
    with account_scope(env["account_id"]):
        adv = _advance(env, amount="6000", n=6)
        assert adv.installment_amount == D("1000.00")
        assert due_installment(adv, 2026, 3) == D("0")  # لم تُعتمد بعد
        approve_advance(advance=adv, approved_by_person=env["person"])
        assert due_installment(adv, 2026, 3) == D("1000.00")


@pytest.mark.django_db(transaction=True)
def test_lump_sum_deducts_once(env):
    with account_scope(env["account_id"]):
        adv = _advance(env, amount="3000",
                       method=RepaymentMethod.LUMP_SUM)
        approve_advance(advance=adv, approved_by_person=env["person"])
        assert due_installment(adv, 2026, 3) == D("3000")
        assert due_installment(adv, 2026, 4) == D("0")


@pytest.mark.django_db(transaction=True)
def test_no_deduction_before_start_month(env):
    with account_scope(env["account_id"]):
        adv = _advance(env)
        approve_advance(advance=adv, approved_by_person=env["person"])
        assert due_installment(adv, 2026, 2) == D("0")


# ══════════ السداد ══════════

@pytest.mark.django_db(transaction=True)
def test_repayment_reduces_outstanding(env):
    with account_scope(env["account_id"]):
        adv = _advance(env, amount="6000", n=6)
        approve_advance(advance=adv, approved_by_person=env["person"])
        record_deduction(advance=adv, year=2026, month=3, amount=D("1000"))
        adv.refresh_from_db()
        assert adv.repaid_amount == D("1000.00")
        assert adv.outstanding == D("5000.00")


@pytest.mark.django_db(transaction=True)
def test_full_repayment_settles(env):
    with account_scope(env["account_id"]):
        adv = _advance(env, amount="2000", n=2)
        approve_advance(advance=adv, approved_by_person=env["person"])
        record_deduction(advance=adv, year=2026, month=3, amount=D("1000"))
        record_deduction(advance=adv, year=2026, month=4, amount=D("1000"))
        adv.refresh_from_db()
        assert adv.status == AdvanceStatus.SETTLED
        assert adv.outstanding == D("0.00")


@pytest.mark.django_db(transaction=True)
def test_last_installment_capped_at_outstanding(env):
    """القسط الأخير لا يتجاوز المتبقي."""
    with account_scope(env["account_id"]):
        adv = _advance(env, amount="1000", n=3)   # 333.33 × 3
        approve_advance(advance=adv, approved_by_person=env["person"])
        for m in (3, 4, 5):
            due = due_installment(adv, 2026, m)
            record_deduction(advance=adv, year=2026, month=m, amount=due)
            adv.refresh_from_db()
        assert adv.repaid_amount == D("1000.00")


@pytest.mark.django_db(transaction=True)
def test_settlement_on_termination(env):
    with account_scope(env["account_id"]):
        adv = _advance(env, amount="6000", n=6)
        approve_advance(advance=adv, approved_by_person=env["person"])
        record_deduction(advance=adv, year=2026, month=3, amount=D("1000"))
        res = settle_on_termination(employment=env["emp"])
        assert res["count"] == 1
        assert res["total_outstanding"] == "5000.00"


# ══════════ العهد ══════════

@pytest.mark.django_db(transaction=True)
def test_assign_and_return_asset(env):
    with account_scope(env["account_id"]):
        a = assign_asset(employment=env["emp"], name_ar="حاسب محمول",
                         value=D("4500"), category="device",
                         serial_number="SN-1")
        assert a.status == AssetStatus.ASSIGNED
        assert a.is_outstanding
        return_asset(asset=a)
        a.refresh_from_db()
        assert a.status == AssetStatus.RETURNED
        assert not a.is_outstanding


@pytest.mark.django_db(transaction=True)
def test_unreturned_assets_in_settlement(env):
    """ق-41: قيمة ما لم يُرجَع تُخصم من المخالصة."""
    with account_scope(env["account_id"]):
        assign_asset(employment=env["emp"], name_ar="حاسب",
                     value=D("4500"))
        assign_asset(employment=env["emp"], name_ar="هاتف",
                     value=D("1500"), category="phone")
        res = assets_settlement(env["emp"])
        assert res["count"] == 2
        assert res["total_value"] == "6000.00"


@pytest.mark.django_db(transaction=True)
def test_lost_asset_stays_outstanding(env):
    with account_scope(env["account_id"]):
        a = assign_asset(employment=env["emp"], name_ar="هاتف",
                         value=D("1500"))
        return_asset(asset=a, status=AssetStatus.LOST,
                     condition_note="فُقد")
        a.refresh_from_db()
        assert a.is_outstanding
        assert assets_settlement(env["emp"])["count"] == 1


@pytest.mark.django_db(transaction=True)
def test_deduct_unreturned_marks_assets(env):
    with account_scope(env["account_id"]):
        assign_asset(employment=env["emp"], name_ar="حاسب", value=D("4500"))
        count = deduct_unreturned(employment=env["emp"],
                                  note="خُصمت في المخالصة")
        assert count == 1
        assert outstanding_assets(env["emp"]).count() == 0


@pytest.mark.django_db(transaction=True)
def test_negative_asset_value_rejected(env):
    with account_scope(env["account_id"]):
        with pytest.raises(AssetError):
            assign_asset(employment=env["emp"], name_ar="شيء",
                         value=D("-100"))


# ══════════ الوثائق ══════════

@pytest.mark.django_db(transaction=True)
def test_expiring_documents_severity(env):
    """التنبيه الاستباقي — انتهاء الإقامة يوقف الموظف."""
    with account_scope(env["account_id"]):
        today = date.today()
        add_document(employment=env["emp"],
                     document_type=DocumentType.IQAMA,
                     document_number="2154967927",
                     expiry_date=today + timedelta(days=10))
        add_document(employment=env["emp"],
                     document_type=DocumentType.PASSPORT,
                     document_number="P123",
                     expiry_date=today - timedelta(days=5))
        rows = expiring_documents(env["comp"], within_days=60)
        assert len(rows) == 2
        by_type = {r["document_type"]: r for r in rows}
        assert by_type["جواز سفر"]["is_expired"] is True
        assert by_type["جواز سفر"]["severity"] == "منتهية"
        assert by_type["إقامة"]["severity"] == "حرجة"


@pytest.mark.django_db(transaction=True)
def test_far_expiry_not_listed(env):
    with account_scope(env["account_id"]):
        add_document(employment=env["emp"],
                     document_type=DocumentType.CONTRACT,
                     expiry_date=date.today() + timedelta(days=300))
        assert expiring_documents(env["comp"], within_days=60) == []


@pytest.mark.django_db(transaction=True)
def test_expiry_before_issue_rejected(env):
    with account_scope(env["account_id"]):
        with pytest.raises(AssetError):
            add_document(employment=env["emp"],
                         document_type=DocumentType.IQAMA,
                         issue_date=date(2026, 5, 1),
                         expiry_date=date(2026, 1, 1))


# ══════════ العزل ══════════

@pytest.mark.django_db(transaction=True)
def test_isolated_between_accounts(env, rls_enforced_late):
    other = provision_account(slug="adv-other", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(env["account_id"]):
        _advance(env)
        assign_asset(employment=env["emp"], name_ar="حاسب", value=D("100"))
        add_document(employment=env["emp"],
                     document_type=DocumentType.IQAMA,
                     expiry_date=date.today() + timedelta(days=30))
    rls_enforced_late()
    with account_scope(other.account_id):
        assert Advance.objects.count() == 0
        assert Asset.objects.count() == 0
        assert EmployeeDocument.objects.count() == 0
