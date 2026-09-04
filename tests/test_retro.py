"""
حرّاس التسويات الرجعية (ق-69).

ما تمنعه:
  • تسوية عن شهر ما زال مسيره مفتوحًا — فالاحتساب يأخذ التصحيح
  • ردّ الخصم كاملًا بدل الفرق — فمن تأخر ساعة لا يستحق ساعتين
  • فتح مسير مغلق بعد المهلة
  • قرار يُعاد على تسوية حُسم أمرها
  • تسرّبها بين الشركات
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (AccountMembership, Role,
                                         RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay, DayStatus
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.models import Employment
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import Request, RequestStatus, RequestType
from apps.leaves.services.requests import apply_effect
from apps.payroll.models import (PayrollRun, PayrollRunStatus, PayrollRunType,
                                 PayrollSettings, RetroAdjustment,
                                 RetroSource, RetroStatus)
from apps.payroll.services.retro import (RetroError, can_reopen,
                                         closed_run_for, decide_adjustment,
                                         merge_into_run, record_adjustment,
                                         revive_deferred)


@pytest.fixture
def env(db):
    r = provision_account(slug="retro-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        def hire(first, family, nid, mobile, no, code, scope, pay=9000):
            from apps.payroll.models import PayComponent
            basic = PayComponent.objects.get(company=comp, code="BASIC")
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mobile)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=date(2023, 1, 1),
                salary_lines=[(basic, pay)])
            u = User.objects.create_user(username=f"rt.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, role=Role.objects.get(account=acc, code=code),
                company=comp, scope=scope.value)
            return e

        hrs = hire("أمل", "الغامدي", "1011122233", "0501112223", "H1",
                   "hr_staff", Scope.COMPANY)
        emp = hire("وليد", "العنزي", "1022233344", "0502223334", "E1",
                   "employee", Scope.OWN)

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "hrs": hrs, "emp": emp}


def _closed_run(env, year, month, approved_ago_hours=1):
    """مسير مغلق منذ ساعة (داخل المهلة)."""
    return PayrollRun.objects.create(
        account_id=env["acc"].id, company_id=env["comp"].id,
        run_no=f"PR-{year}{month:02d}-T", run_type=PayrollRunType.REGULAR,
        period_year=year, period_month=month,
        accrual_date=date(year, month, 28),
        status=PayrollRunStatus.APPROVED,
        approved_at=timezone.now() - timedelta(hours=approved_ago_hours))


def _fix_request(env, work_date, before_minutes):
    """يوم محتسب ناقصًا ثم طلب تصحيح معتمَد."""
    AttendanceDay.objects.filter(
        employment=env["emp"], work_date=work_date).delete()
    AttendanceDay.objects.create(
        account_id=env["acc"].id, company_id=env["comp"].id,
        employment=env["emp"], work_date=work_date,
        status=DayStatus.PRESENT, worked_minutes=before_minutes)

    return Request.objects.create(
        account_id=env["acc"].id, company_id=env["comp"].id,
        request_no=f"AF-{work_date}", employment=env["emp"],
        request_type=RequestType.ATTENDANCE_FIX,
        status=RequestStatus.APPROVED,
        payload={"work_date": str(work_date), "fix_target": "both",
                 "first_in": "08:00", "last_out": "16:00",
                 "reason": "نسيان بصمة"})


# ══════════ متى تُنشأ التسوية ══════════

@pytest.mark.django_db(transaction=True)
def test_no_retro_when_run_open(env):
    """
    ⚠️ المسير المفتوح لا يحتاج تسوية — فالاحتساب القادم يأخذ
    التصحيح بنفسه، وإنشاؤها يعني صرف الفرق مرتين.
    """
    wd = date(2026, 8, 12)
    with account_scope(env["account_id"]):
        req = _fix_request(env, wd, 360)
        apply_effect(req)
        assert RetroAdjustment.objects.count() == 0, (
            "أُنشئت تسوية ومسير الشهر مفتوح — الفرق يُصرف مرتين")


@pytest.mark.django_db(transaction=True)
def test_retro_created_when_run_closed(env):
    """التصحيح في شهر أُغلق مسيره يترك فرقًا مستحقًا."""
    wd = date(2026, 8, 12)
    with account_scope(env["account_id"]):
        _closed_run(env, 2026, 8)
        req = _fix_request(env, wd, 360)
        apply_effect(req)
        adj = RetroAdjustment.objects.first()

    assert adj is not None, "لم تُنشأ تسوية والمسير مغلق"
    assert adj.period_year == 2026 and adj.period_month == 8
    assert adj.source == RetroSource.ATTENDANCE_FIX


@pytest.mark.django_db(transaction=True)
def test_amount_is_the_difference_not_the_deduction(env):
    """
    ⚠️ الحارس الحرج: الفرق لا الخصم كاملًا.

    من تأخر ساعة ونسي بصمته ساعتين يعود له أجر ساعة — والتسوية
    تُحتسب بالدقائق المستعادة لا بقيمة اليوم.
    """
    wd = date(2026, 8, 12)
    with account_scope(env["account_id"]):
        _closed_run(env, 2026, 8)
        req = _fix_request(env, wd, 420)      # نقصت 60 دقيقة فقط
        apply_effect(req)
        adj = RetroAdjustment.objects.first()

        from apps.leaves.services.requests import _daily_wage
        daily = _daily_wage(env["emp"])

    assert adj is not None
    expected = (daily / Decimal("480") * Decimal("60")).quantize(
        Decimal("0.01"))
    assert adj.amount == expected, (
        f"التسوية {adj.amount} والمتوقّع {expected} — حُسبت بقيمة اليوم "
        f"لا بالدقائق المستعادة")
    assert adj.amount < daily, "التسوية تجاوزت أجر اليوم كاملًا"


@pytest.mark.django_db(transaction=True)
def test_no_retro_when_nothing_gained(env):
    """يوم كامل أصلًا لا يترك فرقًا — فلا تسوية."""
    wd = date(2026, 8, 12)
    with account_scope(env["account_id"]):
        _closed_run(env, 2026, 8)
        req = _fix_request(env, wd, 480)      # كامل أصلًا
        apply_effect(req)
        assert RetroAdjustment.objects.count() == 0


# ══════════ مهلة إعادة الفتح ══════════

@pytest.mark.django_db(transaction=True)
def test_reopen_allowed_within_window(env):
    """إعادة فتح المسير ممكنة داخل المهلة."""
    with account_scope(env["account_id"]):
        run = _closed_run(env, 2026, 8, approved_ago_hours=2)
        st = PayrollSettings.objects.filter(company=env["comp"]).first()
        assert can_reopen(run, st), "مُنعت إعادة الفتح داخل المهلة"


@pytest.mark.django_db(transaction=True)
def test_reopen_denied_after_window(env):
    """
    ⚠️ بعد المهلة لا يُمسّ المسير المغلق (ق-44) — وتصير التسوية
    في التالي حتمًا.
    """
    with account_scope(env["account_id"]):
        run = _closed_run(env, 2026, 8, approved_ago_hours=72)
        st = PayrollSettings.objects.filter(company=env["comp"]).first()
        assert not can_reopen(run, st), "أُعيد فتح مسير تجاوز المهلة"


# ══════════ قرار موظف الموارد ══════════

@pytest.mark.django_db(transaction=True)
def test_defer_keeps_it_alive(env):
    """
    التأجيل يبقيها معلّقة لمسير لاحق — لا يُلغيها.
    """
    with account_scope(env["account_id"]):
        adj = record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=100)
        decide_adjustment(adjustment=adj, action="defer")
        adj.refresh_from_db()
        assert adj.status == RetroStatus.DEFERRED

        revive_deferred(company=env["comp"])
        adj.refresh_from_db()
        assert adj.status == RetroStatus.PENDING, (
            "المؤجَّلة لم تعد معلّقة — ضاع استحقاق الموظف")


@pytest.mark.django_db(transaction=True)
def test_cancel_ends_it(env):
    """الإلغاء ينهيها — ولا تعود بالإحياء."""
    with account_scope(env["account_id"]):
        adj = record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=100)
        decide_adjustment(adjustment=adj, action="cancel")
        revive_deferred(company=env["comp"])
        adj.refresh_from_db()

    assert adj.status == RetroStatus.CANCELLED, "عادت الملغاة"


@pytest.mark.django_db(transaction=True)
def test_decision_is_final(env):
    """لا يُعاد القرار على تسوية حُسم أمرها (ق-44)."""
    with account_scope(env["account_id"]):
        adj = record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=100)
        decide_adjustment(adjustment=adj, action="cancel")
        with pytest.raises(RetroError):
            decide_adjustment(adjustment=adj, action="defer")


@pytest.mark.django_db(transaction=True)
def test_no_merge_into_approved_run(env):
    """
    ⚠️ لا تُدرج تسوية في مسير معتمَد — فالمعتمَد لا يُمسّ.
    """
    with account_scope(env["account_id"]):
        adj = record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=100)
        run = _closed_run(env, 2026, 9)
        with pytest.raises(RetroError):
            merge_into_run(adjustments=[adj], run=run)


# ══════════ العزل ══════════

@pytest.mark.django_db(transaction=True)
def test_only_hr_sees_retro(env):
    """التسويات فروق رواتب — لا يراها إلا من يُعدّ المسير."""
    c = Client()
    c.force_login(env["hrs"].person.user)
    assert c.get("/api/payroll/retro/").status_code == 200

    c2 = Client()
    c2.force_login(env["emp"].person.user)
    assert c2.get("/api/payroll/retro/").status_code == 403, (
        "موظف عادي يرى فروق رواتب غيره")

# ══════════ الدمج في القسيمة (ق-69) ══════════

def _run_payroll(env, year, month):
    """يُنشئ مسيرًا ويحتسبه — كما يفعل موظف الموارد."""
    from apps.payroll.models import PayrollRunType
    from apps.payroll.services.engine import calculate_run, create_run

    run = create_run(company=env["comp"], run_type=PayrollRunType.REGULAR,
                     year=year, month=month)
    calculate_run(run)
    return run


@pytest.mark.django_db(transaction=True)
def test_retro_becomes_payslip_line(env):
    """
    ⚠️ التسوية بندًا في القسيمة لا علمًا في جدول.

    فتعليمها «مدموجة» بلا بند لا يصل الموظف شيء.
    """
    from apps.payroll.models import Payslip

    with account_scope(env["account_id"]):
        record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=Decimal("78.12"),
            reason_ar="تصحيح بصمة أغسطس")

        run = _run_payroll(env, 2026, 9)
        slip = Payslip.objects.filter(run=run,
                                      employment=env["emp"]).first()
        lines = list(slip.lines.filter(
            component_code__startswith="RETRO")) if slip else []

    assert lines, "التسوية لم تصر بندًا في القسيمة"
    assert lines[0].amount == Decimal("78.12")
    assert "2026/08" in lines[0].name_ar, (
        f"البند بلا شهره: {lines[0].name_ar}")


@pytest.mark.django_db(transaction=True)
def test_retro_moves_the_net(env):
    """
    ⚠️ الحارس الحرج: التسوية تدخل الصافي.

    فبند يظهر ولا يُدفع أسوأ من غيابه — الموظف يقرأ استحقاقًا لم
    يصله.
    """
    from apps.payroll.models import Payslip

    with account_scope(env["account_id"]):
        base_run = _run_payroll(env, 2026, 10)
        base = Payslip.objects.get(run=base_run,
                                   employment=env["emp"]).net_pay

        record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=Decimal("100.00"))

        run = _run_payroll(env, 2026, 11)
        after = Payslip.objects.get(run=run, employment=env["emp"]).net_pay

    assert after == base + Decimal("100.00"), (
        f"الصافي {after} والمتوقّع {base + Decimal('100.00')} — "
        f"البند ظهر ولم يُدفع")


@pytest.mark.django_db(transaction=True)
def test_retro_paid_once(env):
    """
    ⚠️ لا تُصرف مرتين: تُعلَّم مدموجة بمسيرها فلا تعود في التالي.
    """
    from apps.payroll.models import Payslip

    with account_scope(env["account_id"]):
        adj = record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=Decimal("100.00"))

        first = _run_payroll(env, 2026, 9)
        adj.refresh_from_db()
        assert adj.status == RetroStatus.MERGED
        assert adj.merged_run_id == first.id, "لم تُنسب لمسيرها"

        second = _run_payroll(env, 2026, 10)
        slip = Payslip.objects.get(run=second, employment=env["emp"])
        again = slip.lines.filter(component_code__startswith="RETRO")

    assert not again.exists(), "صُرفت التسوية مرتين"


@pytest.mark.django_db(transaction=True)
def test_negative_retro_is_a_deduction(env):
    """
    التسوية السالبة استقطاع لا استحقاق — فالفرق قد يكون على
    الموظف لا له.
    """
    from apps.payroll.models import Payslip, PayslipLineType

    with account_scope(env["account_id"]):
        record_adjustment(
            employment=env["emp"], year=2026, month=8,
            source=RetroSource.OTHER,
            amount_before=Decimal("200.00"), amount_after=Decimal("50.00"))

        run = _run_payroll(env, 2026, 9)
        slip = Payslip.objects.get(run=run, employment=env["emp"])
        line = slip.lines.filter(
            component_code__startswith="RETRO").first()

    assert line is not None
    assert line.line_type == PayslipLineType.DEDUCTION, (
        "الفرق السالب ظهر استحقاقًا — يُدفع للموظف بدل أن يُخصم")
    assert line.amount == Decimal("150.00")


@pytest.mark.django_db(transaction=True)
def test_same_month_retro_not_merged(env):
    """
    تسوية شهر لا تُدرج في مسير الشهر نفسه — فالاحتساب يأخذها،
    وإدراجها يعني صرفها مرتين.
    """
    from apps.payroll.models import Payslip

    with account_scope(env["account_id"]):
        record_adjustment(
            employment=env["emp"], year=2026, month=9,
            source=RetroSource.ATTENDANCE_FIX,
            amount_before=0, amount_after=Decimal("100.00"))

        run = _run_payroll(env, 2026, 9)
        slip = Payslip.objects.get(run=run, employment=env["emp"])
        lines = slip.lines.filter(component_code__startswith="RETRO")

    assert not lines.exists(), "أُدرجت تسوية الشهر في مسيره"
