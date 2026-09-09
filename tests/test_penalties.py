"""
حرّاس الجزاءات التأديبية (ق-119، ق-121).

⚠️ نظامية وماليّة: القيود من النموذج الموحّد للائحة تنظيم العمل
(وزارة الموارد البشرية) — تجاوزها يعرّض المنشأة للمساءلة.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models_penalties import (
    Penalty, PenaltyKind, PenaltyStatus, ViolationType)
from apps.employees.services import penalties as svc
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayrollSettings


@pytest.fixture
def env(db):
    from apps.employees.models import SalaryStructure
    from apps.payroll.models import PayComponent

    r = provision_account(slug="pen-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        svc.provision_default_violations(comp)

        p, _ = create_person(
            account=acc, first_name_ar="راشد", family_name_ar="العمري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1033344455", mobile="0503334445")
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="P-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("6000"))])

        yield {"account_id": r.account_id, "company": comp,
               "employment": emp}


def _v(env, code):
    return ViolationType.objects.get(company=env["company"], code=code)


def test_repeat_escalates_the_degree(env):
    """التدرّج: الأولى إنذار أو ربع يوم، ثم تصعد بالتكرار."""
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        emp = env["employment"]
        seen = []
        for i in range(3):
            p = svc.preview(emp, v, date(2026, 3, 1))
            seen.append(Decimal(p["days"]))
            svc.issue(employment=emp, violation=v,
                      occurred_on=date(2026, 3, 1),
                      description="تأخر", employee_statement="أفاد")
        assert seen == [Decimal("0.25"), Decimal("0.50"), Decimal("1.00")], seen


def test_monthly_cap_is_five_days(env):
    """
    ⚠️ السقف: لا يُقتطع أكثر من **أجر خمسة أيام في الشهر**.

    نصٌّ في النموذج الموحّد — وتجاوزه مخالفة.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "ABSENT-1")
        emp = env["employment"]
        for i in range(4):
            try:
                svc.issue(employment=emp, violation=v,
                          occurred_on=date(2026, 4, 1 + i),
                          description="غياب", employee_statement="أفاد")
            except svc.PenaltyError:
                pass
        total = svc.deducted_days_in_month(emp, date(2026, 4, 1))
        assert total <= Decimal("5"), total


def test_statement_required_above_one_day(env):
    """
    ⚠️ ما تجاوز **أجر يوم واحد** يلزمه سماع أقوال الموظف ومحضر.

    فالنموذج يوجب إبلاغه كتابةً وتحقيق دفاعه قبل توقيعه.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "ABSENT-1")
        emp = env["employment"]
        # الأولى يوم — تمرّ بلا إفادة
        svc.issue(employment=emp, violation=v, occurred_on=date(2026, 5, 1),
                  description="غياب", employee_statement="")
        # الثانية يومان — تُرفض بلا إفادة
        with pytest.raises(svc.PenaltyError):
            svc.issue(employment=emp, violation=v,
                      occurred_on=date(2026, 5, 2),
                      description="غياب", employee_statement="")


def test_reset_days_drops_old_repeats(env):
    """
    ما مضى على سابقته أكثر من **مدّة السقوط** يُعدّ أولى.

    فالموظف لا يُلاحَق بمخالفةٍ قديمة أبدًا.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        emp = env["employment"]
        svc.issue(employment=emp, violation=v, occurred_on=date(2025, 1, 1),
                  description="قديمة", employee_statement="")
        # بعد مدّة السقوط (١٨٠ يومًا افتراضًا)
        later = date(2025, 1, 1) + timedelta(days=v.reset_days + 10)
        assert svc.occurrence_for(emp, v, later) == 1


def test_documented_without_deduction(env):
    """
    ⚠️ الخصم **قرار إداريّ**: تُوثَّق المخالفة بلا خصم.

    والجزاء يبقى في صحيفته — فالتوثيق لا يُهدر.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "ABSENT-1")
        emp = env["employment"]
        pen = svc.issue(employment=emp, violation=v,
                        occurred_on=date(2026, 6, 1),
                        description="غياب", employee_statement="أفاد",
                        apply_deduction=False)
        assert pen.amount == Decimal("0")
        assert pen.days == Decimal("0")
        assert svc.deducted_days_in_month(emp, date(2026, 6, 1)) == 0
        assert Penalty.objects.filter(employment=emp).exists()


def test_occurrence_not_counted_stays_at_degree(env):
    """
    ⚠️ والتكرار قرارٌ كذلك: ما لم يُحتسب لا يرفع الدرجة.

    فالتوثيق حفظُ واقعة، والتصعيد يُقرَّر.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        emp = env["employment"]
        svc.issue(employment=emp, violation=v, occurred_on=date(2026, 7, 1),
                  description="تأخر", employee_statement="",
                  count_occurrence=False)
        assert svc.occurrence_for(emp, v, date(2026, 7, 2)) == 1


def test_company_switch_disables_all_deductions(env):
    """وإعدادُ الشركة سقفٌ فوقهما — مطفأً لا خصم في النظام كلّه."""
    with account_scope(env["account_id"]):
        PayrollSettings.objects.filter(
            company=env["company"]).update(penalties_deduct_enabled=False)
        v = _v(env, "ABSENT-1")
        p = svc.preview(env["employment"], v, date(2026, 8, 1))
        assert not p["deductible"]
        assert Decimal(p["days"]) == 0


def test_violation_without_financial_effect(env):
    """وبندٌ بلا أثر ماليّ يُوثَّق ولا يُخصم مهما كانت درجته."""
    with account_scope(env["account_id"]):
        v = _v(env, "ABSENT-1")
        ViolationType.objects.filter(id=v.id).update(financial_effect=False)
        v.refresh_from_db()
        p = svc.preview(env["employment"], v, date(2026, 9, 1))
        assert not p["deductible"]


def test_pending_board_lists_unsigned_violations(env):
    """
    سجلّ المقترحات يعرض من خالف ولم يُوقَّع عليه — بحسم وقته.

    فما لا يُعرض لا يُطبَّق، والمسؤول لا يبحث عن المخالفين.
    """
    from apps.attendance.models import AttendanceDay, DayStatus

    with account_scope(env["account_id"]):
        AttendanceDay.objects.create(
            account_id=env["account_id"], company=env["company"],
            employment=env["employment"], work_date=date(2026, 10, 5),
            status=DayStatus.PRESENT, late_minutes=45)

        rows = svc.pending_board(env["company"], date(2026, 10, 1),
                                 date(2026, 10, 31))
        assert len(rows) == 1
        assert rows[0]["minutes"] == 45
        # ٤٥ دقيقة من ٦٠٠٠ على ثماني ساعات = ١٨.٧٥
        assert Decimal(rows[0]["time_deduction"]) == Decimal("18.75")


def test_signed_day_leaves_the_board(env):
    """وما وُقّع عليه يخرج من السجلّ — فلا يُوقَّع مرّتين."""
    from apps.attendance.models import AttendanceDay, DayStatus

    with account_scope(env["account_id"]):
        AttendanceDay.objects.create(
            account_id=env["account_id"], company=env["company"],
            employment=env["employment"], work_date=date(2026, 11, 3),
            status=DayStatus.ABSENT)

        rows = svc.pending_board(env["company"], date(2026, 11, 1),
                                 date(2026, 11, 30))
        assert len(rows) == 1

        svc.issue_batch(company=env["company"], rows=rows,
                        employee_statement="أفاد")
        after = svc.pending_board(env["company"], date(2026, 11, 1),
                                  date(2026, 11, 30))
        assert after == []
