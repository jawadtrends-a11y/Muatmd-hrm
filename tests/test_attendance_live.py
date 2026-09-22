"""
حرّاس الحضور المباشر (ق-235).

⚠️⚠️ **كان الحضور لا يُحتسب إلا بزرٍّ يدويّ** — فلا يرى الموظف بصمته، ولا غياب
يُعرف، **والمسير يصرف الشهر كاملًا للجميع**. وقرار جواد: «يُحدَّث مباشرةً —
غائبٌ فور بداية الدوام بلا بصمة، وحاضرٌ متأخّرٌ فور البصمة».
"""
from datetime import date, time

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance import tasks
from apps.attendance.models import AttendanceDay, Shift, ShiftAssignment
from apps.attendance.services.processing import record_punch
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person


def _env(start):
    r = provision_account(slug=f"al-{start.hour}", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        p, _ = create_person(account=acc, first_name_ar="سعد", family_name_ar="الشمري",
                             gender="male", nationality_code="SA", id_type="national_id",
                             id_number=f"1{start.hour:02d}7776661", mobile=f"05{start.hour:02d}777666")
        emp = create_employment(person=p, company=comp, employee_no="L1",
                                join_date=date(2023, 1, 1))
        emp = emp[0] if isinstance(emp, tuple) else emp
        sh = Shift.objects.create(account=acc, company=comp, code=f"S{start.hour}",
                                  name_ar="فترة", start_time=start, end_time=time(23, 59))
        ShiftAssignment.objects.create(account=acc, company=comp, employment=emp,
                                       shift=sh, effective_from=date(2023, 1, 1))
    return r.account_id, emp


def test_punch_processes_its_day_immediately(db):
    """⚠️⚠️ الأهمّ: **البصمة يُحتسب يومها فورًا** — لا بزرٍّ ولا ليلًا."""
    acc, emp = _env(time(0, 0, 1))
    with account_scope(acc):
        record_punch(employment=emp, punched_at=timezone.now(), source="device")
        assert AttendanceDay.objects.filter(employment=emp,
                                            work_date=timezone.localdate()).exists()


def test_sweep_marks_started_shift_without_punch(db):
    """«غائب» فور بداية الدوام بلا بصمة — ومن بدأ دوامه يُسجَّل يومه."""
    acc, emp = _env(time(0, 0, 1))
    tasks.process_account_absences.apply(kwargs={"account_id": acc})
    with account_scope(acc):
        d = AttendanceDay.objects.filter(employment=emp, work_date=timezone.localdate()).first()
        assert d is not None and d.status != "present"


def test_sweep_waits_for_shift_start(db):
    """⚠️ **ومن لم يبدأ دوامه لا يُسجَّل غائبًا** — فالمحرّك لا يعرف الساعة."""
    if timezone.localtime().time() >= time(23, 59):
        pytest.skip("لحظة نهاية اليوم")
    acc, emp = _env(time(23, 59, 59))
    tasks.process_account_absences.apply(kwargs={"account_id": acc})
    with account_scope(acc):
        assert not AttendanceDay.objects.filter(employment=emp,
                                                work_date=timezone.localdate()).exists()


def test_provisioning_creates_default_shift(db):
    """⚠️⚠️ **والتأسيس يُنشئ الفترة الافتراضية** — وكان لا يُنشئها فلا غياب يُحسب."""
    from apps.attendance.services.rules import effective_shift
    r = provision_account(slug="ds-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        sh = Shift.objects.get(company_id=r.company_id, is_default=True)
        assert (sh.start_time, sh.end_time) == (time(8), time(17))
        assert sh.grace_in_minutes == 15
        assert sh.working_days == [0, 1, 2, 3, 4]      # الأحد → الخميس (0=الأحد)


def test_manual_attendance_company_is_skipped(db):
    """⚠️ **والشركة التي أوقفت الاحتساب لا يُسجَّل موظفوها غائبين** — فلا تُصفَّر رواتبها."""
    from apps.payroll.models import PayrollSettings
    acc, emp = _env(time(0, 0, 2))
    with account_scope(acc):
        PayrollSettings.objects.filter(company_id=emp.company_id).update(auto_attendance=False)
    tasks.process_account_absences.apply(kwargs={"account_id": acc})
    with account_scope(acc):
        assert not AttendanceDay.objects.filter(employment=emp,
                                                work_date=timezone.localdate()).exists()


def test_annual_balance_accrues_on_read(db):
    """
    ⚠️⚠️ **ورصيد السنوية يُحسب عند قراءته** — فموظفٌ منذ ٢٠٢٣ كان بلا سجلّ رصيد
    ولا تظهر له «السنوية» أصلًا.
    """
    from decimal import Decimal
    from apps.leaves.models import LeaveType
    from apps.leaves.services.balances import balance_summary, consume
    acc, emp = _env(time(0, 0, 3))
    with account_scope(acc):
        rows = {r["code"]: r for r in balance_summary(emp)}
        assert "ANNUAL" in rows and Decimal(rows["ANNUAL"]["available"]) > 0
        assert "MARRIAGE" not in rows                 # المناسبات لا رصيد لها — فلا تتكرّر
        consume(emp, LeaveType.objects.get(company_id=emp.company_id, code="ANNUAL"), 1)
