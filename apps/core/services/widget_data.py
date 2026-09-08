"""
بيانات ودجتات اللوحة (ق-106).

لكل ودجت دالّة تُرجع dict بسيطًا — رقمًا أو قائمة قصيرة. والثقل
محسوب: اللوحة تُفتح كل صباح، فكل ودجت استعلامٌ أو اثنان لا أكثر.

وكلّها تمرّ بالبوابة: الودجت تعرض ما يراه صاحبها لا أكثر.
"""
from datetime import date, timedelta

from django.db.models import Count, Q

from apps.core.access.gate import Gate

BUILDERS = {}


def widget(key):
    def deco(fn):
        BUILDERS[key] = fn
        return fn
    return deco


def build(key, request):
    fn = BUILDERS.get(key)
    return fn(request) if fn else {"empty": True}


# ── مساعدات ──────────────────────────────────────────

def _person(request):
    return getattr(request.user, "person", None)


def _employment(request):
    from apps.employees.models import Employment, EmploymentStatus
    p = _person(request)
    if p is None:
        return None
    return Employment.objects.filter(
        person=p, status=EmploymentStatus.ACTIVE).first()


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


# ══════════ ما يخصّني ══════════

@widget("my_leave_balance")
def _my_leave_balance(request):
    from apps.leaves.models import LeaveBalance
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    rows = []
    for b in LeaveBalance.objects.filter(
            employment=emp).select_related("leave_type")[:4]:
        rows.append({"label": b.leave_type.name_ar,
                     "value": str(b.balance_days)})
    return {"kind": "stat_list", "rows": rows}


@widget("my_requests")
def _my_requests(request):
    from apps.leaves.models import Request, RequestStatus
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    # معزول ذاتيًا: مقيَّد بتوظيف المستخدم نفسه
    qs = Request.objects.filter(employment=emp).exclude(
        status__in=[RequestStatus.CANCELLED])
    pending = qs.filter(status=RequestStatus.PENDING).count()
    rows = [{"label": r.get_request_type_display(),
             "value": r.get_status_display(),
             "link": f"/me/requests"}
            for r in qs.order_by("-created_at")[:4]]
    return {"kind": "list_with_count", "count": pending, "rows": rows,
            "link": "/me/requests"}


@widget("my_attendance")
def _my_attendance(request):
    from apps.attendance.models import AttendanceDay, DayStatus
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    today = date.today()
    start = today.replace(day=1)
    # معزول ذاتيًا: مقيَّد بتوظيف المستخدم نفسه
    agg = AttendanceDay.objects.filter(
        employment=emp, work_date__gte=start, work_date__lte=today
    ).aggregate(
        present=Count("id", filter=Q(status=DayStatus.PRESENT)),
        absent=Count("id", filter=Q(status=DayStatus.ABSENT)),
        leave=Count("id", filter=Q(status=DayStatus.LEAVE)),
    )
    return {"kind": "stat_list", "rows": [
        {"label": "حضور", "value": agg["present"]},
        {"label": "غياب", "value": agg["absent"]},
        {"label": "إجازة", "value": agg["leave"]},
    ], "link": "/me/attendance"}


@widget("my_next_leave")
def _my_next_leave(request):
    from apps.leaves.services.leave_requests import leave_dates_in_range
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    today = date.today()
    days = leave_dates_in_range(emp, today, today + timedelta(days=180))
    if not days:
        return {"kind": "stat", "value": "—", "hint": "لا إجازة قادمة"}
    nxt = min(days)
    return {"kind": "stat", "value": str(nxt),
            "hint": f"بعد {(nxt - today).days} يومًا"}


@widget("my_documents")
def _my_documents(request):
    from apps.employees.models import EmployeeDocument
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    soon = date.today() + timedelta(days=60)
    # معزول ذاتيًا: مقيَّد بتوظيف المستخدم نفسه
    n = EmployeeDocument.objects.filter(
        employment=emp, expiry_date__isnull=False,
        expiry_date__lte=soon).count()
    return {"kind": "stat", "value": n, "hint": "خلال ٦٠ يومًا"}


@widget("my_last_payslip")
def _my_last_payslip(request):
    from apps.payroll.models import Payslip
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    # معزول ذاتيًا: مقيَّد بتوظيف المستخدم نفسه
    ps = Payslip.objects.filter(employment=emp).order_by("-id").first()
    if ps is None:
        return {"kind": "stat", "value": "—"}
    return {"kind": "stat", "value": str(ps.net_pay),
            "hint": "ريال", "link": "/me"}


