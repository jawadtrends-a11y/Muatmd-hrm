"""
حرّاس الحضور والانصراف.

أهمها test_overlapping_attendance_across_companies_is_allowed —
حارس قرار (ق-13) يمنع مبرمجًا لاحقًا من إضافة تحقق التداخل ظنًّا
منه أنه خلل.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import (
    AttendanceDay, AttendancePunch, DayStatus, Shift, ShiftAssignment,
)
from apps.attendance.services.processing import (
    AttendanceError, adjust_day_manually, approve_overtime,
    build_monthly_summary, process_employment_days, record_punch,
)
from apps.attendance.services.rules import compute_day
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayrollSettings
from apps.payroll.services.components import provision_default_components

TZ = timezone.get_current_timezone()


def _stamp(d, h, m=0):
    return timezone.make_aware(datetime(2026, 3, d, h, m), TZ)


@pytest.fixture
def env(db):
    r = provision_account(slug="att-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        c1 = Company.objects.get(id=r.company_id)
        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077788899", mobile="0507778889")
        e, _, _ = create_employment(person=p, company=c1, employee_no="A-1",
                                    join_date=date(2024, 1, 1))
        shift = Shift.objects.create(
            account=acc, company=c1, code="DAY", name_ar="صباحي",
            start_time="08:00", end_time="16:00", break_minutes=60,
            grace_in_minutes=15, working_days=[0, 1, 2, 3, 4])
        ShiftAssignment.objects.create(
            account=acc, company=c1, employment=e, shift=shift,
            effective_from=date(2024, 1, 1))
        yield {"account_id": r.account_id, "acc": acc, "c1": c1,
               "person": p, "emp": e, "shift": shift}


def _punch(emp, d, h, m=0, ref=""):
    return record_punch(employment=emp, punched_at=_stamp(d, h, m),
                        source="device", external_ref=ref)


# ══════════ قرار ق-13 — حارس لا يُلغى ══════════

@pytest.mark.django_db(transaction=True)
def test_overlapping_attendance_across_companies_is_allowed(env):
    """
    حارس قرار (ق-13): شخص واحد، شركتان، نفس اليوم، ساعات متداخلة.

    يجب أن يُقبل بلا خطأ وبلا تحذير وبلا علامة — الشخص قد يعمل
    حضوريًا في شركة وعن بُعد في أخرى.

    ⚠️ فشل هذا الاختبار يعني أن أحدهم أضاف تحقق تداخل — أزِله.
    """
    with account_scope(env["account_id"]):
        c2 = Company.objects.create(account=env["acc"], code="C2",
                                    legal_name_ar="شركة ثانية")
        provision_default_components(c2)
        PayrollSettings.objects.get_or_create(company=c2,
                                              defaults={"account": env["acc"]})
        e2, _, _ = create_employment(person=env["person"], company=c2,
                                     employee_no="B-1",
                                     join_date=date(2024, 1, 1))

        # نفس اليوم، ساعات متداخلة كليًا
        _punch(env["emp"], 2, 8, ref="a1")
        _punch(env["emp"], 2, 16, ref="a2")
        _punch(e2, 2, 10, ref="b1")
        _punch(e2, 2, 18, ref="b2")

        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 2),
                                end_date=date(2026, 3, 2))
        process_employment_days(employment=e2, start_date=date(2026, 3, 2),
                                end_date=date(2026, 3, 2))

        d1 = AttendanceDay.objects.get(employment=env["emp"],
                                       work_date=date(2026, 3, 2))
        d2 = AttendanceDay.objects.get(employment=e2,
                                       work_date=date(2026, 3, 2))
        assert d1.status == DayStatus.PRESENT
        assert d2.status == DayStatus.PRESENT
        assert not d1.is_manually_adjusted and not d2.is_manually_adjusted


# ══════════ قواعد الاحتساب ══════════

@pytest.mark.django_db(transaction=True)
def test_normal_day_deducts_break(env):
    with account_scope(env["account_id"]):
        _punch(env["emp"], 2, 7, 55, "p1")
        _punch(env["emp"], 2, 16, 5, "p2")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 2),
                                end_date=date(2026, 3, 2))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 2))
        assert d.status == DayStatus.PRESENT
        assert d.worked_minutes == 430      # 490 − 60 استراحة
        assert d.late_minutes == 0


@pytest.mark.django_db(transaction=True)
def test_late_beyond_grace_counted(env):
    with account_scope(env["account_id"]):
        _punch(env["emp"], 3, 8, 40, "p3")
        _punch(env["emp"], 3, 16, 0, "p4")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 3),
                                end_date=date(2026, 3, 3))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 3))
        assert d.late_minutes == 40


@pytest.mark.django_db(transaction=True)
def test_late_within_grace_ignored(env):
    """سماح 15 دقيقة — الحضور 08:10 لا يُحتسب تأخيرًا."""
    with account_scope(env["account_id"]):
        _punch(env["emp"], 4, 8, 10, "p5")
        _punch(env["emp"], 4, 16, 0, "p6")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 4),
                                end_date=date(2026, 3, 4))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 4))
        assert d.late_minutes == 0


@pytest.mark.django_db(transaction=True)
def test_overtime_computed(env):
    with account_scope(env["account_id"]):
        _punch(env["emp"], 5, 8, 0, "p7")
        _punch(env["emp"], 5, 19, 0, "p8")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 5),
                                end_date=date(2026, 3, 5))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 5))
        assert d.overtime_minutes == 180


@pytest.mark.django_db(transaction=True)
def test_absent_when_no_punches(env):
    """9 مارس 2026 = الاثنين — يوم عمل بلا بصمات = غياب."""
    with account_scope(env["account_id"]):
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 9),
                                end_date=date(2026, 3, 9))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 9))
        assert d.status == DayStatus.ABSENT


@pytest.mark.django_db(transaction=True)
def test_weekend_detected(env):
    """
    الترقيم السعودي: الأحد=0 … السبت=6.
    مع working_days=[0..4] (الأحد–الخميس) تكون العطلة الجمعة والسبت.
    6 مارس 2026 = الجمعة، و7 مارس = السبت.
    """
    with account_scope(env["account_id"]):
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 6),
                                end_date=date(2026, 3, 7))
        for day in (date(2026, 3, 6), date(2026, 3, 7)):
            d = AttendanceDay.objects.get(employment=env["emp"],
                                          work_date=day)
            assert d.status == DayStatus.WEEKEND


@pytest.mark.django_db(transaction=True)
def test_single_punch_is_partial(env):
    with account_scope(env["account_id"]):
        _punch(env["emp"], 9, 8, 0, "p9")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 9),
                                end_date=date(2026, 3, 9))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 9))
        assert d.status == DayStatus.PARTIAL
        assert d.punch_count == 1


# ══════════ البصمات الخام ══════════

@pytest.mark.django_db(transaction=True)
def test_duplicate_punch_ignored_silently(env):
    """الأجهزة تعيد الإرسال عند فشل الاتصال — التكرار يُتجاهل."""
    with account_scope(env["account_id"]):
        _, created1 = _punch(env["emp"], 2, 8, 0, "same-ref")
        _, created2 = _punch(env["emp"], 2, 8, 0, "same-ref")
        assert created1 is True
        assert created2 is False
        assert AttendancePunch.objects.filter(
            employment=env["emp"], external_ref="same-ref").count() == 1


@pytest.mark.django_db(transaction=True)
def test_reprocessing_does_not_lose_punches(env):
    """البصمات الخام لا تُمس — إعادة المعالجة تعيد البناء منها."""
    with account_scope(env["account_id"]):
        _punch(env["emp"], 2, 8, 0, "r1")
        _punch(env["emp"], 2, 16, 0, "r2")
        for _ in range(3):
            process_employment_days(employment=env["emp"],
                                    start_date=date(2026, 3, 2),
                                    end_date=date(2026, 3, 2))
        assert AttendancePunch.objects.filter(employment=env["emp"]).count() == 2
        assert AttendanceDay.objects.filter(employment=env["emp"]).count() == 1


# ══════════ الاعتماد والتعديل ══════════

@pytest.mark.django_db(transaction=True)
def test_overtime_requires_approval(env):
    """الإضافي لا يدخل المسير إلا بعد اعتماد صريح."""
    with account_scope(env["account_id"]):
        _punch(env["emp"], 5, 8, 0, "o1")
        _punch(env["emp"], 5, 19, 0, "o2")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 5),
                                end_date=date(2026, 3, 5))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 5))
        assert d.overtime_minutes == 180
        assert d.approved_overtime_minutes == 0

        approve_overtime(attendance_day=d, minutes=120,
                         approved_by_person=env["person"])
        d.refresh_from_db()
        assert d.approved_overtime_minutes == 120


@pytest.mark.django_db(transaction=True)
def test_cannot_approve_more_than_computed(env):
    with account_scope(env["account_id"]):
        _punch(env["emp"], 5, 8, 0, "o3")
        _punch(env["emp"], 5, 19, 0, "o4")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 5),
                                end_date=date(2026, 3, 5))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 5))
        with pytest.raises(AttendanceError):
            approve_overtime(attendance_day=d, minutes=999,
                             approved_by_person=env["person"])


@pytest.mark.django_db(transaction=True)
def test_manual_adjustment_survives_reprocessing(env):
    """التعديل اليدوي قرار بشري لا تمحوه إعادة المعالجة."""
    with account_scope(env["account_id"]):
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 9),
                                end_date=date(2026, 3, 9))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 9))
        adjust_day_manually(attendance_day=d, person=env["person"],
                            note="إذن شفهي", status=DayStatus.LEAVE)
        res = process_employment_days(employment=env["emp"],
                                      start_date=date(2026, 3, 9),
                                      end_date=date(2026, 3, 9))
        d.refresh_from_db()
        assert d.status == DayStatus.LEAVE
        assert res.days_skipped == 1


@pytest.mark.django_db(transaction=True)
def test_adjustment_requires_note(env):
    with account_scope(env["account_id"]):
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 9),
                                end_date=date(2026, 3, 9))
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=date(2026, 3, 9))
        with pytest.raises(AttendanceError):
            adjust_day_manually(attendance_day=d, person=env["person"],
                                note="  ", status=DayStatus.LEAVE)


# ══════════ الملخص الشهري ══════════

@pytest.mark.django_db(transaction=True)
def test_monthly_summary_aggregates(env):
    """محرك الرواتب يقرأ صفًا واحدًا لا 600 بصمة."""
    with account_scope(env["account_id"]):
        _punch(env["emp"], 2, 8, 0, "s1")
        _punch(env["emp"], 2, 16, 0, "s2")
        _punch(env["emp"], 3, 8, 40, "s3")
        _punch(env["emp"], 3, 16, 0, "s4")
        process_employment_days(employment=env["emp"],
                                start_date=date(2026, 3, 1),
                                end_date=date(2026, 3, 10))
        s = build_monthly_summary(employment=env["emp"], year=2026, month=3)
        assert s.late_minutes == 40
        assert s.worked_days > 0
        assert s.unpaid_absent_days > 0


# ══════════ العزل ══════════

@pytest.mark.django_db(transaction=True)
def test_attendance_isolated_between_accounts(env, rls_enforced_late):
    other = provision_account(slug="att-other", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(env["account_id"]):
        _punch(env["emp"], 2, 8, 0, "i1")
    rls_enforced_late()
    with account_scope(other.account_id):
        assert AttendancePunch.objects.count() == 0
        assert AttendanceDay.objects.count() == 0


@pytest.mark.django_db
def test_saudi_weekday_numbering():
    """
    حارس ترقيم الأيام: الأحد=0 … السبت=6.

    خطأ بيوم واحد هنا يجعل كل الحضور خاطئًا — الجمعة تصير يوم عمل
    والأحد عطلة. مثبَّت بتواريخ حقيقية.
    """
    cases = [
        (date(2026, 3, 8), 0, "الأحد"),
        (date(2026, 3, 2), 1, "الاثنين"),
        (date(2026, 3, 5), 4, "الخميس"),
        (date(2026, 3, 6), 5, "الجمعة"),
        (date(2026, 3, 7), 6, "السبت"),
    ]
    for d, expected, name in cases:
        actual = (d.weekday() + 1) % 7
        assert actual == expected, f"{name} {d} → {actual} بدل {expected}"
