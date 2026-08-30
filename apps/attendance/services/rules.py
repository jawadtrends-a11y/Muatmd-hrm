"""
قواعد احتساب الحضور اليومي.

═══════════════════════════════════════════════════════════════
قرار تصميمي مثبَّت (ق-13) — لا تُلغِه

الحضور المتداخل عبر شركات الحساب الواحد حالة صحيحة ومقصودة.
الشخص قد يعمل حضوريًا في شركة وعن بُعد في أخرى بساعات متداخلة.

ممنوع إضافة:
  • قيد تفرد يمنع حضورًا متزامنًا لنفس person_id
  • تحذير أو علامة أو تنبيه على التداخل
  • أي تحقق يربط سجل حضور بشركة بسجل حضور بشركة أخرى

سجلات الحضور مستقلة تمامًا لكل employment_id.
═══════════════════════════════════════════════════════════════

البصمات الخام لا تُمس. هذه الدوال تشتق السجل اليومي منها،
ويمكن إعادة البناء بالكامل عند تغيير أي سياسة.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.attendance.models import DayStatus


@dataclass(frozen=True)
class DayComputation:
    work_date: date
    status: str
    first_in: datetime | None
    last_out: datetime | None
    worked_minutes: int
    late_minutes: int
    early_out_minutes: int
    overtime_minutes: int
    punch_count: int
    notes: list = field(default_factory=list)


def _combine(day: date, t: time, tz=None):
    naive = datetime.combine(day, t)
    return timezone.make_aware(naive, tz or timezone.get_current_timezone())


def compute_day(*, work_date, punches, shift=None, is_holiday=False,
                is_on_leave=False):
    """
    يحتسب سجل يوم واحد من بصماته.

    punches: قائمة datetime مرتّبة تصاعديًا
    shift: الوردية السارية، أو None لو لا وردية مسندة
    """
    notes = []
    punches = sorted(punches)
    count = len(punches)

    if is_on_leave:
        return DayComputation(work_date, DayStatus.LEAVE, None, None,
                              0, 0, 0, 0, count, ["في إجازة"])
    if is_holiday:
        return DayComputation(work_date, DayStatus.HOLIDAY, None, None,
                              0, 0, 0, 0, count, ["عطلة"])

    if shift is None:
        status = DayStatus.PRESENT if punches else DayStatus.NOT_SCHEDULED
        worked = _worked_minutes(punches)
        return DayComputation(work_date, status,
                              punches[0] if punches else None,
                              punches[-1] if punches else None,
                              worked, 0, 0, 0, count,
                              ["لا وردية مسندة — لا يُحتسب تأخير"])

    # يوم راحة أسبوعية
    weekday = (work_date.weekday() + 1) % 7      # 0=الأحد
    if shift.working_days and weekday not in shift.working_days:
        if punches:
            worked = _worked_minutes(punches)
            return DayComputation(
                work_date, DayStatus.PRESENT, punches[0], punches[-1],
                worked, 0, 0, worked, count,
                ["عمل في يوم راحة — كامل الوقت إضافي"])
        return DayComputation(work_date, DayStatus.WEEKEND, None, None,
                              0, 0, 0, 0, 0, ["راحة أسبوعية"])

    if not punches:
        return DayComputation(work_date, DayStatus.ABSENT, None, None,
                              0, 0, 0, 0, 0, ["لا بصمات"])

    first_in, last_out = punches[0], punches[-1]
    if count == 1:
        notes.append("بصمة واحدة — لم يُسجَّل الانصراف")

    scheduled_start = _combine(work_date, shift.start_time)
    end_day = work_date + timedelta(days=1) if shift.crosses_midnight else work_date
    scheduled_end = _combine(end_day, shift.end_time)

    # الدوام المرن: يُحتسب بإجمالي الساعات لا بوقت الحضور
    if shift.is_flexible:
        worked = _worked_minutes(punches)
        expected = int((scheduled_end - scheduled_start).total_seconds() // 60) \
            - shift.break_minutes
        overtime = max(0, worked - expected)
        return DayComputation(work_date, DayStatus.PRESENT, first_in, last_out,
                              worked, 0, 0, overtime, count,
                              notes + ["دوام مرن"])

    late = max(0, int((first_in - scheduled_start).total_seconds() // 60))
    if late <= shift.grace_in_minutes:
        late = 0
    elif shift.grace_in_minutes:
        notes.append(f"تجاوز سماح التأخير ({shift.grace_in_minutes} دقيقة)")

    early_out = 0
    if count > 1:
        early_out = max(0, int((scheduled_end - last_out).total_seconds() // 60))
        if early_out <= shift.grace_out_minutes:
            early_out = 0

    worked = _worked_minutes(punches)
    if worked > shift.break_minutes:
        worked -= shift.break_minutes

    overtime = 0
    if count > 1 and last_out > scheduled_end:
        overtime = int((last_out - scheduled_end).total_seconds() // 60)

    status = DayStatus.PRESENT
    if count == 1 or (late and worked == 0):
        status = DayStatus.PARTIAL

    return DayComputation(work_date, status, first_in, last_out,
                          worked, late, early_out, overtime, count, notes)


def _worked_minutes(punches) -> int:
    """
    دقائق العمل = مجموع الفترات بين كل دخول وخروج متتاليين.
    البصمات الفردية (بلا مقابل) تُتجاهل.
    """
    if len(punches) < 2:
        return 0
    total = 0
    for i in range(0, len(punches) - 1, 2):
        total += int((punches[i + 1] - punches[i]).total_seconds() // 60)
    return total


def effective_shift(employment, work_date):
    """الوردية السارية بتاريخ معيّن — لا بتاريخ اليوم."""
    from apps.attendance.models import ShiftAssignment
    a = (ShiftAssignment.objects
         .filter(employment=employment, effective_from__lte=work_date)
         .filter(models_q_effective_to(work_date))
         .select_related("shift")
         .order_by("-effective_from").first())
    return a.shift if a else None


def models_q_effective_to(work_date):
    from django.db.models import Q
    return Q(effective_to__isnull=True) | Q(effective_to__gte=work_date)
