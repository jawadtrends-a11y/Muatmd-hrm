"""
حرّاس إيقاف خصم السلفة (ق-141).

**فجوةٌ كشفها جواد:** السلفة تُخصم آليًّا دائمًا ولا سبيل
لإيقافه — وموظفٌ في ظرفٍ طارئ، أو سلفةٌ تُسدَّد بحوالةٍ خارج
الراتب، أو نزاعٌ قائم.

⚠️⚠️ **والإيقاف تأخيرٌ لا إعفاء**: الرصيد يبقى دَينًا، ويُخصم
كاملًا في مخالصة نهاية الخدمة.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models import Advance, AdvanceStatus
from apps.employees.services import advances as svc
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent, PayrollRunType
from apps.payroll.services import engine


@pytest.fixture
def env(db):
    r = provision_account(slug="ap-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="زياد", family_name_ar="العسيري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011122288", mobile="0501112228")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="V-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])

        adv = Advance.objects.create(
            account=acc, company=comp, employment=emp,
            advance_no="ADV-1", amount=Decimal("6000"),
            installments_count=6, installment_amount=Decimal("1000"),
            start_year=2026, start_month=1,
            status=AdvanceStatus.ACTIVE, reason="سلفة")

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "adv": adv}


def test_deduction_is_on_by_default(env):
    """الخصم مفعّل افتراضًا — فهو الأصل."""
    with account_scope(env["account_id"]):
        assert env["adv"].auto_deduct is True
        assert env["adv"].is_deductible is True


def test_pause_needs_a_reason(env):
    """
    ⚠️ **وبسببٍ إلزاميّ**: فإيقافٌ بلا سبب يُنسى، ويبقى الموظف
    غير مخصوم عليه سنين.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.AdvanceError) as e:
            svc.pause_deduction(advance=env["adv"], reason="")
        assert "سبب" in str(e.value)


def test_paused_debt_remains(env):
    """
    ⚠️⚠️ الأهمّ: **الإيقاف تأخيرٌ لا إعفاء**.

    فالرصيد يبقى دَينًا — وعدُّه مسدَّدًا يُهدر مال الشركة.
    """
    with account_scope(env["account_id"]):
        svc.pause_deduction(advance=env["adv"], reason="ظرف طارئ")
        env["adv"].refresh_from_db()

        assert env["adv"].is_outstanding is True, "ضاع الدَين"
        assert env["adv"].is_deductible is False
        assert env["adv"].outstanding == Decimal("6000")


def test_paused_is_excluded_from_payroll(env):
    """
    **والمسير لا يخصمها** — فمن أُوقف خصمه لا يُقتطع من راتبه.
    """
    with account_scope(env["account_id"]):
        ids = list(svc.deductible_advances(env["emp"])
                   .values_list("id", flat=True))
        assert env["adv"].id in ids

        svc.pause_deduction(advance=env["adv"], reason="ظرف")
        ids2 = list(svc.deductible_advances(env["emp"])
                    .values_list("id", flat=True))
        assert env["adv"].id not in ids2


def test_paused_still_counts_on_termination(env):
    """
    ⚠️ **ويُخصم كاملًا في نهاية الخدمة**: فالدَين لا يُعفى
    بإيقاف قسطه.
    """
    with account_scope(env["account_id"]):
        svc.pause_deduction(advance=env["adv"], reason="ظرف")
        ids = list(svc.outstanding_advances(env["emp"])
                   .values_list("id", flat=True))
        assert env["adv"].id in ids, "سقط الدَين من المخالصة"
        assert svc.total_outstanding(env["emp"]) == Decimal("6000")


def test_payslip_has_no_advance_line_when_paused(env):
    """والقسيمة تخلو من قسطها — لا بصفرٍ بل بغيابه."""
    with account_scope(env["account_id"]):
        svc.pause_deduction(advance=env["adv"], reason="ظرف")

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        slip = run.payslips.first()
        codes = [l.component_code for l in slip.lines.all()]
        assert not any(c.startswith("ADVANCE_") for c in codes), codes


def test_resume_restores_deduction(env):
    """والاستئناف يُعيد الخصم."""
    with account_scope(env["account_id"]):
        svc.pause_deduction(advance=env["adv"], reason="ظرف")
        svc.resume_deduction(advance=env["adv"])
        env["adv"].refresh_from_db()
        assert env["adv"].is_deductible is True
        assert env["adv"].deduct_paused_reason == ""


def test_double_pause_refused(env):
    """ولا يُوقَف موقوف، ولا يُستأنف مفعَّل."""
    with account_scope(env["account_id"]):
        svc.pause_deduction(advance=env["adv"], reason="ظرف")
        with pytest.raises(svc.AdvanceError):
            svc.pause_deduction(advance=env["adv"], reason="ثانية")
        svc.resume_deduction(advance=env["adv"])
        with pytest.raises(svc.AdvanceError):
            svc.resume_deduction(advance=env["adv"])
