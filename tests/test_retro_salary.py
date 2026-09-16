"""
حرّاس الأثر الرجعيّ لتغيير الراتب (ق-212).

⚠️⚠️ **فمن رفع راتبًا من يناير في مارس — والمسيران مغلقان —
الفرقُ كان يضيع صامتًا**.

**قرار جواد:** «يأخذ نفس الأثر الرجعي للطلبات الأخرى».
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import (
    create_employment, create_person, set_salary_structure)
from apps.payroll.models import PayrollRun, PayrollRunStatus
from apps.payroll.models_retro import RetroAdjustment, RetroSource
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="retro-s", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="سالم", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1081001100", mobile="0508100110")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="RS-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("8000"))])

        yield {"account_id": r.account_id, "comp": comp,
               "emp": emp, "basic": basic}


def _close(env, year, month):
    """مسيرٌ معتمدٌ لشهرٍ — فالتسوية لا تقع إلا على مغلق."""
    return PayrollRun.objects.create(
        account_id=env["emp"].account_id,
        company=env["comp"], run_no=f"PR-{year}-{month:02d}",
        period_year=year, period_month=month,
        accrual_date=date(year, month, 28),
        status=PayrollRunStatus.APPROVED)


def _raise_to(env, amount, effective_from):
    return set_salary_structure(
        employment=env["emp"],
        lines=[(env["basic"], Decimal(amount))],
        effective_from=effective_from, reason="annual_raise")


def test_closed_months_get_adjustments(env):
    """
    ⚠️⚠️ الأهمّ: **وكلُّ شهرٍ مغلقٍ بين السريان واليوم يُسجَّل**.
    """
    today = date.today()
    y = today.year
    with account_scope(env["account_id"]):
        # شهران مغلقان قبل هذا الشهر
        m1 = today.month - 2 if today.month > 2 else 1
        m2 = today.month - 1 if today.month > 1 else 2
        _close(env, y, m1)
        _close(env, y, m2)

        _raise_to(env, "10000", date(y, m1, 1))

        adj = RetroAdjustment.objects.filter(
            employment=env["emp"], source=RetroSource.SALARY)
        assert adj.count() >= 2, list(adj.values_list(
            "period_month", "amount"))


def test_amounts_keep_before_and_after(env):
    """
    ⚠️ **والقيمتان تُحفظان** — قبل وبعد لا الفرق وحده (ق-80).
    """
    today = date.today()
    m = today.month - 1 if today.month > 1 else 1
    with account_scope(env["account_id"]):
        _close(env, today.year, m)
        _raise_to(env, "10000", date(today.year, m, 1))

        a = RetroAdjustment.objects.filter(
            employment=env["emp"], source=RetroSource.SALARY).first()
        assert a is not None
        assert a.amount_before == Decimal("8000")
        assert a.amount_after == Decimal("10000")
        assert a.amount == Decimal("2000")


def test_open_month_is_skipped(env):
    """
    ⚠️ **ولا تسويةَ لشهرٍ مفتوح**: **فالمسير القادم يحتسبه بنفسه**
    — وتسجيلُها ازدواجٌ في الدفع.
    """
    today = date.today()
    with account_scope(env["account_id"]):
        # لا مسيرَ معتمدًا أصلًا
        _raise_to(env, "10000", date(today.year, today.month, 1))
        assert not RetroAdjustment.objects.filter(
            employment=env["emp"], source=RetroSource.SALARY).exists()


def test_no_diff_no_adjustment(env):
    """**وراتبٌ لم يتغيّر لا يُسجَّل**."""
    today = date.today()
    m = today.month - 1 if today.month > 1 else 1
    with account_scope(env["account_id"]):
        _close(env, today.year, m)
        _raise_to(env, "8000", date(today.year, m, 1))
        assert not RetroAdjustment.objects.filter(
            employment=env["emp"], source=RetroSource.SALARY).exists()


def test_decrease_records_negative(env):
    """
    ⚠️ **والنقصان يُسجَّل كذلك**: فتصحيحُ خطأٍ **يسترجع**، ولا
    نُسجّل الزيادة وحدها.
    """
    today = date.today()
    m = today.month - 1 if today.month > 1 else 1
    with account_scope(env["account_id"]):
        _close(env, today.year, m)
        _raise_to(env, "6000", date(today.year, m, 1))

        a = RetroAdjustment.objects.filter(
            employment=env["emp"], source=RetroSource.SALARY).first()
        assert a is not None
        assert a.amount == Decimal("-2000"), a.amount