# ══════════ ما ينتظر قراري ══════════

@widget("pending_approvals")
def _pending_approvals(request):
    from apps.leaves.services.approvals import pending_for
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    qs = pending_for(emp)
    rows = [{"label": r.get_request_type_display(),
             "value": r.employment.person.display_name}
            for r in qs.select_related("employment__person")[:5]]
    return {"kind": "list_with_count", "count": qs.count(), "rows": rows,
            "link": "/team/requests"}


@widget("overdue_approvals")
def _overdue_approvals(request):
    from django.utils import timezone

    from apps.leaves.services.approvals import pending_for
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    cutoff = timezone.now() - timedelta(days=2)
    n = pending_for(emp).filter(created_at__lt=cutoff).count()
    return {"kind": "stat", "value": n, "hint": "أكثر من يومين",
            "tone": "danger" if n else "muted", "link": "/team/requests"}


@widget("pending_delegations")
def _pending_delegations(request):
    from apps.leaves.models import Delegation, DelegationStatus
    emp = _employment(request)
    if emp is None:
        return {"empty": True}
    # معزول ذاتيًا: مقيَّد بالنائب نفسه
    n = Delegation.objects.filter(
        deputy=emp, status=DelegationStatus.PENDING).count()
    return {"kind": "stat", "value": n, "hint": "تنتظر قرارك"}


# ══════════ فريقي ══════════

def _team_employments(request, perm="attendance.view"):
    """مرؤوسوه — عبر البوابة، فنطاقه هو الحدّ."""
    from apps.employees.models import Employment, EmploymentStatus
    return Gate.filter_queryset(
        request.user, perm, Employment.objects.all()
    ).filter(company_id=_company_id(request),
             status=EmploymentStatus.ACTIVE)


@widget("team_today")
def _team_today(request):
    from apps.attendance.models import AttendanceDay, DayStatus
    team = _team_employments(request)
    total = team.count()
    if not total:
        return {"empty": True}
    agg = AttendanceDay.objects.filter(
        employment__in=team, work_date=date.today()
    ).aggregate(
        present=Count("id", filter=Q(status=DayStatus.PRESENT)),
        absent=Count("id", filter=Q(status=DayStatus.ABSENT)),
        leave=Count("id", filter=Q(status=DayStatus.LEAVE)),
    )
    return {"kind": "stat_list", "rows": [
        {"label": "حاضر", "value": agg["present"]},
        {"label": "غائب", "value": agg["absent"], "tone": "danger"},
        {"label": "إجازة", "value": agg["leave"]},
        {"label": "الإجمالي", "value": total},
    ], "link": "/team/attendance"}


@widget("team_absent")
def _team_absent(request):
    from apps.attendance.models import AttendanceDay, DayStatus
    team = _team_employments(request)
    n = AttendanceDay.objects.filter(
        employment__in=team, work_date=date.today(),
        status=DayStatus.ABSENT).count()
    return {"kind": "stat", "value": n, "tone": "danger" if n else "muted",
            "hint": "اليوم", "link": "/team/attendance"}


@widget("team_on_leave")
def _team_on_leave(request):
    from apps.leaves.services.leave_requests import leave_dates_in_range
    today = date.today()
    rows = []
    for e in _team_employments(request, "leaves.view").select_related(
            "person")[:100]:
        if leave_dates_in_range(e, today, today):
            rows.append({"label": e.person.display_name, "value": "في إجازة"})
    return {"kind": "list_with_count", "count": len(rows),
            "rows": rows[:5], "link": "/team/requests"}


@widget("team_upcoming_leaves")
def _team_upcoming_leaves(request):
    from apps.leaves.services.leave_requests import leave_dates_in_range
    today = date.today()
    horizon = today + timedelta(days=30)
    rows = []
    for e in _team_employments(request, "leaves.view").select_related(
            "person")[:100]:
        days = leave_dates_in_range(e, today + timedelta(days=1), horizon)
        if days:
            rows.append({"label": e.person.display_name,
                         "value": str(min(days))})
    rows.sort(key=lambda r: r["value"])
    return {"kind": "list_with_count", "count": len(rows), "rows": rows[:5],
            "hint": "خلال ٣٠ يومًا"}


