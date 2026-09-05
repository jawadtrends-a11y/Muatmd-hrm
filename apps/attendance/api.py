"""
API الحضور والانصراف.

⚠️ ق-13: ممنوع إضافة أي تحقق تداخل عبر الشركات هنا أو في أي طبقة.
الحضور المتداخل حالة صحيحة — راجع apps/attendance/services/rules.py
"""
from datetime import date, datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.attendance.models import (
    AttendanceDay, AttendanceMonthlySummary, AttendancePunch, Shift,
    ShiftAssignment,
)
from apps.attendance.services.processing import (
    AttendanceError, adjust_day_manually, approve_overtime,
    build_monthly_summary, process_employment_days, record_punch,
)
from apps.core.access.gate import Gate
from apps.employees.models import Employment


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _my_employment(request):
    """
    الارتباط الوظيفي للمستخدم الحالي — للخدمة الذاتية.

    مقيّد بـperson المرتبط بالمستخدم، فلا حاجة لـGate: المستخدم
    يبحث عن نفسه لا عن غيره.
    """
    from apps.employees.models import Employment, EmploymentStatus
    person = getattr(request.user, "person", None)
    if person is None:
        return None
    return Employment.objects.filter(
        person=person, company_id=_company_id(request),
        status=EmploymentStatus.ACTIVE).first()


