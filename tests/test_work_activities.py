"""
حرّاس أنشطة العمل (ق-143).

**المدير يُسند نشاطًا يوميًّا** — موصوفًا أو بعددٍ مستهدَف —
**ويُسجَّل سلفًا لمدًى**.

⚠️ **والجزئيّ والمتعذّر يُحدَّد فيهما ما أُنجز وما لم يُنجَز** —
فالمدير يعرف العائق لا الرقم وحده (قرار جواد).

⚠️⚠️ **والأثر الماليّ لا يقع بإقرار الموظف وحده** — بل بمراجعةٍ
يعتمدها المدير.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models import (
    ActivityStatus, PayBasis, PayEffect, WorkActivity)
from apps.employees.services import activities as svc
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    PayComponent, PayrollRunStatus, PayrollRunType, PayrollSettings)
from apps.payroll.services import engine

TODAY = date.today()


@pytest.fixture
def env(db):
    r = provision_account(slug="act-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="ماجد", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1033344499", mobile="0503334449")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="A-9",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("8000"))])

        st = PayrollSettings.objects.get(company=comp)
        st.activities_enabled = True
        st.save(update_fields=["activities_enabled"])

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "settings": st}


def _assign(env, **kw):
    base = {"employment": env["emp"], "title": "إدخال معاملات",
            "start_date": date(2026, 9, 1), "end_date": date(2026, 9, 5),
            "skip_weekends": False}
    base.update(kw)
    return svc.assign(**base)


def _first(env):
    return WorkActivity.objects.filter(
        employment=env["emp"]).order_by("work_date").first()


def test_disabled_in_settings_blocks_assignment(env):
    """
    ⚠️ **ثلاث طبقات**: الباقة، ثم إعدادات الشركة، ثم اختيار المدير.

    فمن أغلقها من الأساس لا تُسند لموظفيه.
    """
    with account_scope(env["account_id"]):
        env["settings"].activities_enabled = False
        env["settings"].save(update_fields=["activities_enabled"])
        with pytest.raises(svc.ActivityError) as e:
            _assign(env)
        assert "غير مفعَّلة" in str(e.value)


def test_assign_spans_a_range(env):
    """**ويُسجَّل سلفًا لمدًى** — فلا يُعاد إدخاله كل صباح."""
    with account_scope(env["account_id"]):
        out = _assign(env)
        assert out["created"] == 5
        assert WorkActivity.objects.filter(
            employment=env["emp"]).count() == 5


def test_descriptive_activity_needs_no_target(env):
    """
    ⚠️ **والهدف العدديّ اختياريّ**: فنشاطٌ كتابيّ لا يُقاس برقم.
    """
    with account_scope(env["account_id"]):
        _assign(env, title="راجع ملفّات القسم")
        a = _first(env)
        assert a.is_measurable is False
        assert a.achievement is None

        svc.report(activity=a, status=ActivityStatus.DONE,
                   done_note="اكتملت المراجعة")
        assert a.status == ActivityStatus.DONE


def test_partial_requires_both_notes(env):
    """
    ⚠️⚠️ الأهمّ: **الجزئيّ يُحدَّد فيه ما أُنجز وما لم يُنجَز**.

    فالمدير يعرف العائق لا الرقم وحده — وسببٌ عامّ لا يكفي.
    """
    with account_scope(env["account_id"]):
        _assign(env, target_count=20, unit="معاملة")
        a = _first(env)

        with pytest.raises(svc.ActivityError):
            svc.report(activity=a, status=ActivityStatus.PARTIAL,
                       done_count=12)
        with pytest.raises(svc.ActivityError):
            svc.report(activity=a, status=ActivityStatus.PARTIAL,
                       done_count=12, pending_note="تعذّر")

        svc.report(activity=a, status=ActivityStatus.PARTIAL,
                   done_count=12, done_note="١٢ معاملة",
                   pending_note="٨ لانقطاع النظام")
        assert a.achievement == 60


def test_not_done_requires_a_reason(env):
    """والمتعذّر كذلك — فلا يمرّ بلا بيان."""
    with account_scope(env["account_id"]):
        _assign(env)
        a = _first(env)
        with pytest.raises(svc.ActivityError):
            svc.report(activity=a, status=ActivityStatus.NOT_DONE)


def test_amount_per_unit(env):
    """والاحتساب لكل وحدة يضرب المنجَز في المبلغ."""
    with account_scope(env["account_id"]):
        _assign(env, target_count=20, unit="معاملة",
                pay_effect=PayEffect.BONUS, pay_basis=PayBasis.PER_UNIT,
                bonus_amount=Decimal("5"))
        a = _first(env)
        svc.report(activity=a, status=ActivityStatus.DONE, done_count=20,
                   done_note="تمّت")
        assert svc.compute_amount(a) == Decimal("100")


def test_pending_activity_is_not_a_shortfall(env):
    """
    ⚠️ **ولا يُحتسب لما لم يُقرّ بعد**: فنشاطٌ بانتظار الإقرار
    ليس تقصيرًا — وحسمُه ظلم.
    """
    with account_scope(env["account_id"]):
        _assign(env, target_count=10,
                pay_effect=PayEffect.DEDUCTION,
                pay_basis=PayBasis.PER_ACTIVITY,
                deduction_amount=Decimal("50"))
        a = _first(env)
        assert a.status == ActivityStatus.PENDING
        assert svc.compute_amount(a) == Decimal("0")


def test_review_is_required_before_pay(env):
    """
    ⚠️⚠️ **والأثر لا يقع بإقرار الموظف وحده**.

    فمالٌ يُصرف بقول صاحبه بلا مراجعة — والمراجعة هي الضابط.
    """
    with account_scope(env["account_id"]):
        _assign(env, target_count=20, pay_effect=PayEffect.BONUS,
                pay_basis=PayBasis.PER_UNIT, bonus_amount=Decimal("5"))
        a = _first(env)
        svc.report(activity=a, status=ActivityStatus.DONE, done_count=20,
                   done_note="تمّت")

        # ⚠️ **والمسير لا يراه قبل المراجعة** — فالفحص هناك أصدق:
        # فـ settled_amount فارغٌ قبلها، ومجموعُه صفرٌ بأيّ حال.
        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        slip = run.payslips.first()
        assert "ACTIVITY" not in [l.component_code
                                  for l in slip.lines.all()], (
            "دخل المسير بلا مراجعة")

        svc.review(activity=a)
        assert svc.pending_amount(env["emp"], 2026, 9) == Decimal("100")

        engine.calculate_run(run)
        slip = run.payslips.first()
        assert "ACTIVITY" in [l.component_code for l in slip.lines.all()]


def test_review_before_report_refused(env):
    """ولا مراجعة قبل الإقرار."""
    with account_scope(env["account_id"]):
        _assign(env)
        with pytest.raises(svc.ActivityError):
            svc.review(activity=_first(env))


def test_reported_is_locked_after_review(env):
    """والمراجَع لا يُعدَّل إقراره — فالمال حُسم عليه."""
    with account_scope(env["account_id"]):
        _assign(env)
        a = _first(env)
        svc.report(activity=a, status=ActivityStatus.DONE,
                   done_note="تمّت")
        svc.review(activity=a)
        with pytest.raises(svc.ActivityError):
            svc.report(activity=a, status=ActivityStatus.NOT_DONE,
                       pending_note="تراجع")


def test_reviewed_lands_in_the_payslip(env):
    """والمراجَع يدخل القسيمة بندًا."""
    with account_scope(env["account_id"]):
        _assign(env, target_count=20, pay_effect=PayEffect.BONUS,
                pay_basis=PayBasis.PER_UNIT, bonus_amount=Decimal("5"))
        a = _first(env)
        svc.report(activity=a, status=ActivityStatus.DONE, done_count=20,
                   done_note="تمّت")
        svc.review(activity=a)

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        slip = run.payslips.first()
        assert "ACTIVITY" in [l.component_code for l in slip.lines.all()]


def test_paid_flag_rises_on_approval_only(env):
    """
    ⚠️ **وتُعلَّم مدفوعةً عند الاعتماد لا الحساب** — فمسيرٌ يُلغى
    لا يستهلكها.
    """
    with account_scope(env["account_id"]):
        _assign(env, target_count=20, pay_effect=PayEffect.BONUS,
                pay_basis=PayBasis.PER_UNIT, bonus_amount=Decimal("5"))
        a = _first(env)
        svc.report(activity=a, status=ActivityStatus.DONE, done_count=20,
                   done_note="تمّت")
        svc.review(activity=a)

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        a.refresh_from_db()
        assert a.is_paid is False, "استُهلك النشاط بمجرّد الحساب"

        run.status = PayrollRunStatus.SUBMITTED
        run.save(update_fields=["status"])
        engine.approve_run(run, None)
        a.refresh_from_db()
        assert a.is_paid is True