@widget("team_late")
def _team_late(request):
    from apps.attendance.models import AttendanceDay
    from django.db.models import Sum
    team = _team_employments(request)
    start = date.today().replace(day=1)
    agg = AttendanceDay.objects.filter(
        employment__in=team, work_date__gte=start,
        late_minutes__gt=0).aggregate(n=Count("id"), m=Sum("late_minutes"))
    return {"kind": "stat_list", "rows": [
        {"label": "مرّات التأخّر", "value": agg["n"] or 0},
        {"label": "مجموع الدقائق", "value": agg["m"] or 0},
    ]}


# ══════════ المنشأة ══════════

def _company_employments(request, perm="employees.view_all"):
    from apps.employees.models import Employment, EmploymentStatus
    return Gate.filter_queryset(
        request.user, perm, Employment.objects.all()
    ).filter(company_id=_company_id(request),
             status=EmploymentStatus.ACTIVE)


@widget("headcount")
def _headcount(request):
    return {"kind": "stat", "value": _company_employments(request).count(),
            "hint": "موظفًا نشطًا", "link": "/employees"}


@widget("new_hires")
def _new_hires(request):
    since = date.today() - timedelta(days=30)
    qs = _company_employments(request).filter(
        join_date__gte=since).select_related("person").order_by("-join_date")
    rows = [{"label": e.person.display_name, "value": str(e.join_date)}
            for e in qs[:5]]
    return {"kind": "list_with_count", "count": qs.count(), "rows": rows,
            "hint": "خلال ٣٠ يومًا", "link": "/employees"}


@widget("attendance_today")
def _attendance_today(request):
    from apps.attendance.models import AttendanceDay, DayStatus
    team = _company_employments(request, "attendance.view_all")
    total = team.count()
    agg = AttendanceDay.objects.filter(
        employment__in=team, work_date=date.today()
    ).aggregate(
        present=Count("id", filter=Q(status=DayStatus.PRESENT)),
        absent=Count("id", filter=Q(status=DayStatus.ABSENT)),
        leave=Count("id", filter=Q(status=DayStatus.LEAVE)),
    )
    return {"kind": "stat_list", "rows": [
        {"label": "حاضر", "value": agg["present"]},
        {"label": "غائب", "value": agg["absent"], "tone": "danger"},
        {"label": "إجازة", "value": agg["leave"]},
        {"label": "الإجمالي", "value": total},
    ], "link": "/attendance"}


@widget("expiring_documents")
def _expiring_documents(request):
    from apps.employees.models import EmployeeDocument
    soon = date.today() + timedelta(days=60)
    emps = _company_employments(request)
    qs = EmployeeDocument.objects.filter(
        employment__in=emps, expiry_date__isnull=False,
        expiry_date__lte=soon).select_related(
            "employment__person").order_by("expiry_date")
    rows = [{"label": d.employment.person.display_name,
             "value": str(d.expiry_date)} for d in qs[:5]]
    return {"kind": "list_with_count", "count": qs.count(), "rows": rows,
            "hint": "خلال ٦٠ يومًا", "tone": "warn"}


@widget("expiring_iqama")
def _expiring_iqama(request):
    from apps.employees.models import Person
    soon = date.today() + timedelta(days=60)
    people = _company_employments(request).values_list("person_id", flat=True)
    qs = Person.objects.filter(
        id__in=people, id_type="iqama", id_expiry_date__isnull=False,
        id_expiry_date__lte=soon).order_by("id_expiry_date")
    rows = [{"label": p.display_name, "value": str(p.id_expiry_date)}
            for p in qs[:5]]
    return {"kind": "list_with_count", "count": qs.count(), "rows": rows,
            "hint": "خلال ٦٠ يومًا", "tone": "warn"}


@widget("headcount_by_dept")
def _headcount_by_dept(request):
    qs = _company_employments(request).values(
        "department__name_ar").annotate(n=Count("id")).order_by("-n")
    rows = [{"label": r["department__name_ar"] or "بلا إدارة",
             "value": r["n"]} for r in qs[:6]]
    return {"kind": "bar_list", "rows": rows}