def _get_employment(request, employment_id, permission):
    qs = Gate.filter_queryset(request.user, permission,
                              Employment.objects.all())
    return qs.filter(id=employment_id,
                     company_id=_company_id(request)).first()


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def shifts(request):
    """الورديات."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "attendance.view")
        qs = Gate.filter_queryset(request.user, "attendance.view",
                                  Shift.objects.all())
        return Response([
            {"id": s.id, "code": s.code, "name_ar": s.name_ar,
             "start_time": s.start_time, "end_time": s.end_time,
             "break_minutes": s.break_minutes,
             "grace_in_minutes": s.grace_in_minutes,
             "grace_out_minutes": s.grace_out_minutes,
             "working_days": s.working_days,
             "crosses_midnight": s.crosses_midnight,
             "is_flexible": s.is_flexible, "is_active": s.is_active}
            for s in qs.filter(company_id=company_id)
        ])

    Gate.require(request.user, "attendance.shifts")
    from apps.accounts.models import Company
    comp = Gate.filter_queryset(
        request.user, "company.view", Company.objects.all()
    ).filter(id=company_id).first()

    existing = Gate.filter_queryset(request.user, "attendance.shifts",
                                    Shift.objects.all())
    code = (request.data.get("code") or "").strip().upper()
    if existing.filter(company_id=company_id, code=code).exists():
        return Response({"detail": f"الرمز مستخدم: {code}"}, status=409)

    s = Shift.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=request.data.get("name_ar", ""),
        start_time=request.data.get("start_time", "08:00"),
        end_time=request.data.get("end_time", "16:00"),
        break_minutes=int(request.data.get("break_minutes", 60)),
        grace_in_minutes=int(request.data.get("grace_in_minutes", 0)),
        grace_out_minutes=int(request.data.get("grace_out_minutes", 0)),
        working_days=request.data.get("working_days", [0, 1, 2, 3, 4]),
        crosses_midnight=bool(request.data.get("crosses_midnight", False)),
        is_flexible=bool(request.data.get("is_flexible", False)),
    )
    return Response({"id": s.id, "code": s.code}, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def punch(request):
    """
    تسجيل بصمة خام.

    external_ref يمنع التكرار عند إعادة إرسال الجهاز — الأجهزة
    تعيد الإرسال عند فشل الاتصال.
    """
    Gate.require(request.user, "attendance.view")
    emp = _get_employment(request, request.data.get("employment_id"),
                          "attendance.view")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    raw = request.data.get("punched_at")
    if not raw:
        when = timezone.now()
    else:
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return Response(
                {"detail": "صيغة الوقت غير صحيحة — استخدم ISO 8601"},
                status=400)
        # الوقت قد يصل بمنطقة زمنية أو بدونها — نتعامل مع الحالتين
        when = parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)

    p, created = record_punch(
        employment=emp, punched_at=when,
        source=request.data.get("source", "web"),
        device_id=request.data.get("device_id", ""),
        external_ref=request.data.get("external_ref", ""),
        latitude=request.data.get("latitude"),
        longitude=request.data.get("longitude"),
        raw_payload=request.data.get("raw_payload"),
    )
    return Response(
        {"id": p.id, "punched_at": p.punched_at, "created": created,
         "note": None if created else "بصمة مكررة — تُتجاهل"},
        status=201 if created else 200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def punches(request, employment_id):
    """
    البصمات الخام — للقراءة فقط.
    لا تُعدَّل ولا تُحذف: هي مصدر الحقيقة.
    """
    Gate.require(request.user, "attendance.view")
    emp = _get_employment(request, employment_id, "attendance.view")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    qs = Gate.filter_queryset(request.user, "attendance.view",
                              AttendancePunch.objects.all()
                              ).filter(employment=emp)
    if request.GET.get("from"):
        qs = qs.filter(punched_at__date__gte=request.GET["from"])
    if request.GET.get("to"):
        qs = qs.filter(punched_at__date__lte=request.GET["to"])

    return Response([
        {"id": p.id, "punched_at": p.punched_at, "source": p.source,
         "device_id": p.device_id, "external_ref": p.external_ref}
        for p in qs.order_by("punched_at")[:500]
    ])


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def attendance_days(request, employment_id):
    """السجلات اليومية، وإعادة المعالجة."""
    perm = ("attendance.view" if request.method == "GET"
            else "attendance.edit")
    Gate.require(request.user, perm)
    emp = _get_employment(request, employment_id, perm)
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    if request.method == "POST":
        try:
            res = process_employment_days(
                employment=emp,
                start_date=date.fromisoformat(request.data["from"]),
                end_date=date.fromisoformat(request.data["to"]),
                force=bool(request.data.get("force")))
        except (KeyError, ValueError) as e:
            return Response({"detail": f"تواريخ غير صالحة: {e}"}, status=400)
        return Response({
            "punches_read": res.punches_read,
            "days_created": res.days_created,
            "days_updated": res.days_updated,
            "days_skipped": res.days_skipped,
            "note": "الأيام المعدَّلة يدويًا تُتخطى إلا بـforce",
        })

    qs = Gate.filter_queryset(request.user, perm,
                              AttendanceDay.objects.all()
                              ).filter(employment=emp)
    if request.GET.get("from"):
        qs = qs.filter(work_date__gte=request.GET["from"])
    if request.GET.get("to"):
        qs = qs.filter(work_date__lte=request.GET["to"])

    # السجل متاح كاملًا من تاريخ الالتحاق ولو كان قبل عشرين سنة —
    # لكن لا يُجلب كاملًا في رد واحد: سبعة آلاف يوم تخنق المتصفح.
    # فالأحدث أولًا (وهو المطلوب غالبًا) بصفحات.
    qs = qs.order_by("-work_date")
    page, page_size = _page_params(request)
    total = qs.count()
    pages = max(1, -(-total // page_size))
    page = min(page, pages)

    rows = [
        {"id": d.id, "work_date": d.work_date, "status": d.status,
         "status_label": d.get_status_display(),
         "first_in": d.first_in, "last_out": d.last_out,
         "worked_minutes": d.worked_minutes,
         "late_minutes": d.late_minutes,
         "early_out_minutes": d.early_out_minutes,
         "overtime_minutes": d.overtime_minutes,
         "approved_overtime_minutes": d.approved_overtime_minutes,
         "punch_count": d.punch_count,
         "is_manually_adjusted": d.is_manually_adjusted,
         "adjustment_note": d.adjustment_note}
        for d in qs[(page - 1) * page_size: page * page_size]
    ]

    return Response({
        "employment_id": emp.id,
        "employee_no": emp.employee_no,
        "name_ar": emp.person.display_name,
        "join_date": emp.join_date,
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
        "rows": rows,
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def approve_day_overtime(request, day_id):
    """
    اعتماد العمل الإضافي — لا يدخل المسير إلا بعده.
    """
    Gate.require(request.user, "attendance.approve")
    qs = Gate.filter_queryset(request.user, "attendance.approve",
                              AttendanceDay.objects.all())
    day = qs.filter(id=day_id, company_id=_company_id(request)).first()
    if day is None:
        return Response({"detail": "السجل غير موجود"}, status=404)

    person = getattr(request.user, "person", None)
    try:
        approve_overtime(attendance_day=day,
                         minutes=int(request.data.get("minutes", 0)),
                         approved_by_person=person)
    except AttendanceError as e:
        return Response({"detail": str(e)}, status=400)
    except (TypeError, ValueError):
        return Response({"detail": "عدد الدقائق غير صالح"}, status=400)

    day.refresh_from_db()
    return Response({"id": day.id,
                     "overtime_minutes": day.overtime_minutes,
                     "approved_overtime_minutes":
                         day.approved_overtime_minutes})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def adjust_day(request, day_id):
    """
    تعديل يدوي — يُعلَّم ويُنسب لفاعله ولا تمحوه إعادة المعالجة.
    """
    Gate.require(request.user, "attendance.edit")
    qs = Gate.filter_queryset(request.user, "attendance.edit",
                              AttendanceDay.objects.all())
    day = qs.filter(id=day_id, company_id=_company_id(request)).first()
    if day is None:
        return Response({"detail": "السجل غير موجود"}, status=404)

    person = getattr(request.user, "person", None)
    fields = {k: v for k, v in request.data.items()
              if k in {"first_in", "last_out", "worked_minutes",
                       "late_minutes", "early_out_minutes",
                       "overtime_minutes", "status"}}
    try:
        adjust_day_manually(attendance_day=day, person=person,
                            note=request.data.get("note", ""), **fields)
    except AttendanceError as e:
        return Response({"detail": str(e)}, status=400)

    day.refresh_from_db()
    return Response({"id": day.id, "status": day.status,
                     "is_manually_adjusted": day.is_manually_adjusted,
                     "adjustment_note": day.adjustment_note})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def monthly_summary(request, employment_id):
    """
    الملخص الشهري — محرك الرواتب يقرأ صفًا واحدًا لا 600 بصمة.
    """
    perm = ("attendance.view" if request.method == "GET"
            else "attendance.edit")
    Gate.require(request.user, perm)
    emp = _get_employment(request, employment_id, perm)
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    try:
        year = int(request.data.get("year") or request.GET.get("year"))
        month = int(request.data.get("month") or request.GET.get("month"))
    except (TypeError, ValueError):
        return Response({"detail": "السنة والشهر مطلوبان"}, status=400)

    if request.method == "POST":
        s = build_monthly_summary(employment=emp, year=year, month=month)
    else:
        s = Gate.filter_queryset(
            request.user, perm, AttendanceMonthlySummary.objects.all()
        ).filter(employment=emp, period_year=year,
                 period_month=month).first()
        if s is None:
            return Response({"detail": "لا ملخص لهذه الفترة"}, status=404)

    return Response({
        "period": f"{year}-{month:02d}",
        "worked_days": str(s.worked_days),
        "unpaid_absent_days": str(s.unpaid_absent_days),
        "paid_leave_days": str(s.paid_leave_days),
        "late_minutes": s.late_minutes,
        "approved_overtime_minutes": s.approved_overtime_minutes,
        "is_final": s.is_final,
    })


# ══════════════════ العرض الجماعي ══════════════════

def _page_params(request, default_size=20, max_size=200):
    """
    معاملات التقسيم — page وpage_size.

    عشرون سجلًا في الصفحة (عشرة موظفين بدخولهم وخروجهم). والقراءة
    تبقى ثابتة الكلفة مهما بلغ عدد الموظفين، فلا يثقل النظام عند
    التوسّع.
    """
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except ValueError:
        page = 1
    try:
        size = int(request.GET.get("page_size") or default_size)
    except ValueError:
        size = default_size
    return page, max(1, min(size, max_size))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def daily_board(request):
    """
    حضور يوم واحد لكل الموظفين — ما يفتحه مدير الموارد كل صباح.

    من حضر، ومن تأخر، ومن غاب، ومن في إجازة.
    """
    from apps.attendance.models import AttendanceDay
    from apps.employees.models import Employment, EmploymentStatus

    Gate.require(request.user, "attendance.view")
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    try:
        day = (date.fromisoformat(request.GET["date"])
               if request.GET.get("date") else date.today())
    except ValueError:
        return Response({"detail": "تاريخ غير صالح"}, status=400)

    days = {
        d.employment_id: d
        for d in Gate.filter_queryset(
            request.user, "attendance.view", AttendanceDay.objects.all()
        ).filter(company_id=company_id, work_date=day)
    }

    employments = Gate.filter_queryset(
        request.user, "attendance.view", Employment.objects.all()
    ).filter(company_id=company_id,
             status=EmploymentStatus.ACTIVE).select_related(
        "person", "department").order_by("employee_no")

    page, page_size = _page_params(request)
    total = employments.count()
    pages = max(1, -(-total // page_size))
    page = min(page, pages)

    # العدّاد يشمل كل موظفي الشركة لا الصفحة المعروضة — «حاضر 40»
    # تعني الشركة كلها، وإلا كان الرقم مضلّلًا
    from django.db.models import Count as _Count
    counts = {
        r["status"]: r["n"]
        for r in Gate.filter_queryset(
            request.user, "attendance.view", AttendanceDay.objects.all()
        ).filter(
            id__in=[d.id for d in days.values()]
        ).values("status").annotate(n=_Count("id"))
    }
    no_record = total - sum(counts.values())
    if no_record > 0:
        counts["no_record"] = no_record

    rows = []
    for emp in employments[(page - 1) * page_size: page * page_size]:
        d = days.get(emp.id)
        status = d.status if d else "no_record"
        rows.append({
            "employment_id": emp.id,
            "employee_no": emp.employee_no,
            "name_ar": emp.person.display_name,
            "department": emp.department.name_ar if emp.department else "",
            "status": status,
            "status_label": d.get_status_display() if d else "لا سجل",
            "first_in": (timezone.localtime(d.first_in).strftime("%H:%M")
                         if d and d.first_in else ""),
            "last_out": (timezone.localtime(d.last_out).strftime("%H:%M")
                         if d and d.last_out else ""),
            "late_minutes": d.late_minutes if d else 0,
            "worked_minutes": d.worked_minutes if d else 0,
            "overtime_minutes": d.overtime_minutes if d else 0,
            "approved_overtime": d.approved_overtime_minutes if d else 0,
            "day_id": d.id if d else None,
        })

    return Response({
        "date": str(day),
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
        "counts": counts,
        "rows": rows,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monthly_board(request):
    """
    ملخص الحضور الشهري — يُحتسب لحظيًا من سجلات الأيام.

    لا يُقرأ من جدول ملخّص مُخزَّن: المدير يدخل في منتصف يوم العمل
    فيجب أن يرى بصمة اليوم فورًا لا بعد مهمة ليلية. والجمع يتم في
    القاعدة على صفحة واحدة، فتبقى الكلفة ثابتة مهما كبر الحساب.

    والاستثناء: الشهر الذي اعتُمد مسيره له صف نهائي في
    AttendanceMonthlySummary فيُقرأ منه — فلا تتغيّر أرقام مسير
    معتمد بأثر رجعي لو صُحّحت بصمة بعده (ق-69).
    """
    from calendar import monthrange

    from django.db.models import Count, Q, Sum

    from apps.attendance.models import AttendanceDay, AttendanceMonthlySummary
    from apps.employees.models import Employment, EmploymentStatus

    Gate.require(request.user, "attendance.view")
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    try:
        year = int(request.GET.get("year") or date.today().year)
        month = int(request.GET.get("month") or date.today().month)
    except ValueError:
        return Response({"detail": "سنة أو شهر غير صالح"}, status=400)
    if not 1 <= month <= 12:
        return Response({"detail": "الشهر بين 1 و12"}, status=400)

    employments = Gate.filter_queryset(
        request.user, "attendance.view", Employment.objects.all()
    ).filter(company_id=company_id,
             status=EmploymentStatus.ACTIVE).select_related(
        "person", "department").order_by("employee_no")

    page, page_size = _page_params(request)
    total = employments.count()
    pages = max(1, -(-total // page_size))
    page = min(page, pages)
    window = list(employments[(page - 1) * page_size: page * page_size])
    emp_ids = [e.id for e in window]

    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])

    frozen = {
        f.employment_id: f
        for f in Gate.filter_queryset(
            request.user, "attendance.view",
            AttendanceMonthlySummary.objects.all()
        ).filter(
            company_id=company_id, period_year=year, period_month=month,
            employment_id__in=emp_ids, is_final=True)
    }

    live = {
        r["employment_id"]: r
        for r in Gate.filter_queryset(
            request.user, "attendance.view", AttendanceDay.objects.all()
        ).filter(
            company_id=company_id, employment_id__in=emp_ids,
            work_date__gte=first, work_date__lte=last,
        ).values("employment_id").annotate(
            worked=Count("id", filter=Q(status__in=["present", "partial"])),
            absent=Count("id", filter=Q(status="absent")),
            leave=Count("id", filter=Q(status="leave")),
            late=Sum("late_minutes"),
            overtime=Sum("approved_overtime_minutes"),
        )
    }

    rows = []
    for emp in window:
        f = frozen.get(emp.id)
        if f is not None:
            worked, absent, leave = (str(f.worked_days),
                                     str(f.unpaid_absent_days),
                                     str(f.paid_leave_days))
            late, overtime = f.late_minutes, f.approved_overtime_minutes
        else:
            d = live.get(emp.id, {})
            worked = str(d.get("worked", 0))
            absent = str(d.get("absent", 0))
            leave = str(d.get("leave", 0))
            late = d.get("late") or 0
            overtime = d.get("overtime") or 0

        rows.append({
            "employment_id": emp.id,
            "employee_no": emp.employee_no,
            "name_ar": emp.person.display_name,
            "department": emp.department.name_ar if emp.department else "",
            "worked_days": worked,
            "absent_days": absent,
            "leave_days": leave,
            "late_minutes": late,
            "overtime_minutes": overtime,
            "overtime_hours": f"{overtime / 60:.2f}",
            "is_final": f is not None,
        })

    return Response({
        "year": year, "month": month,
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
        "rows": rows,
    })


# ══════════════════ حضوري (ق-58) ══════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_attendance(request):
    """
    سجل حضور الموظف نفسه — بلا صلاحية إدارية.

    ق-58: الموظف يرى حضوره هو، لا حضور زملائه.
    """
    from datetime import date

    from apps.attendance.models import AttendanceDay
    from apps.employees.models import Employment, EmploymentStatus

    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    emp = Employment.objects.filter(
        person=person, company_id=_company_id(request),
        status=EmploymentStatus.ACTIVE).first()
    if emp is None:
        emp = Employment.objects.filter(person=person).first()
    if emp is None:
        return Response({"detail": "لا ارتباط وظيفي"}, status=404)

    try:
        year = int(request.GET.get("year") or date.today().year)
        month = int(request.GET.get("month") or date.today().month)
    except ValueError:
        return Response({"detail": "سنة أو شهر غير صالح"}, status=400)

    days = AttendanceDay.objects.filter(
        employment=emp, work_date__year=year, work_date__month=month
    ).order_by("work_date")

    rows = []
    totals = {"present": 0, "absent": 0, "leave": 0, "weekend": 0,
              "late_minutes": 0, "worked_minutes": 0,
              "overtime_minutes": 0, "approved_overtime": 0}

    for d in days:
        totals[d.status] = totals.get(d.status, 0) + 1
        totals["late_minutes"] += d.late_minutes or 0
        totals["worked_minutes"] += d.worked_minutes or 0
        totals["overtime_minutes"] += d.overtime_minutes or 0
        totals["approved_overtime"] += d.approved_overtime_minutes or 0

        rows.append({
            "date": d.work_date,
            "status": d.status,
            "status_label": d.get_status_display(),
            "first_in": (timezone.localtime(d.first_in).strftime("%H:%M")
                         if d.first_in else ""),
            "last_out": (timezone.localtime(d.last_out).strftime("%H:%M")
                         if d.last_out else ""),
            "late_minutes": d.late_minutes or 0,
            "worked_minutes": d.worked_minutes or 0,
            "overtime_minutes": d.overtime_minutes or 0,
            "approved_overtime": d.approved_overtime_minutes or 0,
            "adjusted": d.is_manually_adjusted,
            "note": d.adjustment_note or "",
        })

    return Response({
        "employee_no": emp.employee_no,
        "year": year,
        "month": month,
        "totals": {
            **totals,
            "worked_hours": f"{totals['worked_minutes'] / 60:.1f}",
            "overtime_hours": f"{totals['approved_overtime'] / 60:.1f}",
        },
        "days": rows,
    })


# ══════════════════ مواقع العمل والبصمة (ق-62) ══════════════════

def _coord(value):
    """
    إحداثي بسبع خانات عشرية — كما يقبل النموذج.

    الخريطة تعطي دقة أعلى (21.55544190123)، والمستخدم لم يكتبها
    بيده. فالخادم يقصّها ولا يرفض الحفظ برسالة تقنية.
    """
    if value in (None, ""):
        return None
    from decimal import Decimal, ROUND_HALF_UP
    try:
        return Decimal(str(value)).quantize(Decimal("0.0000001"),
                                            rounding=ROUND_HALF_UP)
    except Exception:      # noqa: BLE001
        return None


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def work_sites(request):
    """مواقع العمل — قائمة وإضافة."""
    from apps.attendance.models_sites import WorkSite

    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "sites.view")
        qs = Gate.filter_queryset(
            request.user, "sites.view", WorkSite.objects.all()
        ).filter(company_id=company_id).select_related("site_manager__person")

        return Response([{
            "id": s.id, "code": s.code, "name_ar": s.name_ar,
            "city": s.city, "address": s.address,
            "latitude": str(s.latitude) if s.latitude else None,
            "longitude": str(s.longitude) if s.longitude else None,
            "radius_meters": s.radius_meters,
            "tolerance_meters": s.tolerance_meters,
            "effective_radius": s.effective_radius,
            "enforce_geofence": s.enforce_geofence,
            "has_coordinates": s.has_coordinates,
            "manager": (s.site_manager.person.display_name
                        if s.site_manager else ""),
            "employees": s.assignments.count(),
            "devices": s.devices.count(),
            "is_active": s.is_active,
        } for s in qs])

    Gate.require(request.user, "sites.manage")
    d = request.data

    try:
        site = WorkSite.objects.create(
            account_id=request.user.person.account_id,
            company_id=company_id,
            code=(d.get("code") or "").strip()[:20],
            name_ar=(d.get("name_ar") or "").strip()[:150],
            name_en=(d.get("name_en") or "").strip()[:150],
            city=(d.get("city") or "").strip()[:80],
            address=(d.get("address") or "").strip()[:255],
            latitude=_coord(d.get("latitude")),
            longitude=_coord(d.get("longitude")),
            radius_meters=int(d.get("radius_meters") or 100),
            tolerance_meters=int(d.get("tolerance_meters") or 100),
            enforce_geofence=bool(d.get("enforce_geofence", True)),
            note=(d.get("note") or "")[:255])
    except Exception as e:      # noqa: BLE001
        return Response({"detail": f"بيانات غير صالحة: {e}"}, status=400)

    return Response({"id": site.id, "code": site.code}, status=201)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def work_site_detail(request, site_id):
    """تعديل موقع أو تعطيله."""
    from apps.attendance.models_sites import WorkSite

    Gate.require(request.user, "sites.manage")
    site = Gate.filter_queryset(
        request.user, "sites.manage", WorkSite.objects.all()
    ).filter(id=site_id).first()
    if site is None:
        return Response({"detail": "الموقع غير موجود"}, status=404)

    if request.method == "DELETE":
        site.is_active = False
        site.save(update_fields=["is_active", "updated_at"])
        return Response({"deactivated": True})

    d = request.data
    for field in ("name_ar", "name_en", "city", "address", "note"):
        if field in d:
            setattr(site, field, (d.get(field) or "")[:255])
    for field in ("latitude", "longitude"):
        if field in d:
            setattr(site, field, _coord(d[field]))
            continue
        if field in d:
            setattr(site, field, d.get(field) or None)
    for field in ("radius_meters", "tolerance_meters"):
        if field in d:
            setattr(site, field, int(d.get(field) or 100))
    if "enforce_geofence" in d:
        site.enforce_geofence = bool(d["enforce_geofence"])

    try:
        site.full_clean()
        site.save()
    except Exception as e:      # noqa: BLE001
        return Response({"detail": f"قيمة غير صالحة: {e}"}, status=400)

    return Response({"updated": True})


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def site_assignments(request, site_id):
    """إسناد الموظفين لموقع."""
    from apps.attendance.models_sites import SiteAssignment, WorkSite
    from apps.employees.models import Employment

    Gate.require(request.user, "sites.view")
    site = Gate.filter_queryset(
        request.user, "sites.view", WorkSite.objects.all()
    ).filter(id=site_id).first()
    if site is None:
        return Response({"detail": "الموقع غير موجود"}, status=404)

    if request.method == "GET":
        return Response([{
            "id": a.id,
            "employment_id": a.employment_id,
            "employee_no": a.employment.employee_no,
            "name": a.employment.person.display_name,
            "is_primary": a.is_primary,
            "effective_from": a.effective_from,
            "effective_to": a.effective_to,
        } for a in site.assignments.select_related("employment__person")])

    Gate.require(request.user, "sites.assign")

    if request.method == "DELETE":
        # المعرّف من الرابط أو الجسم — الحذف يقبل الاثنين
        eid = (request.GET.get("employment_id")
               or request.data.get("employment_id"))
        SiteAssignment.objects.filter(site=site, employment_id=eid).delete()
        return Response({"removed": True})

    # ق-77: النقل بتاريخ سريان إلزامي.
    #
    # فالبصمة تُقاس بنطاق الموقع: نقل بلا تاريخ يجعل بصمات الأمس
    # تُقاس بموقع اليوم، فيظهر الموظف خارج النطاق في أيام كان
    # فيها ملتزمًا ويُخصم منه ظلمًا.
    raw = request.data.get("effective_from")
    if not raw:
        return Response(
            {"detail": "حدّد تاريخ بداية العمل في الموقع",
             "code": "effective_from_required"}, status=400)
    try:
        starts = date.fromisoformat(str(raw))
    except ValueError:
        return Response({"detail": f"تاريخ غير صالح: {raw}"}, status=400)

    ids = request.data.get("employment_ids") or []
    if request.data.get("employment_id"):
        ids.append(request.data["employment_id"])

    # الإسناد يمسّ موظفين آخرين — فالبوابة تحدّ بنطاق المُسنِد
    allowed = Gate.filter_queryset(
        request.user, "sites.assign", Employment.objects.all()
    ).filter(company_id=site.company_id)

    made = 0
    for eid in ids:
        emp = allowed.filter(id=eid).first()
        if emp is None:
            continue
        # إسناده السابق يُغلق بيوم قبل الجديد — فلكل يوم موقع
        # واحد، وسجل البصمة يبقى متسقًا مع تاريخ النقل
        SiteAssignment.objects.filter(
            employment=emp, effective_to__isnull=True
        ).exclude(site=site).update(
            effective_to=starts - timedelta(days=1))

        _obj, created = SiteAssignment.objects.update_or_create(
            employment=emp, site=site,
            defaults={"account_id": site.account_id,
                      "company_id": site.company_id,
                      "effective_from": starts,
                      "effective_to": None,
                      "is_primary": bool(request.data.get("is_primary"))})
        made += int(created)

    return Response({"assigned": made}, status=201)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_punch(request):
    """
    بصمة الموظف بنفسه (ق-62).

    GET يرجع مواقعه وحالة بصمته اليوم — فيعرف قبل أن يضغط.
    POST يسجّل البصمة بعد التحقق من النطاق.
    """
    from apps.attendance.models import AttendancePunch
    from apps.attendance.models_sites import PunchMethod
    from apps.attendance.services.geofence import (
        GeofenceError, record_punch, sites_for,
    )
    from django.utils import timezone

    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    # الموظف يبحث عن ارتباطه هو — person مقيّد بالمستخدم نفسه
    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ارتباط وظيفي نشط"}, status=404)

    if request.method == "GET":
        today = timezone.localdate()
        punches = AttendancePunch.objects.filter(
            employment=emp, punched_at__date=today).order_by("punched_at")

        return Response({
            "employee_no": emp.employee_no,
            "today": str(today),
            "punches": [{
                "at": timezone.localtime(p.punched_at).strftime("%H:%M"),
                "source": p.source,
                "site": (p.raw_payload or {}).get("site_code", ""),
            } for p in punches],
            "sites": [{
                "id": s.id, "name_ar": s.name_ar, "code": s.code,
                "latitude": str(s.latitude) if s.latitude else None,
                "longitude": str(s.longitude) if s.longitude else None,
                "radius": s.effective_radius,
                "enforced": s.enforce_geofence,
            } for s in sites_for(emp)],
        })

    try:
        punch, site, distance = record_punch(
            employment=emp,
            latitude=request.data.get("latitude"),
            longitude=request.data.get("longitude"),
            accuracy_m=request.data.get("accuracy"),
            method=PunchMethod.MOBILE_GPS)
    except GeofenceError as e:
        return Response({"detail": str(e), "code": "outside_geofence"},
                        status=400)

    from django.utils import timezone as tz
    return Response({
        "recorded": True,
        "at": tz.localtime(punch.punched_at).strftime("%H:%M"),
        "site": site.name_ar if site else "",
        "distance_m": distance,
    }, status=201)


# ══════════ تعديل الوردية وحذفها ══════════

@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def shift_detail(request, shift_id):
    """
    تعديل وردية أو تعطيلها.

    والرمز لا يُعدَّل: الإسنادات تشير إليه، وتغييره يفصلها عنها.
    والوردية المُسندة تُعطَّل لا تُحذف — فحذفها يترك موظفين بلا
    دوام محدَّد.
    """
    from apps.attendance.models import Shift, ShiftAssignment

    Gate.require(request.user, "attendance.shifts")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    s = Shift.objects.filter(id=shift_id, company_id=_company_id(request)).first()
    if s is None:
        return Response({"detail": "الوردية غير موجودة"}, status=404)

    if request.method == "DELETE":
        assigned = ShiftAssignment.objects.filter(shift=s).exists()
        if assigned:
            s.is_active = False
            s.save(update_fields=["is_active", "updated_at"])
            from apps.core.services.audit import log_action
            log_action(instance=s, action="update",
                       actor=getattr(request.user, "person", None),
                       label=s.code,
                       summary=f"عُطّلت الوردية {s.name_ar} (مُسندة لموظفين)",
                       channel="web")
            return Response({"deactivated": True,
                             "detail": "الوردية مُسندة لموظفين — عُطّلت "
                                       "ولم تُحذف"})

        from apps.core.services.audit import log_delete
        log_delete(instance=s, actor=getattr(request.user, "person", None),
                   label=s.code, summary=f"حُذفت الوردية {s.name_ar}",
                   channel="web")
        s.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "name_en", "name_ur", "start_time", "end_time"):
        if f in d and d[f] not in (None, ""):
            setattr(s, f, d[f])
    for f in ("break_minutes", "grace_in_minutes", "grace_out_minutes"):
        if f in d:
            try:
                setattr(s, f, int(d[f] or 0))
            except (TypeError, ValueError):
                pass
    if "working_days" in d:
        s.working_days = d["working_days"]
    for f in ("crosses_midnight", "is_flexible", "is_active"):
        if f in d:
            setattr(s, f, bool(d[f]))
    s.save()

    from apps.core.services.audit import log_action
    log_action(instance=s, action="update",
               actor=getattr(request.user, "person", None),
               label=s.code, summary=f"عُدّلت الوردية {s.name_ar}",
               channel="web")
    return Response({
        "id": s.id, "code": s.code, "name_ar": s.name_ar,
        "start_time": s.start_time, "end_time": s.end_time,
        "break_minutes": s.break_minutes,
        "grace_in_minutes": s.grace_in_minutes,
        "grace_out_minutes": s.grace_out_minutes,
        "working_days": s.working_days,
        "crosses_midnight": s.crosses_midnight,
        "is_flexible": s.is_flexible, "is_active": s.is_active,
    })


# ══════════ أجهزة البصمة ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def punch_devices(request):
    """
    أجهزة البصمة — قائمة وإضافة.

    والمفتاح يُعرض مرة واحدة عند الإنشاء ثم يُخزَّن مجزّأً: من
    يقرأ القاعدة لا ينتحل جهازًا.
    """
    import secrets

    from django.contrib.auth.hashers import make_password

    from apps.attendance.models_sites import PunchDevice, WorkSite

    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "sites.view")
        qs = Gate.filter_queryset(request.user, "sites.view",
                                  PunchDevice.objects.all())
        return Response([{
            "id": d.id, "device_code": d.device_code,
            "name_ar": d.name_ar,
            "site": d.site.name_ar if d.site_id else None,
            "site_id": d.site_id,
            "last_seen_at": d.last_seen_at,
            "is_active": d.is_active,
        } for d in qs.filter(company_id=company_id).select_related("site")])

    Gate.require(request.user, "sites.manage")

    code = (request.data.get("device_code") or "").strip().upper()
    if not code:
        return Response({"detail": "رمز الجهاز مطلوب"}, status=400)

    # معزول ذاتيًا: مقيَّد بالشركة النشطة للمنفّذ
    if PunchDevice.objects.filter(company_id=_company_id(request), device_code=code).exists():
        return Response({"detail": f"الرمز مستخدم: {code}"}, status=409)

    site = None
    if request.data.get("site_id"):
        site = Gate.filter_queryset(
            request.user, "sites.view", WorkSite.objects.all()
        ).filter(id=request.data["site_id"],
                 company_id=company_id).first()
        if site is None:
            return Response({"detail": "الموقع غير موجود"}, status=400)

    from apps.accounts.models import Company
    # معزول ذاتيًا: مقيَّد بالشركة النشطة للمنفّذ
    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    raw_key = secrets.token_urlsafe(32)
    d = PunchDevice.objects.create(
        account_id=comp.account_id, company_id=company_id,
        device_code=code, name_ar=request.data.get("name_ar", ""),
        site=site, api_key_hash=make_password(raw_key))

    from apps.core.services.audit import log_create
    log_create(instance=d, actor=getattr(request.user, "person", None),
               label=d.device_code,
               summary=f"جهاز بصمة جديد: {d.name_ar}", channel="web")

    return Response({
        "id": d.id, "device_code": d.device_code, "name_ar": d.name_ar,
        # المفتاح يُعرض هنا وحدها — ولا يُسترجع بعدها
        "api_key": raw_key,
        "api_key_note": "احفظ المفتاح الآن — لا يُعرض مرة أخرى",
    }, status=201)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def punch_device_detail(request, device_id):
    """
    تعديل جهاز أو حذفه — والرمز لا يُعدَّل، فالجهاز يُصادق به.
    """
    from apps.attendance.models_sites import PunchDevice, WorkSite

    Gate.require(request.user, "sites.manage")

    # معزول ذاتيًا: مقيَّد بالشركة النشطة للمنفّذ
    d = PunchDevice.objects.filter(id=device_id, company_id=_company_id(request)).first()
    if d is None:
        return Response({"detail": "الجهاز غير موجود"}, status=404)

    if request.method == "DELETE":
        from apps.core.services.audit import log_delete
        log_delete(instance=d, actor=getattr(request.user, "person", None),
                   label=d.device_code,
                   summary=f"حُذف جهاز البصمة {d.name_ar}", channel="web")
        d.delete()
        return Response({"deleted": True})

    if "name_ar" in request.data:
        d.name_ar = request.data["name_ar"]
    if "is_active" in request.data:
        d.is_active = bool(request.data["is_active"])
    if "site_id" in request.data:
        if request.data["site_id"]:
            site = Gate.filter_queryset(
                request.user, "sites.view", WorkSite.objects.all()
            ).filter(id=request.data["site_id"],
                     company_id=d.company_id).first()
            if site is None:
                return Response({"detail": "الموقع غير موجود"}, status=400)
            d.site = site
        else:
            d.site = None
    d.save()

    from apps.core.services.audit import log_action
    log_action(instance=d, action="update",
               actor=getattr(request.user, "person", None),
               label=d.device_code,
               summary=f"عُدّل جهاز البصمة {d.name_ar}", channel="web")
    return Response({
        "id": d.id, "device_code": d.device_code, "name_ar": d.name_ar,
        "site": d.site.name_ar if d.site_id else None,
        "site_id": d.site_id, "last_seen_at": d.last_seen_at,
        "is_active": d.is_active,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def device_setup_guide(request):
    """
    دليل ربط الأجهزة (ق-84).

    فمن يشتري جهازًا يحتاج الرابط والترويسات وشكل الجسم — لا أن
    يبحث في وثيقة منفصلة أو يسأل الدعم.
    """
    Gate.require(request.user, "sites.view")

    base = request.build_absolute_uri("/").rstrip("/")

    return Response({
        "ingest_url": f"{base}/api/attendance/ingest/",
        "ping_url": f"{base}/api/attendance/ingest/ping/",
        "headers": {
            "X-Device-Code": "رمز الجهاز كما أُنشئ في النظام",
            "X-Device-Key": "المفتاح الذي عُرض مرة واحدة عند الإنشاء",
            "Content-Type": "application/json",
        },
        "body_example": {
            "punches": [
                {"employee_no": "1007",
                 "punched_at": "2026-09-05T08:01:33"},
            ],
        },
        "fields_ar": {
            "employee_no": "الرقم الوظيفي — مطلوب",
            "punched_at": "وقت البصمة بصيغة ISO — مطلوب",
            "external_ref": "أي حقل إضافي يُحفظ في البيانات الخام "
                            "للمراجعة، ولا يُعتمد عليه في منع "
                            "التكرار",
        },
        "response_example": {
            "accepted": 1, "duplicated": 0,
            "unknown_employees": [], "invalid": [], "received": 1,
        },
        "max_batch": 500,
        "notes_ar": [
            "رقم الموظف على الجهاز هو الرقم الوظيفي في النظام.",
            "البصمة تُسجَّل بوقتها الأصلي لا بوقت وصولها — فارفع "
            "المتأخرة بتواريخها.",
            "الرفع المتكرّر آمن: البصمة نفسها لا تُحتسب مرتين، "
            "فأعِد رفع ما لم تتأكد من وصوله.",
            "والبصمة تُميَّز بالجهاز والموظف والوقت بالثانية — لا "
            "بمعرّف ترسله أنت، فلا يضرّك اختلافه بين الرفعات.",
            "أقصى دفعة 500 بصمة — قسّم ما زاد.",
            "جرّب ping أولًا: يؤكّد أن الرمز والمفتاح صحيحان قبل "
            "أن تبدأ.",
        ],
    })
