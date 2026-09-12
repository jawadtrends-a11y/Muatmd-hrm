"""
حرّاس البنود المكرّرة (ق-135).

⚠️ **بندٌ بلا نهاية يُحسم من الموظف سنين** — ومن أدخله نسيه.
فالنهاية بتاريخٍ أو بعدد مرّات، والعدّاد يُرفع عند **الاعتماد**
لا عند الحساب.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    PayComponent, PayrollRunType, RecurringAdjustment, RecurringKind)
from apps.payroll.services import engine

TODAY = date.today()


@pytest.fixture
def env(db):
    r = provision_account(slug="rec-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        other = (PayComponent.objects.filter(company=comp)
                 .exclude(code="BASIC").first())

        p, _ = create_person(
            account=acc, first_name_ar="نواف", family_name_ar="الشهري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1066677799", mobile="0506667779")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="R-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("8000"))])

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "component": other or basic}


def _rec(env, **kw):
    defaults = {
        "account_id": env["account_id"], "company": env["comp"],
        "employment": env["emp"], "component": env["component"],
        "kind": RecurringKind.DEDUCTION, "amount": Decimal("200"),
        "start_year": 2026, "start_month": 1,
    }
    defaults.update(kw)
    return RecurringAdjustment.objects.create(**defaults)


def test_applies_within_its_window(env):
    """يسري في مداه لا قبله ولا بعده."""
    with account_scope(env["account_id"]):
        r = _rec(env, start_year=2026, start_month=3,
                 end_year=2026, end_month=6)
        assert r.applies_to(2026, 2) is False
        assert r.applies_to(2026, 3) is True
        assert r.applies_to(2026, 6) is True
        assert r.applies_to(2026, 7) is False


def test_max_occurrences_stops_it(env):
    """
    ⚠️ **والسقف يوقفه**: كقسطٍ ينتهي.

    فبلا نهايةٍ يُحسم من الموظف سنين — ومن أدخله نسيه.
    """
    with account_scope(env["account_id"]):
        r = _rec(env, max_occurrences=3)
        assert r.remaining == 3
        r.applied_count = 3
        assert r.applies_to(2026, 9) is False
        assert r.remaining == 0


def test_inactive_never_applies(env):
    """والمعطَّل لا يسري."""
    with account_scope(env["account_id"]):
        r = _rec(env, is_active=False)
        assert r.applies_to(2026, 9) is False


def test_deduction_lands_in_the_payslip(env):
    """
    والحسم المكرّر **يظهر في القسيمة** — فالبند بلا أثرٍ ورقة.
    """
    with account_scope(env["account_id"]):
        _rec(env, amount=Decimal("250"), reason="قسط قرض")

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)

        slip = run.payslips.first()
        assert slip is not None
        codes = [line.component_code for line in slip.lines.all()]
        assert env["component"].code in codes, codes
        assert "recurring" in (slip.calculation_trace or {})


def test_counter_rises_on_approval_not_calculation(env):
    """
    ⚠️⚠️ الأهمّ: **العدّاد يُرفع عند الاعتماد لا عند الحساب**.

    فمسيرٌ يُحسب ثم يُلغى لا يستهلك قسطًا — وإلا نقص قسطٌ بلا صرف
    وانتهى القرض قبل سداده.
    """
    from apps.payroll.models import PayrollRunStatus

    with account_scope(env["account_id"]):
        r = _rec(env, max_occurrences=3)

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        r.refresh_from_db()
        assert r.applied_count == 0, "استُهلك قسطٌ بمجرّد الحساب"

        run.status = PayrollRunStatus.SUBMITTED
        run.save(update_fields=["status"])
        engine.approve_run(run, None)

        r.refresh_from_db()
        assert r.applied_count == 1, "اعتُمد المسير ولم يُستهلك القسط"


def test_exhausted_is_deactivated(env):
    """وما استُهلك بالكامل يُطفأ — فلا يزحم قوائم السارية."""
    from apps.payroll.models import PayrollRunStatus

    with account_scope(env["account_id"]):
        r = _rec(env, max_occurrences=1)

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        run.status = PayrollRunStatus.SUBMITTED
        run.save(update_fields=["status"])
        engine.approve_run(run, None)

        r.refresh_from_db()
        assert r.applied_count == 1
        assert r.is_active is False
