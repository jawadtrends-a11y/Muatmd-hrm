"""
حرّاس تذكير المديرين (ق-105).

التوقيت هو الميزة: تذكيرٌ بعد انصرافه لا قيمة له، وتذكيرٌ في وقت
ثابت للجميع يخطئ أكثرهم.
"""
from datetime import date, time

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import Shift, ShiftAssignment
from apps.attendance.models_exemption import AttendanceExemption
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.tasks_reminders import (
    EXEMPT_HOUR, HOURS_BEFORE, _reminder_time, _within_window)


@pytest.fixture
def env(db):
    r = provision_account(slug="rem-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        day = Shift.objects.create(
            account=acc, company=comp, code="DAY", name_ar="نهاري",
            start_time="08:00", end_time="17:00",
            working_days=[0, 1, 2, 3, 4], is_default=True)
        evening = Shift.objects.create(
            account=acc, company=comp, code="EVE", name_ar="مسائي",
            start_time="14:00", end_time="22:00",
            working_days=[0, 1, 2, 3, 4])

        def mk(no, idn, mob, first, family, shift=None):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA", id_type="national_id",
                id_number=idn, mobile=mob)
            e, _, _ = create_employment(person=p, company=comp,
                                        employee_no=no,
                                        join_date=date(2024, 1, 1))
            if shift:
                ShiftAssignment.objects.create(
                    account=acc, company=comp, employment=e, shift=shift,
                    effective_from=date(2024, 1, 1))
            return e

        yield {
            "account_id": r.account_id, "company": comp,
            "day_emp": mk("R-1", "1011122201", "0501110001",
                          "سلطان", "الدوسري"),
            "eve_emp": mk("R-2", "1011122202", "0501110002",
                          "بندر", "العتيبي", evening),
            "shift": day,
        }


def test_reminder_is_two_hours_before_shift_end(env):
    """فترته تنتهي 17:00 → يُذكَّر 15:00."""
    with account_scope(env["account_id"]):
        t = _reminder_time(env["day_emp"], date(2026, 6, 8))   # اثنين
        assert t == time(17 - HOURS_BEFORE, 0), t


def test_reminder_follows_each_shift(env):
    """
    ⚠️ الوقت ليس ثابتًا: صاحب الفترة المسائية (تنتهي 22:00)
    يُذكَّر 20:00 لا 15:00 — والوقت الموحّد يخطئه بخمس ساعات.
    """
    with account_scope(env["account_id"]):
        t = _reminder_time(env["eve_emp"], date(2026, 6, 8))
        assert t == time(22 - HOURS_BEFORE, 0), t


def test_exempt_manager_reminded_at_three(env):
    """
    من أُعفي من البصمة لا نهاية لفترته عمليًّا — الثالثة عصرًا.

    ويُختبر بصاحب الفترة المسائية عمدًا: فترته تنتهي 22:00 فوقته
    الطبيعي 20:00، والإعفاء يحوّله إلى 15:00. ولو اختبرناه بالنهاري
    (17:00 ← 15:00) لنجح الاختبار بالصدفة لا بالمنطق.
    """
    emp = env["eve_emp"]
    with account_scope(env["account_id"]):
        assert _reminder_time(emp, date(2026, 6, 8)) == time(20, 0)
        AttendanceExemption.objects.create(
            account_id=env["account_id"], company=env["company"],
            employment=emp, start_date=date(2026, 1, 1), reason="مدير عام")
        assert _reminder_time(emp, date(2026, 6, 8)) == time(EXEMPT_HOUR, 0)


def test_no_reminder_on_weekend(env):
    """لا قرار يُنتظر ممّن ليس على رأس عمله."""
    with account_scope(env["account_id"]):
        assert _reminder_time(env["day_emp"], date(2026, 6, 12)) is None


def test_window_fires_once_not_early_nor_late():
    """
    النافذة ربع ساعة: تُطلق مرّة واحدة في دورتها.

    وبلا حدّ أعلى يتكرّر التذكير كل ربع ساعة حتى نهاية الدوام،
    وبلا حدّ أدنى يُطلق قبل أوانه.
    """
    assert _within_window(time(15, 0), time(15, 0))
    assert _within_window(time(15, 0), time(15, 14))
    assert not _within_window(time(15, 0), time(15, 15))
    assert not _within_window(time(15, 0), time(14, 59))
    assert not _within_window(None, time(15, 0))
