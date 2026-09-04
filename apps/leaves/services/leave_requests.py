"""
طلبات الإجازة — من التقديم إلى أثرها على الحضور والراتب.

قرار المالك (ق-32): يوم الإجازة لا يُحتسب غيابًا. والإجازة بلا أجر
تُخصم أجر اليوم فقط — الغياب مخالفة، والإجازة بلا أجر حق مأذون.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.leaves.models import (
    LeaveType, Request, RequestStatus, RequestType,
)
from apps.leaves.services.balances import (
    LeaveError, check_eligibility, compute_leave_days, consume,
)


@dataclass
class LeaveRequestResult:
    request: Request
    charged_days: Decimal
    end_date: date
    extended_days: int
    excluded: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def _next_request_no(company, prefix="LV"):
    year = date.today().year
    count = Request.objects.filter(
        company=company, request_no__startswith=f"{prefix}-{year}").count()
    return f"{prefix}-{year}-{count + 1:05d}"


@transaction.atomic
def create_leave_request(*, employment, leave_type_code, start_date,
                         requested_days, note="", attachment_url="",
                         channel="web", submit=True):
    """
    ينشئ طلب إجازة ويحتسب أثره.

    يفحص الأهلية أولًا، ثم يحتسب الأيام حسب سياسة النوع (ق-33)،
    ثم يرفعه لسلسلة الاعتماد.
    """
    company = employment.company
    leave_type = LeaveType.objects.filter(
        company=company, code=leave_type_code, is_active=True).first()
    if leave_type is None:
        raise LeaveError(f"نوع إجازة غير موجود: {leave_type_code}")

    errors = check_eligibility(employment, leave_type, start_date)
    if errors:
        raise LeaveError(" | ".join(errors))

    if leave_type.requires_attachment and not attachment_url:
        raise LeaveError(f"{leave_type.name_ar} تتطلب مرفقًا")

    if (leave_type.max_consecutive_days
            and Decimal(str(requested_days)) > leave_type.max_consecutive_days):
        raise LeaveError(
            f"أقصى مدة متصلة لـ{leave_type.name_ar}: "
            f"{leave_type.max_consecutive_days} يومًا")

    from apps.attendance.services.rules import effective_shift
    shift = effective_shift(employment, start_date)

    calc = compute_leave_days(
        company=company, leave_type=leave_type, start_date=start_date,
        requested_days=requested_days, shift=shift)

    overlap = _find_overlap(employment, start_date, calc.end_date)
    if overlap:
        raise LeaveError(
            f"تتداخل مع طلب قائم: {overlap.request_no} "
            f"({overlap.payload.get('start_date')} — "
            f"{overlap.payload.get('end_date')})")

    req = Request.objects.create(
        account=employment.account, company=company, employment=employment,
        request_no=_next_request_no(company),
        request_type=RequestType.LEAVE,
        note=note, attachment_url=attachment_url, channel=channel,
        payload={
            "leave_type": leave_type.code,
            "leave_type_name": leave_type.name_ar,
            "start_date": str(start_date),
            "end_date": str(calc.end_date),
            "days": str(calc.charged_days),
            "calendar_days": calc.calendar_days,
            "extended_days": calc.extended_days,
            "excluded": calc.excluded,
            "is_paid": leave_type.is_paid,
            "pay_percentage": str(leave_type.pay_percentage),
        },
    )

    warnings = []
    if not leave_type.is_paid:
        warnings.append(
            "إجازة بلا أجر — لا تُحتسب غيابًا لكن يُخصم أجر الأيام")

    if submit:
        from apps.leaves.services.approvals import submit_request
        req, _ = submit_request(req)

    return LeaveRequestResult(
        request=req, charged_days=calc.charged_days,
        end_date=calc.end_date, extended_days=calc.extended_days,
        excluded=calc.excluded, warnings=warnings)


def _find_overlap(employment, start, end):
    """يمنع تداخل إجازتين للموظف نفسه."""
    candidates = Request.objects.filter(
        employment=employment, request_type=RequestType.LEAVE,
        status__in=[RequestStatus.PENDING, RequestStatus.APPROVED])
    for r in candidates:
        try:
            r_start = date.fromisoformat(r.payload.get("start_date", ""))
            r_end = date.fromisoformat(r.payload.get("end_date", ""))
        except (ValueError, TypeError):
            continue
        if r_start <= end and r_end >= start:
            return r
    return None


@transaction.atomic
def apply_approved_leave(request_obj):
    """
    يطبّق الإجازة المعتمدة: يخصم الرصيد ويعلّم أيام الحضور.

    ق-32: يوم الإجازة يُعلَّم LEAVE لا ABSENT — الغياب مخالفة
    والإجازة حق مأذون. والإجازة بلا أجر تُخصم من الراتب لا من
    سجل الانضباط.
    """
    if request_obj.status != RequestStatus.APPROVED:
        raise LeaveError("الطلب غير معتمد")
    if request_obj.request_type != RequestType.LEAVE:
        raise LeaveError("ليس طلب إجازة")
    if request_obj.payload.get("applied"):
        return {"already_applied": True}

    payload = request_obj.payload
    employment = request_obj.employment
    leave_type = LeaveType.objects.get(
        company=request_obj.company, code=payload["leave_type"])
    start = date.fromisoformat(payload["start_date"])
    end = date.fromisoformat(payload["end_date"])
    days = Decimal(payload["days"])

    consume(employment, leave_type, days, year=start.year)

    marked = _mark_attendance_days(
        employment=employment, start=start, end=end,
        leave_type=leave_type, request_no=request_obj.request_no,
        excluded=payload.get("excluded", []))

    payload["applied"] = True
    payload["applied_at"] = timezone.now().isoformat()
    request_obj.payload = payload
    request_obj.save(update_fields=["payload", "updated_at"])

    out = {
        "consumed_days": str(days),
        "attendance_days_marked": marked,
        "is_paid": leave_type.is_paid,
        "pay_percentage": str(leave_type.pay_percentage),
        "note": ("إجازة بلا أجر — يُخصم أجر الأيام في المسير"
                 if not leave_type.is_paid else "إجازة مدفوعة"),
    }

    # ق-69: الإجازة المعتمدة بأثر رجعي — أيامها كانت محسوبة غيابًا
    retro = _retro_leave(request_obj, start, end, leave_type)
    if retro:
        out["retro"] = retro
    return out


def _retro_leave(request_obj, start, end, leave_type):
    """
    تسوية عن إجازة اعتُمدت بعد إغلاق مسير شهرها (ق-69).

    فأيامها كانت محسوبة غيابًا ومخصومة. والإجازة المدفوعة تردّ
    الخصم كاملًا، وغير المدفوعة لا تردّ شيئًا — فالخصم واقع في
    الحالين.
    """
    from apps.payroll.services.retro import (RetroSource, closed_run_for,
                                             record_adjustment)

    if not leave_type.is_paid:
        return None      # بلا أجر — الخصم قائم بحقّه

    run = closed_run_for(company=request_obj.company,
                         year=start.year, month=start.month)
    if run is None:
        return None      # المسير مفتوح — الاحتساب يأخذها

    # أيام الإجازة الواقعة في شهر المسير المغلق وحدها
    from apps.attendance.models import AttendanceDay, DayStatus
    absent_days = AttendanceDay.objects.filter(
        employment=request_obj.employment,
        work_date__gte=start, work_date__lte=end,
        work_date__year=start.year, work_date__month=start.month,
    ).count()
    if absent_days == 0:
        return None

    daily = _daily_wage_for(request_obj.employment)
    if daily is None:
        return None

    pct = (leave_type.pay_percentage or Decimal("100")) / Decimal("100")
    amount = (daily * Decimal(absent_days) * pct).quantize(Decimal("0.01"))

    adj = record_adjustment(
        employment=request_obj.employment,
        year=start.year, month=start.month,
        source=RetroSource.LEAVE,
        amount_before=Decimal("0"), amount_after=amount,
        reason_ar=(f"إجازة {leave_type.name_ar} بأثر رجعي — "
                   f"{absent_days} يومًا بطلب {request_obj.request_no}"),
        source_request=request_obj)
    return {"id": adj.id, "amount": str(adj.amount)} if adj else None


def _daily_wage_for(employment):
    """أجر اليوم من آخر هيكل راتب ساري."""
    from apps.employees.models import SalaryStructure

    st = (SalaryStructure.objects
          .filter(employment=employment, effective_to__isnull=True)
          .order_by("-effective_from").first())
    if st is None:
        return None
    return (st.gross_monthly or Decimal("0")) / Decimal("30")


def _mark_attendance_days(*, employment, start, end, leave_type,
                          request_no, excluded):
    """
    يعلّم أيام الحضور كإجازة.

    الأيام المستثناة (عطل مُمدَّدة) تبقى بحالتها — لأنها ليست
    إجازة بل امتداد لها.
    """
    from apps.attendance.models import AttendanceDay, DayStatus

    excluded_dates = {x.get("date") for x in (excluded or [])}
    marked = 0
    cur = start
    while cur <= end:
        if str(cur) not in excluded_dates:
            AttendanceDay.objects.update_or_create(
                employment=employment, work_date=cur,
                defaults={
                    "account": employment.account,
                    "company": employment.company,
                    "status": DayStatus.LEAVE,
                    "is_manually_adjusted": True,
                    "adjustment_note": (
                        f"إجازة {leave_type.name_ar} — الطلب {request_no}"
                        + ("" if leave_type.is_paid else " (بلا أجر)")),
                    "computed_at": timezone.now(),
                })
            marked += 1
        cur += timedelta(days=1)
    return marked


def unpaid_leave_days_in_period(employment, year, month):
    """
    أيام الإجازة بلا أجر في شهر — لخصمها في المسير.

    منفصلة عن أيام الغياب: الغياب مخالفة، والإجازة بلا أجر حق مأذون
    يُخصم أجره فقط (ق-32).
    """
    from calendar import monthrange
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])

    total = Decimal("0")
    for r in Request.objects.filter(
            employment=employment, request_type=RequestType.LEAVE,
            status=RequestStatus.APPROVED):
        if not r.payload.get("applied"):
            continue
        if r.payload.get("is_paid", True):
            continue
        try:
            r_start = date.fromisoformat(r.payload["start_date"])
            r_end = date.fromisoformat(r.payload["end_date"])
        except (KeyError, ValueError):
            continue
        overlap_start = max(r_start, start)
        overlap_end = min(r_end, end)
        if overlap_start <= overlap_end:
            excluded = {x.get("date") for x in r.payload.get("excluded", [])}
            cur = overlap_start
            while cur <= overlap_end:
                if str(cur) not in excluded:
                    total += 1
                cur += timedelta(days=1)
    return total
