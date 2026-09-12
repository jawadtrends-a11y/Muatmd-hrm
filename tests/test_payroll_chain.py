"""
حرّاس سلسلة موافقات المسير (ق-140).

**المسير مالٌ يُصرف** — وشركاتٌ تشترط مرورَه بالمالية ثم المدير
العام.

⚠️ **وبلا سلسلة يُعتمد مباشرةً** — فلا نكسر من لا يحتاجها.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    PayComponent, PayrollApproval, PayrollApprovalDecision,
    PayrollApprovalStep, PayrollRunStatus, PayrollRunType)
from apps.payroll.services import engine
from apps.payroll.services import run_approval as chain
from apps.payroll.services.engine import PayrollError


@pytest.fixture
def env(db):
    r = provision_account(slug="pc-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        def hire(first, nid, mob, no, code):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar="النجار",
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("8000"))])
            u = User.objects.create_user(username=f"pc.{no}",
                                         password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, employment=e,
                role=Role.objects.get(account=acc, code=code),
                company=comp, scope=Scope.COMPANY.value)
            return u, e

        hr, _ = hire("عادل", "1011122266", "0501112226", "P-1",
                     "hr_manager")
        ceo, _ = hire("سلطان", "1022233377", "0502223337", "P-2", "ceo")

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "hr": hr, "ceo": ceo,
               "hr_role": Role.objects.get(account=acc, code="hr_manager"),
               "ceo_role": Role.objects.get(account=acc, code="ceo")}


def _run(env, month=9):
    run = engine.create_run(company=env["comp"],
                            run_type=PayrollRunType.REGULAR,
                            year=2026, month=month)
    engine.calculate_run(run)
    return run


def _chain(env):
    for i, role in ((1, env["hr_role"]), (2, env["ceo_role"])):
        PayrollApprovalStep.objects.create(
            account=env["acc"], company=env["comp"],
            step_order=i, role=role,
            title=f"الخطوة {i}")


def test_without_a_chain_approval_works(env):
    """
    ⚠️ **بلا سلسلة يُعتمد مباشرةً** — فلا نكسر من لا يحتاجها.
    """
    with account_scope(env["account_id"]):
        run = _run(env)
        engine.submit_run(run)
        engine.approve_run(run, None)
        run.refresh_from_db()
        assert run.status == PayrollRunStatus.APPROVED


def test_chain_blocks_approval_until_complete(env):
    """
    ⚠️⚠️ الأهمّ: **لا يُعتمد قبل اكتمال سلسلته**.

    فالسلسلة تُبنى ليُمرّ بها لا ليُتخطّى — وتخطّيها يجعلها زينةً
    لا ضابطًا.
    """
    with account_scope(env["account_id"]):
        _chain(env)
        run = _run(env)
        engine.submit_run(run)

        assert PayrollApproval.objects.filter(run=run).count() == 2
        with pytest.raises(PayrollError) as e:
            engine.approve_run(run, None)
        assert "بانتظار اعتماد" in str(e.value)


def test_steps_are_decided_in_order(env):
    """والخطوات بترتيبها — لا تُقفز."""
    with account_scope(env["account_id"]):
        _chain(env)
        run = _run(env)
        engine.submit_run(run)

        assert chain.current_step(run).step_order == 1
        chain.decide(run=run, user=env["hr"], approve=True)
        assert chain.current_step(run).step_order == 2
        out = chain.decide(run=run, user=env["ceo"], approve=True)
        assert out.get("completed") is True
        assert chain.current_step(run) is None

        engine.approve_run(run, None)
        run.refresh_from_db()
        assert run.status == PayrollRunStatus.APPROVED


def test_only_the_role_can_decide(env):
    """
    ⚠️ **والقرار بالدور**: من لا يحمل دور الخطوة لا يقرّرها.
    """
    with account_scope(env["account_id"]):
        _chain(env)
        run = _run(env)
        engine.submit_run(run)

        with pytest.raises(chain.ChainError) as e:
            chain.decide(run=run, user=env["ceo"], approve=True)
        assert "وليس لك" in str(e.value)


def test_rejection_returns_it_for_correction(env):
    """
    ⚠️ **والرفض يُعيده للتصحيح لا يُلغيه**.

    فالعمل المحتسَب لا يُهدر، والسبب مكتوبٌ ليُعالَج.
    """
    with account_scope(env["account_id"]):
        _chain(env)
        run = _run(env)
        engine.submit_run(run)

        out = chain.decide(run=run, user=env["hr"], approve=False,
                           note="فرق في بدل السكن")
        assert out["rejected"] is True

        run.refresh_from_db()
        assert run.status == PayrollRunStatus.CALCULATED
        assert run.submitted_at is None

        step = PayrollApproval.objects.get(run=run, step_order=1)
        assert step.decision == PayrollApprovalDecision.REJECTED
        assert step.note == "فرق في بدل السكن"


def test_resubmit_restarts_the_chain(env):
    """
    ⚠️ **وإعادة الرفع تُعيد السلسلة من أوّلها**.

    فمن اعتمد نسخةً لا يُعدّ معتمدًا لأخرى صُحّحت بعده.
    """
    with account_scope(env["account_id"]):
        _chain(env)
        run = _run(env)
        engine.submit_run(run)
        chain.decide(run=run, user=env["hr"], approve=True)
        assert chain.current_step(run).step_order == 2

        # رفضٌ من الثانية ثم إعادة رفع
        chain.decide(run=run, user=env["ceo"], approve=False, note="مراجعة")
        engine.submit_run(run)

        assert chain.current_step(run).step_order == 1, (
            "لم تُعد السلسلة من أوّلها")
        assert PayrollApproval.objects.filter(
            run=run, decision=PayrollApprovalDecision.APPROVED
        ).count() == 0


def test_chain_state_is_readable(env):
    """وحالة السلسلة تُقرأ — فمن ينتظر يعرف عند من وقف."""
    with account_scope(env["account_id"]):
        _chain(env)
        run = _run(env)
        engine.submit_run(run)
        st = chain.chain_state(run)
        assert st["has_chain"] is True
        assert st["current_step"] == 1
        assert len(st["steps"]) == 2