@widget("nationalities")
def _nationalities(request):
    qs = _company_employments(request).values(
        "person__nationality_code").annotate(n=Count("id")).order_by("-n")
    rows = [{"label": r["person__nationality_code"] or "—", "value": r["n"]}
            for r in qs[:6]]
    return {"kind": "bar_list", "rows": rows}


@widget("terminations")
def _terminations(request):
    from apps.employees.models import Employment, EmploymentStatus
    start = date.today().replace(day=1)
    n = Gate.filter_queryset(
        request.user, "employees.view_all", Employment.objects.all()
    ).filter(company_id=_company_id(request),
             status=EmploymentStatus.TERMINATED,
             end_date__gte=start).count()
    return {"kind": "stat", "value": n, "hint": "هذا الشهر"}


@widget("leave_liability")
def _leave_liability(request):
    from django.db.models import Sum

    from apps.leaves.models import LeaveBalance
    people = _company_employments(request, "leaves.view_all")
    agg = LeaveBalance.objects.filter(
        employment__in=people).aggregate(d=Sum("balance_days"))
    return {"kind": "stat", "value": str(agg["d"] or 0),
            "hint": "يوم مستحقّ"}


@widget("absence_rate")
def _absence_rate(request):
    from apps.attendance.models import AttendanceDay, DayStatus
    team = _company_employments(request, "attendance.view_all")
    start = date.today().replace(day=1)
    days = AttendanceDay.objects.filter(
        employment__in=team, work_date__gte=start)
    total = days.count()
    absent = days.filter(status=DayStatus.ABSENT).count()
    pct = round(absent * 100 / total, 1) if total else 0
    return {"kind": "stat", "value": f"{pct}%",
            "hint": f"{absent} من {total} يوم",
            "tone": "danger" if pct > 5 else "muted"}


@widget("overtime_summary")
def _overtime_summary(request):
    from django.db.models import Sum

    from apps.attendance.models import AttendanceDay
    team = _company_employments(request, "attendance.view_all")
    start = date.today().replace(day=1)
    agg = AttendanceDay.objects.filter(
        employment__in=team, work_date__gte=start
    ).aggregate(m=Sum("approved_overtime_minutes"))
    hours = round((agg["m"] or 0) / 60, 1)
    return {"kind": "stat", "value": hours, "hint": "ساعة معتمدة"}


# ══════════ الرواتب ══════════

@widget("payroll_status")
def _payroll_status(request):
    from apps.payroll.models import PayrollRun
    qs = Gate.filter_queryset(
        request.user, "payroll.view", PayrollRun.objects.all()
    ).filter(company_id=_company_id(request)).order_by("-id")
    run = qs.first()
    if run is None:
        return {"kind": "stat", "value": "—", "hint": "لا مسير بعد"}
    return {"kind": "stat_list", "rows": [
        {"label": "الفترة", "value": f"{run.period_month}/{run.period_year}"},
        {"label": "الحالة", "value": run.get_status_display()},
        {"label": "الصافي", "value": str(run.total_net)},
    ], "link": "/payroll"}


@widget("payroll_net_trend")
def _payroll_net_trend(request):
    from apps.payroll.models import PayrollRun
    qs = Gate.filter_queryset(
        request.user, "payroll.view", PayrollRun.objects.all()
    ).filter(company_id=_company_id(request)).order_by("-id")[:6]
    rows = [{"label": f"{r.period_month}/{r.period_year}",
             "value": float(r.total_net or 0)} for r in reversed(list(qs))]
    return {"kind": "bar_list", "rows": rows, "link": "/payroll"}


@widget("payroll_by_dept")
def _payroll_by_dept(request):
    from django.db.models import Sum

    from apps.payroll.models import Payslip
    qs = Gate.filter_queryset(
        request.user, "payroll.view", Payslip.objects.all()
    ).values("employment__department__name_ar").annotate(
        s=Sum("net_pay")).order_by("-s")
    rows = [{"label": r["employment__department__name_ar"] or "بلا إدارة",
             "value": float(r["s"] or 0)} for r in qs[:6]]
    return {"kind": "bar_list", "rows": rows}


@widget("eosb_liability")
def _eosb_liability(request):
    return {"kind": "stat", "value": "—", "hint": "قيد الإعداد"}


@widget("advances_outstanding")
def _advances_outstanding(request):
    return {"kind": "stat", "value": "—", "hint": "قيد الإعداد"}
