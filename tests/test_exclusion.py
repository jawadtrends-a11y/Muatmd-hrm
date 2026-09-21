"""
حرّاس الاستبعاد اليدوي من المسير (ق-228).

⚠️⚠️ **الاستبعاد قرارٌ ماليّ**: موظفٌ لا يصله راتبه. فالسبب إلزاميّ،
والفاعل يُنسب، والإعادة لا تحذف — **والمسير المعتمد لا يُمسّ**.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    PayComponent, PayrollRun, PayrollRunStatus, PayrollRunType)
from apps.payroll.models_exclusion import ExclusionScope, PayrollExclusion
from apps.payroll.services import engine
from apps.payroll.services import exclusion as svc


@pytest.fixture
def env(db):
    r = provision_account(slug="excl-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        emps = []
        for i, (fn, idn, mob) in enumerate([
                ("سالم", "1081112221", "0508112221"),
                ("ماهر", "1082223332", "0508223332")]):
            p, _ = create_person(
                account=acc, first_name_ar=fn, family_name_ar="العنزي",
                gender="male", nationality_code="SA", id_type="national_id",
                id_number=idn, mobile=mob)
            emp, _, _ = create_employment(
                person=p, company=comp, employee_no=f"X-{i + 1}",
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("5000"))])
            emps.append(emp)

        run = engine.create_run(company=comp, run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)

        yield {"account_id": r.account_id, "comp": comp,
               "a": emps[0], "b": emps[1], "run": run}


def _count(run):
    run.refresh_from_db()
    return run.payslips.count(), run.employee_count, run.total_net


def test_exclusion_removes_slip_and_updates_totals(env):
    """
    ⚠️⚠️ الأهمّ: **الاستبعاد يُحدّث إجماليّ المسير** — فالمسير يحفظ
    عدده وصافيه، **واستبعادٌ بلا احتسابٍ يترك الملخّص يكذب**.
    """
    with account_scope(env["account_id"]):
        slips, n, net = _count(env["run"])
        assert (slips, n) == (2, 2)

        svc.exclude(run=env["run"], employment=env["a"],
                    scope=ExclusionScope.RUN, reason="تحقيق إداري")

        slips2, n2, net2 = _count(env["run"])
        assert (slips2, n2) == (1, 1)
        assert net2 < net
        assert not env["run"].payslips.filter(employment=env["a"]).exists()


def test_reason_is_required(env):
    """والاستبعاد بلا سببٍ لا يُقبل — فمن سأل «لماذا؟» يجد الجواب."""
    with account_scope(env["account_id"]):
        for bad in ("", "   ", None):
            with pytest.raises(svc.ExclusionError) as e:
                svc.exclude(run=env["run"], employment=env["a"],
                            scope=ExclusionScope.RUN, reason=bad)
            assert "سبب" in str(e.value)
        assert PayrollExclusion.objects.count() == 0


def test_run_scope_does_not_carry_to_next_run(env):
    """«هذا المسير فقط» يعود تلقائيًّا في الشهر التالي."""
    with account_scope(env["account_id"]):
        svc.exclude(run=env["run"], employment=env["a"],
                    scope=ExclusionScope.RUN, reason="إجازة بلا راتب")
        nxt = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=10)
        engine.calculate_run(nxt)
        assert nxt.payslips.filter(employment=env["a"]).exists()


def test_until_revoked_carries_to_next_run(env):
    """و«حتى يُعاد» يبقى خارج المسيرات التالية."""
    with account_scope(env["account_id"]):
        svc.exclude(run=env["run"], employment=env["a"],
                    scope=ExclusionScope.UNTIL_REVOKED, reason="خلاف مالي")
        nxt = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=10)
        engine.calculate_run(nxt)
        assert not nxt.payslips.filter(employment=env["a"]).exists()
        assert nxt.payslips.filter(employment=env["b"]).exists()


def test_revoke_restores_and_keeps_record(env):
    """⚠️ **والإعادة لا تحذف** — تُسجَّل بتاريخها (ق-44)."""
    with account_scope(env["account_id"]):
        ex = svc.exclude(run=env["run"], employment=env["a"],
                         scope=ExclusionScope.RUN, reason="خطأ")
        svc.revoke(exclusion=ex, run=env["run"])

        assert _count(env["run"])[:2] == (2, 2)
        ex.refresh_from_db()
        assert ex.revoked_at is not None
        assert PayrollExclusion.objects.filter(id=ex.id).exists()


def test_approved_run_cannot_be_touched(env):
    """⚠️⚠️ **والمسير المعتمد سجلٌّ ماليّ نهائيّ** — لا يُستبعد منه أحد."""
    with account_scope(env["account_id"]):
        PayrollRun.objects.filter(id=env["run"].id).update(
            status=PayrollRunStatus.APPROVED)
        env["run"].refresh_from_db()
        with pytest.raises(svc.ExclusionError):
            svc.exclude(run=env["run"], employment=env["a"],
                        scope=ExclusionScope.RUN, reason="متأخر")
        assert env["run"].payslips.count() == 2


def test_double_exclusion_is_refused(env):
    with account_scope(env["account_id"]):
        svc.exclude(run=env["run"], employment=env["a"],
                    scope=ExclusionScope.RUN, reason="أول")
        with pytest.raises(svc.ExclusionError) as e:
            svc.exclude(run=env["run"], employment=env["a"],
                        scope=ExclusionScope.RUN, reason="ثانٍ")
        assert "أصلًا" in str(e.value)
