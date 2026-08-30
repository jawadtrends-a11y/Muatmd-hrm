"""
معالجة البصمات إلى سجلات يومية.

البصمات الخام لا تُمس. هذه الطبقة تشتق منها ويمكن إعادة البناء
بالكامل عند تغيير أي سياسة — لا فقدان للبيانات أبدًا.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.attendance.models import (
    AttendanceDay, AttendanceMonthlySummary, AttendancePunch, DayStatus,
)
from apps.attendance.services.rules import compute_day, effective_shift


class AttendanceError(Exception):
    pass


@dataclass
class ProcessResult:
    days_created: int = 0
    days_updated: int = 0
    days_skipped: int = 0
    punches_read: int = 0


@transaction.atomic
def record_punch(*, employment, punched_at, source, device_id="",
                 external_ref="", latitude=None, longitude=None,
                 raw_payload=None):
    """
    يسجّل بصمة خام.

    external_ref مفتاح فريد يمنع التكرار عند إعادة إرسال الجهاز —
    الأجهزة تعيد الإرسال عند فشل الاتصال.
    """
    if external_ref:
        existing = AttendancePunch.objects.filter(
            company=employment.company, external_ref=external_ref).first()
        if existing:
            return existing, False      # مكررة — تُتجاهل بصمت

    punch = AttendancePunch.objects.create(
        account=employment.account, company=employment.company,
        employment=employment, punched_at=punched_at, source=source,
        device_id=device_id, external_ref=external_ref,
        latitude=latitude, longitude=longitude,
        raw_payload=raw_payload or {},
    )
    return punch, True


def _holidays_in(company, start, end):
    from apps.organization.models import Holiday
    return {
        d
        for h in Holiday.objects.filter(
            company=company, start_date__lte=end, end_date__gte=start)
        for d in _date_range(max(h.start_date, start), min(h.end_date, end))
    }


def _date_range(start, end):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


@transaction.atomic
def process_employment_days(*, employment, start_date, end_date,
                            force=False):
    """
    يبني سجلات الحضور اليومية لفترة.

    force=False يتخطى الأيام المعدَّلة يدويًا — التعديل اليدوي قرار
    بشري لا يُمحى بإعادة المعالجة.
    """
    result = ProcessResult()
    holidays = _holidays_in(employment.company, start_date, end_date)

    punches = list(AttendancePunch.objects.filter(
        employment=employment,
        punched_at__date__gte=start_date,
        punched_at__date__lte=end_date,
    ).order_by("punched_at"))
    result.punches_read = len(punches)

    by_day = {}
    for p in punches:
        local = timezone.localtime(p.punched_at)
        by_day.setdefault(local.date(), []).append(p.punched_at)

    existing = {
        d.work_date: d
        for d in AttendanceDay.objects.filter(
            employment=employment, work_date__gte=start_date,
            work_date__lte=end_date)
    }

    for day in _date_range(start_date, end_date):
        current = existing.get(day)
        if current and current.is_manually_adjusted and not force:
            result.days_skipped += 1
            continue

        shift = effective_shift(employment, day)
        comp = compute_day(
            work_date=day, punches=by_day.get(day, []), shift=shift,
            is_holiday=day in holidays, is_on_leave=False)

        defaults = {
            "account": employment.account,
            "company": employment.company,
            "shift": shift,
            "first_in": comp.first_in,
            "last_out": comp.last_out,
            "worked_minutes": comp.worked_minutes,
            "late_minutes": comp.late_minutes,
            "early_out_minutes": comp.early_out_minutes,
            "overtime_minutes": comp.overtime_minutes,
            "status": comp.status,
            "punch_count": comp.punch_count,
            "computed_at": timezone.now(),
        }
        obj, created = AttendanceDay.objects.update_or_create(
            employment=employment, work_date=day, defaults=defaults)
        if created:
            result.days_created += 1
        else:
            result.days_updated += 1

    return result


@transaction.atomic
def build_monthly_summary(*, employment, year, month, payroll_settings=None):
    """
    يجمّع الشهر في صف واحد — محرك الرواتب يقرأه بدل 600 بصمة.

    شرط تحمّل ذروة الرواتب (الوثيقة المعمارية 2 القسم 3.6).
    """
    start = date(year, month, 1)
    end = (date(year + 1, 1, 1) if month == 12
           else date(year, month + 1, 1)) - timedelta(days=1)

    days = AttendanceDay.objects.filter(
        employment=employment, work_date__gte=start, work_date__lte=end)

    worked = sum(1 for d in days if d.status == DayStatus.PRESENT)
    partial = sum(Decimal("0.5") for d in days if d.status == DayStatus.PARTIAL)
    absent = sum(1 for d in days if d.status == DayStatus.ABSENT)
    leave = sum(1 for d in days if d.status == DayStatus.LEAVE)
    late = sum(d.late_minutes for d in days)
    overtime = sum(d.approved_overtime_minutes for d in days)

    summary, _ = AttendanceMonthlySummary.objects.update_or_create(
        employment=employment, period_year=year, period_month=month,
        defaults={
            "account": employment.account,
            "company": employment.company,
            "worked_days": Decimal(worked) + partial,
            "unpaid_absent_days": Decimal(absent),
            "paid_leave_days": Decimal(leave),
            "late_minutes": late,
            "approved_overtime_minutes": overtime,
            "computed_at": timezone.now(),
        },
    )
    return summary


@transaction.atomic
def approve_overtime(*, attendance_day, minutes, approved_by_person):
    """
    اعتماد العمل الإضافي — لا يدخل المسير إلا بعده.

    الفصل بين المحتسب والمعتمد يمنع دخول إضافي غير مأذون في الرواتب.
    """
    if minutes > attendance_day.overtime_minutes:
        raise AttendanceError(
            f"المعتمد ({minutes}) يتجاوز المحتسب "
            f"({attendance_day.overtime_minutes} دقيقة)")
    attendance_day.approved_overtime_minutes = minutes
    attendance_day.save(update_fields=["approved_overtime_minutes",
                                       "updated_at"])
    return attendance_day


@transaction.atomic
def adjust_day_manually(*, attendance_day, person, note, **fields):
    """
    تعديل يدوي — يُعلَّم ويُنسب لفاعله ولا تمحوه إعادة المعالجة.
    """
    if not note.strip():
        raise AttendanceError("سبب التعديل مطلوب")

    allowed = {"first_in", "last_out", "worked_minutes", "late_minutes",
               "early_out_minutes", "overtime_minutes", "status"}
    for key, value in fields.items():
        if key in allowed:
            setattr(attendance_day, key, value)

    attendance_day.is_manually_adjusted = True
    attendance_day.adjusted_by_person = person
    attendance_day.adjustment_note = note
    attendance_day.save()
    return attendance_day
