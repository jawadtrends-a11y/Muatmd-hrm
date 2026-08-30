"""
API الحضور والانصراف.

⚠️ ق-13: ممنوع إضافة أي تحقق تداخل عبر الشركات هنا أو في أي طبقة.
الحضور المتداخل حالة صحيحة — راجع apps/attendance/services/rules.py
"""
from datetime import date, datetime

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

    return Response([
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
        for d in qs.order_by("work_date")
    ])


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
