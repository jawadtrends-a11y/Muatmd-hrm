"""حرّاس مكوّنات الأجر والأعلام الأربعة."""
from decimal import Decimal as D

import pytest

from apps.accounts.models import Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.payroll.models import PayComponent, PayrollSettings
from apps.payroll.services.components import (
    DEFAULT_COMPONENTS, eosb_wage, gosi_subject_wage, overtime_base_wage,
    provision_default_components, set_component_flags,
)
from apps.payroll.services.eosb import EOSBBasisNotSet


@pytest.fixture
def company(db):
    acct = provision_account(
        slug="comp-test", display_name_ar="حساب مكوّنات",
        company_name_ar="شركة مكوّنات", is_sandbox=True,
    )
    with account_scope(acct.account_id):
        return Company.objects.get(id=acct.company_id)


@pytest.fixture
def lines(company):
    with account_scope(company.account_id):
        by = {c.code: c for c in
              PayComponent.objects.filter(company=company)}
        return by, [(by["BASIC"], D("8000")),
                    (by["HOUSING"], D("2000")),
                    (by["TRANSPORT"], D("1000"))]


@pytest.mark.django_db(transaction=True)
def test_components_provisioned_on_account_creation(company):
    with account_scope(company.account_id):
        assert PayComponent.objects.filter(company=company).count() == \
            len(DEFAULT_COMPONENTS)


@pytest.mark.django_db(transaction=True)
def test_payroll_settings_created_with_defaults(company):
    with account_scope(company.account_id):
        s = PayrollSettings.objects.get(company=company)
        assert s.payroll_days_per_month == 30      # ق-22
        assert s.working_hours_per_day == D("8.00")
        assert s.overtime_basis == "full_plus_half_basic"
        assert s.eosb_wage_basis == "not_set"      # ق-21


@pytest.mark.django_db(transaction=True)
def test_gosi_subject_is_basic_plus_housing(company, lines):
    """قرار المالك: الأجر الخاضع = الأساسي + بدل السكن."""
    _, ls = lines
    assert gosi_subject_wage(ls) == D("10000")


@pytest.mark.django_db(transaction=True)
def test_overtime_base_is_basic_only(company, lines):
    _, ls = lines
    assert overtime_base_wage(ls) == D("8000")


@pytest.mark.django_db(transaction=True)
def test_eosb_wage_follows_flags(company, lines):
    """ق-21: أجر المكافأة حسب العقد — الأعلام تقوده."""
    by, ls = lines
    assert eosb_wage(ls, "flagged") == D("8000")

    with account_scope(company.account_id):
        set_component_flags(by["HOUSING"], is_eosb_subject=True)
        set_component_flags(by["TRANSPORT"], is_eosb_subject=True)
        refreshed = {c.code: c for c in
                     PayComponent.objects.filter(company=company)}
    ls2 = [(refreshed["BASIC"], D("8000")),
           (refreshed["HOUSING"], D("2000")),
           (refreshed["TRANSPORT"], D("1000"))]
    assert eosb_wage(ls2, "flagged") == D("11000")


@pytest.mark.django_db(transaction=True)
def test_not_set_basis_blocks_calculation(company, lines):
    """ق-21: الصمت في أجر المكافأة قرار مالي لم يتخذه أحد."""
    _, ls = lines
    with pytest.raises(EOSBBasisNotSet):
        eosb_wage(ls, "not_set")


@pytest.mark.django_db(transaction=True)
def test_excluding_flag_warns_not_blocks(company, lines):
    """ق-23: تحذير عند الاستثناء، بلا منع."""
    by, _ = lines
    with account_scope(company.account_id):
        set_component_flags(by["HOUSING"], is_eosb_subject=True)
        warnings = set_component_flags(by["HOUSING"], is_eosb_subject=False)
    assert len(warnings) == 1
    assert "بدل السكن" in warnings[0]
    assert "القضاء العمالي" in warnings[0]
    by["HOUSING"].refresh_from_db()
    assert by["HOUSING"].is_eosb_subject is False, "مُنع الاستثناء"


@pytest.mark.django_db(transaction=True)
def test_enabling_flag_produces_no_warning(company, lines):
    """التفعيل لا يحذّر — التحذير عند الاستثناء فقط."""
    by, _ = lines
    with account_scope(company.account_id):
        assert set_component_flags(by["TRANSPORT"], is_eosb_subject=True) == []


@pytest.mark.django_db(transaction=True)
def test_basic_is_system_component(company):
    """الراتب الأساسي مكوّن نظامي لا يُحذف."""
    with account_scope(company.account_id):
        basic = PayComponent.objects.get(company=company, code="BASIC")
        assert basic.is_system
        assert basic.is_gosi_subject and basic.is_eosb_subject


@pytest.mark.django_db(transaction=True)
def test_deductions_excluded_from_wage_bases(company, lines):
    """الاستقطاعات لا تدخل في أي أساس احتساب."""
    by, _ = lines
    with account_scope(company.account_id):
        absence = PayComponent.objects.get(company=company, code="ABSENCE")
    ls = [(by["BASIC"], D("8000")), (absence, D("500"))]
    assert gosi_subject_wage(ls) == D("8000")
    assert overtime_base_wage(ls) == D("8000")


@pytest.mark.django_db(transaction=True)
def test_provisioning_is_idempotent(company):
    with account_scope(company.account_id):
        created = provision_default_components(company)
        assert created == [], "أُنشئت مكوّنات مكررة"
