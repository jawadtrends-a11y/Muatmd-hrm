"""
حرّاس تأجيل بنود القسيمة (ق-136).

⚠️ **الراتب لا يُؤجَّل**: تأجيله مخالفةٌ نظامية (المادة ٩٠) —
وإنما يُؤجَّل بندٌ منه: قسط سلفة لظرفٍ طارئ أو حسمٌ بقرار.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    ComponentType, DeferralStatus, PayComponent, PayrollRunStatus, PayrollRunType,
    PayslipDeferral, RecurringAdjustment, RecurringKind)
from apps.payroll.services import deferral as svc
from apps.payroll.services import engine


@pytest.fixture
def env(db):
    r = provision_account(slug="def-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        # ⚠️ المكوّنات المبذورة كلّها ممنوعة التأجيل (راتب وبدلات
        # وحسم غياب) — فالتأجيل يقع على بندٍ تضيفه الشركة.
        other = PayComponent.objects.create(
            account=acc, company=comp, code="LOAN",
            name_ar="قسط قرض شخصيّ",
            component_type=ComponentType.DEDUCTION,
            is_active=True)

        p, _ = create_person(
            account=acc, first_name_ar="بندر", family_name_ar="الدوسري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077788811", mobile="0507778881")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="D-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])

        # بندٌ مكرّر يصير قابلًا للتأجيل
        RecurringAdjustment.objects.create(
            account=acc, company=comp, employment=emp, component=other,
            kind=RecurringKind.DEDUCTION, amount=Decimal("300"),
            start_year=2026, start_month=1, max_occurrences=12,
            reason="قسط قرض")

        run = engine.create_run(company=comp,
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "run": run, "slip": run.payslips.first(),
               "component": other}


def test_salary_can_never_be_deferred(env):
    """
    ⚠️⚠️ الأهمّ: **الراتب وبدلاته لا تُؤجَّل**.

    فالأجر مستحقٌّ في موعده (المادة ٩٠) — وتأجيله مخالفة.
    """
    with account_scope(env["account_id"]):
        for code in ("BASIC", "HOUSING", "GOSI_EMPLOYEE"):
            with pytest.raises(svc.DeferralError) as e:
                svc.defer(payslip=env["slip"], component_code=code,
                          to_year=2026, to_month=10, reason="ظرف")
            assert "لا تُؤجَّل" in str(e.value)


def test_deferrable_lines_exclude_salary(env):
    """والقائمة المعروضة للتأجيل لا تحوي الراتب — فعرضُه إغراءٌ
    بمخالفة."""
    with account_scope(env["account_id"]):
        codes = [l.component_code
                 for l in svc.deferrable_lines(env["slip"])]
        assert "BASIC" not in codes
        assert not any(c.startswith("GOSI") for c in codes)


def test_deferral_moves_the_line(env):
    """
    والبند المؤجَّل **يُنزع من شهره ويُدرج في وجهته**.
    """
    with account_scope(env["account_id"]):
        code = env["component"].code
        svc.defer(payslip=env["slip"], component_code=code,
                  to_year=2026, to_month=11, reason="ظرف طارئ")

        # نُعيد حساب الشهر نفسه — فيُنزع
        engine.calculate_run(env["run"])
        slip = env["run"].payslips.first()
        assert code not in [l.component_code for l in slip.lines.all()]
        assert "deferred_out" in (slip.calculation_trace or {})

        # وشهر الوجهة يحويه
        nxt = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=11)
        engine.calculate_run(nxt)
        nslip = nxt.payslips.first()
        assert "deferred_in" in (nslip.calculation_trace or {})


def test_past_month_is_refused(env):
    """ولا يُؤجَّل إلى شهرٍ مضى — فالتأجيل تأخيرٌ لا رجوع."""
    with account_scope(env["account_id"]):
        with pytest.raises(svc.DeferralError):
            svc.defer(payslip=env["slip"],
                      component_code=env["component"].code,
                      to_year=2026, to_month=8, reason="ظرف")


def test_approved_run_cannot_be_deferred(env):
    """
    ⚠️ **والمسير المعتمد لا يُمسّ**: سجلٌّ ماليّ نهائيّ يُصرف عليه
    ويُرحَّل للمحاسبة (قرار جواد).
    """
    with account_scope(env["account_id"]):
        env["run"].status = PayrollRunStatus.APPROVED
        env["run"].save(update_fields=["status"])
        env["slip"].refresh_from_db()

        with pytest.raises(svc.DeferralError) as e:
            svc.defer(payslip=env["slip"],
                      component_code=env["component"].code,
                      to_year=2026, to_month=11, reason="ظرف")
        assert "معتمد" in str(e.value)


def test_double_deferral_is_refused(env):
    """ولا يُؤجَّل البند مرّتين من نفس القسيمة."""
    with account_scope(env["account_id"]):
        code = env["component"].code
        svc.defer(payslip=env["slip"], component_code=code,
                  to_year=2026, to_month=11, reason="ظرف")
        with pytest.raises(svc.DeferralError):
            svc.defer(payslip=env["slip"], component_code=code,
                      to_year=2026, to_month=12, reason="ثانية")


def test_cancel_restores_the_line(env):
    """وإلغاء التأجيل يُعيد البند لشهره."""
    with account_scope(env["account_id"]):
        code = env["component"].code
        d = svc.defer(payslip=env["slip"], component_code=code,
                      to_year=2026, to_month=11, reason="ظرف")
        svc.cancel(deferral=d)
        d.refresh_from_db()
        assert d.status == DeferralStatus.CANCELLED

        engine.calculate_run(env["run"])
        slip = env["run"].payslips.first()
        assert code in [l.component_code for l in slip.lines.all()]
