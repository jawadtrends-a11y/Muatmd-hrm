"""
API الإجازات والطلبات.

المدير يفتح النظام ليرى ما ينتظره لا ليبحث عنه — لذلك
/me/approvals/ نقطة مستقلة.
"""
from datetime import date, timedelta

from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.leaves.models import (
    ApprovalDecision, LeaveBalance, LeaveType, Request, RequestApproval,
    RequestStatus, RequestType,
)


def _company_id(request):
    return getattr(getattr(request, "account_ctx", None),
                   "active_company_id", None)


def _my_employment(request):
    """الارتباط الوظيفي للمستخدم الحالي — للخدمة الذاتية."""
    from apps.employees.models import Employment, EmploymentStatus
    person = getattr(request.user, "person", None)
    if person is None:
        return None
    return Employment.objects.filter(
        person=person, company_id=_company_id(request),
        status=EmploymentStatus.ACTIVE).first()


# ══════════ أنواع الإجازات ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leave_types(request):
    """أنواع الإجازات المتاحة وسياساتها."""
    Gate.require(request.user, "leaves.view")
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    return Response([
        {
            "id": t.id,
            "code": t.code,
            "name_ar": t.name_ar,
            "name_en": t.name_en,
            "is_paid": t.is_paid,
            "days_per_year": str(t.days_per_year),
            "statutory_min_days": str(t.statutory_min_days),
            "pay_percentage": str(t.pay_percentage),
            "accrual_method": t.accrual_method,
            "days_after_five_years": str(t.days_after_five_years),
            "days_per_event": str(t.days_per_event),
            "carry_forward_policy": t.carry_forward_policy,
            "max_carry_forward_days": str(t.max_carry_forward_days),
            "holiday_treatment": t.holiday_treatment,
            "weekend_treatment": t.weekend_treatment,
            "gender": t.gender_restriction,
            "muslim_only": t.muslim_only,
            "min_service_months": t.min_service_months,
            "once_per_service": t.once_per_service,
            "requires_attachment": t.requires_attachment,
            "max_consecutive_days": t.max_consecutive_days,
            "tiers": [
                {"from_day": tier.from_day, "to_day": tier.to_day,
                 "pay_percentage": str(tier.pay_percentage)}
                for tier in t.tiers.order_by("from_day")
            ],
        }
        for t in LeaveType.objects.filter(
            company_id=company_id, is_active=True).order_by("display_order")
    ])


# ══════════ الأرصدة ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leave_balances(request):
    """
    أرصدة الإجازات.

    بلا employment_id يرجع رصيد المستخدم نفسه — فالموظف يرى
    رصيده بلا صلاحية إضافية.
    """
    company_id = _company_id(request)
    emp_id = request.GET.get("employment_id")
    year = int(request.GET.get("year") or date.today().year)

    if emp_id:
        Gate.require(request.user, "leaves.view")
        qs = Gate.filter_queryset(request.user, "leaves.view",
                                  LeaveBalance.objects.all())
        qs = qs.filter(employment_id=emp_id, year=year)
    else:
        emp = _my_employment(request)
        if emp is None:
            return Response({"detail": "لا ملف موظف مرتبط بحسابك"},
                            status=404)
        qs = LeaveBalance.objects.filter(employment=emp, year=year)

    return Response([
        {
            "leave_type_id": b.leave_type_id,
            "code": b.leave_type.code,
            "name_ar": b.leave_type.name_ar,
            "is_paid": b.leave_type.is_paid,
            "opening": str(b.opening_balance),
            "accrued": str(b.accrued),
            "consumed": str(b.consumed),
            "adjusted": str(b.adjusted),
            "available": str(b.available),
        }
        for b in qs.select_related("leave_type").order_by(
            "leave_type__display_order")
    ])


# ══════════ الطلبات ══════════

def _serialize_request(r, include_chain=False):
    data = {
        "id": r.id,
        "request_no": r.request_no,
        "type": r.request_type,
        "type_label": r.get_request_type_display(),
        "employee_no": r.employment.employee_no,
        "employee_name": r.employment.person.display_name,
        "status": r.status,
        "status_label": r.get_status_display(),
        "current_step": r.current_step,
        "note": r.note,
        "created_at": r.created_at,
        "payload": r.payload,
    }
    if include_chain:
        data["approvals"] = [
            {
                "step": a.step_order,
                "approver": (a.approver_employment.person.display_name
                             if a.approver_employment else "—"),
                "decision": a.decision,
                "decision_label": a.get_decision_display(),
                "comment": a.comment,
                "decided_at": a.decided_at,
            }
            for a in r.approvals.select_related(
                "approver_employment__person").order_by("step_order")
        ]
    return data


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def leave_requests(request):
    """قائمة الطلبات وإنشاؤها."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "leaves.view")
        qs = Gate.filter_queryset(request.user, "leaves.view",
                                  Request.objects.all())
        qs = qs.filter(company_id=company_id).select_related(
            "employment__person")

        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])
        if request.GET.get("type"):
            qs = qs.filter(request_type=request.GET["type"])

        return Response([_serialize_request(r)
                         for r in qs.order_by("-created_at")[:200]])

    # ── إنشاء طلب ──
    from apps.leaves.services.leave_requests import (
        LeaveRequestError, create_leave_request,
    )

    emp_id = request.data.get("employment_id")
    if emp_id:
        Gate.require(request.user, "leaves.manage")
        from apps.employees.models import Employment
        emp = Gate.filter_queryset(
            request.user, "leaves.manage", Employment.objects.all()
        ).filter(id=emp_id, company_id=company_id).first()
    else:
        Gate.require(request.user, "requests.create")
        emp = _my_employment(request)

    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    try:
        res = create_leave_request(
            employment=emp,
            leave_type_code=request.data.get("leave_type_code", ""),
            start_date=date.fromisoformat(request.data["start_date"]),
            requested_days=request.data.get("days"),
            note=request.data.get("note", ""))
    except LeaveRequestError as e:
        return Response({"detail": str(e), "code": "invalid_request"},
                        status=400)
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات ناقصة: {e}"}, status=400)

    return Response({
        "id": res.request.id,
        "request_no": res.request.request_no,
        "status": res.request.status,
        "charged_days": str(res.charged_days),
        "end_date": str(res.end_date),
        "warnings": getattr(res, "warnings", []),
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def request_detail(request, request_id):
    """تفاصيل طلب بسلسلة اعتماده."""
    qs = Request.objects.filter(company_id=_company_id(request))

    if not Gate.check(request.user, "leaves.view").allowed:
        emp = _my_employment(request)
        if emp is None:
            return Response({"detail": "غير مصرّح"}, status=403)
        qs = qs.filter(employment=emp)
    else:
        qs = Gate.filter_queryset(request.user, "leaves.view", qs)

    r = qs.filter(id=request_id).select_related("employment__person").first()
    if r is None:
        return Response({"detail": "الطلب غير موجود"}, status=404)

    return Response(_serialize_request(r, include_chain=True))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def decide_request(request, request_id):
    """
    اعتماد طلب أو رفضه.

    السلسلة تتقدم درجةً درجة، والدرجة الفارغة تُتخطى (ق-35).
    """
    from apps.leaves.services.approvals import ApprovalError, decide

    Gate.require(request.user, "requests.approve")
    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    # النطاق يُطبَّق عبر مقدّم الطلب — فالطلب لا يملك قسمًا
    # ولا مديرًا مباشرًا، وإنما يرثهما من ارتباط مقدّمه
    r = Gate.filter_queryset(
        request.user, "requests.approve", Request.objects.all(),
        employment_field="employment",
    ).filter(id=request_id, company_id=_company_id(request)).first()
    if r is None:
        return Response({"detail": "الطلب غير موجود"}, status=404)

    decision = request.data.get("decision", "")
    if decision not in (ApprovalDecision.APPROVED, ApprovalDecision.REJECTED):
        return Response({"detail": "القرار يجب أن يكون approved أو rejected"},
                        status=400)

    try:
        updated = decide(request_obj=r, approver_employment=emp,
                         decision=decision,
                         comment=request.data.get("comment", ""))
    except ApprovalError as e:
        return Response({"detail": str(e), "code": "cannot_decide"},
                        status=409)

    # الإجازة المعتمدة تُطبَّق على الرصيد والحضور.
    #
    # الإجازة وحدها هنا: أثرها ليس في EFFECTS التي يستدعيها المحرّك،
    # فالأنواع التسعة الأخرى طُبِّق أثرها هناك. واستدعاؤها لغير
    # الإجازة يرفع LeaveError صراحةً («ليس طلب إجازة») فينهار
    # المسار بـ500 بعد أن يكون الطلب قد اعتُمد فعلًا — فيرى
    # المعتمِد خطأً ويظن أن قراره لم يُحفظ.
    #
    # والفشل يُسجَّل ولا يلغي الاعتماد — كما في apply_effect:
    # الموافقة قرار إداري تمّ، والأثر تقني يُعاد تنفيذه.
    if (updated.status == RequestStatus.APPROVED
            and updated.request_type == RequestType.LEAVE):
        from apps.leaves.services.leave_requests import apply_approved_leave
        try:
            apply_approved_leave(updated)
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger("muatmd.requests").error(
                "leave_effect_failed",
                extra={"request_no": updated.request_no, "error": str(e)})

    return Response({
        "id": updated.id,
        "status": updated.status,
        "status_label": updated.get_status_display(),
        "current_step": updated.current_step,
    })


# ══════════ الخدمة الذاتية ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_requests(request):
    """طلباتي — يراها الموظف بلا صلاحية إدارية."""
    Gate.require(request.user, "requests.create")
    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    qs = Request.objects.filter(employment=emp).select_related(
        "employment__person")
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])

    return Response([_serialize_request(r)
                     for r in qs.order_by("-created_at")[:100]])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_approvals(request):
    """
    ما ينتظر اعتمادي.

    المدير يفتح النظام ليرى ما ينتظره لا ليبحث عنه — فهذه
    الشاشة الأولى لكل من يعتمد.
    """
    emp = _my_employment(request)
    if emp is None:
        return Response([])

    pending = RequestApproval.objects.filter(
        approver_employment=emp,
        decision="",   # "" = لم يُقرَّر بعد — كما في محرّك decide
        request__status=RequestStatus.PENDING,
    ).select_related("request__employment__person")

    rows = []
    for a in pending.order_by("request__created_at"):
        r = a.request
        # الدرجة الحالية فقط — لا يُعرض ما لم يصل دوره
        if a.step_order != r.current_step:
            continue
        rows.append({
            **_serialize_request(r),
            "my_step": a.step_order,
            "waiting_since": r.created_at,
        })

    return Response(rows)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_leave_summary(request):
    """
    ملخص إجازاتي — للوحة الموظف.

    الرصيد المتاح وآخر الطلبات في نداء واحد.
    """
    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    year = date.today().year
    balances = LeaveBalance.objects.filter(
        employment=emp, year=year, leave_type__is_paid=True
    ).select_related("leave_type")

    recent = Request.objects.filter(employment=emp).order_by(
        "-created_at")[:5]

    return Response({
        "employee_no": emp.employee_no,
        "year": year,
        "balances": [
            {"code": b.leave_type.code, "name_ar": b.leave_type.name_ar,
             "available": str(b.available), "consumed": str(b.consumed)}
            for b in balances
        ],
        "pending_count": Request.objects.filter(
            employment=emp, status=RequestStatus.PENDING).count(),
        "recent": [_serialize_request(r) for r in recent],
    })


# ══════════════════ الطلبات العامة (ق-54) ══════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def request_types(request):
    """
    الأنواع التي يستحق المستخدم تقديمها، بحقولها.

    الواجهة تبني النموذج من هنا — فإضافة نوع لا تحتاج تعديلها.
    """
    from apps.leaves.services.requests import eligible_types

    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    return Response({
        "employee_no": emp.employee_no,
        "is_saudi": emp.person.nationality_code == "SA",
        "types": eligible_types(emp),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_request(request):
    """
    تقديم طلب — أي نوع.

    الموظف يقدّم لنفسه، ومدير الموارد يقدّم بالنيابة.
    """
    from apps.leaves.services.requests import RequestError, create_request

    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    emp_id = request.data.get("employment_id")
    if emp_id:
        Gate.require(request.user, "requests.manage")
        from apps.employees.models import Employment
        emp = Gate.filter_queryset(
            request.user, "requests.manage", Employment.objects.all()
        ).filter(id=emp_id, company_id=company_id).first()
    else:
        Gate.require(request.user, "requests.create")
        emp = _my_employment(request)

    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    rtype = request.data.get("request_type", "")
    payload = request.data.get("payload") or {}

    try:
        res = create_request(
            employment=emp, request_type=rtype, payload=payload,
            note=request.data.get("note", ""),
            attachment_url=request.data.get("attachment_url", ""))
    except RequestError as e:
        return Response({"detail": str(e), "code": "invalid_request"},
                        status=400)

    return Response({
        "id": res.request.id,
        "request_no": res.request.request_no,
        "status": res.request.status,
        "status_label": res.request.get_status_display(),
        "warnings": res.warnings,
        "effect": res.effect,
    }, status=201)


# ══════════════════ إجازاتي وخطاباتي (ق-58) ══════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_leaves_detail(request):
    """
    إجازاتي — تبويبان: الأرصدة والتاريخ (ق-58).

    الأرصدة تعرض التدرّج النظامي: السنوية، والمرضية بشرائحها
    الثلاث (م/117).
    """
    from datetime import date

    from apps.leaves.models import LeaveBalance, LeaveType, RequestType

    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    year = int(request.GET.get("year") or date.today().year)

    # ── الأرصدة ──
    balances = []
    for b in LeaveBalance.objects.filter(
            employment=emp, year=year).select_related("leave_type"):
        lt = b.leave_type
        tiers = [
            {"from_day": t.from_day, "to_day": t.to_day,
             "pay_percentage": str(t.pay_percentage)}
            for t in lt.tiers.order_by("from_day")
        ]
        balances.append({
            "code": lt.code,
            "name_ar": lt.name_ar,
            "is_paid": lt.is_paid,
            "days_per_year": str(lt.days_per_year),
            "opening": str(b.opening_balance),
            "accrued": str(b.accrued),
            "consumed": str(b.consumed),
            "adjusted": str(b.adjusted),
            "available": str(b.available),
            "tiers": tiers,
        })

    # أنواع بلا رصيد (تُصرف بالحدث لا بالرصيد)
    coded = {b["code"] for b in balances}
    event_types = [
        {"code": t.code, "name_ar": t.name_ar,
         "days_per_event": str(t.days_per_event),
         "is_paid": t.is_paid,
         "once_per_service": t.once_per_service}
        for t in LeaveType.objects.filter(
            company_id=emp.company_id, is_active=True)
        if t.code not in coded and t.days_per_event
    ]

    # ── التاريخ: السابقة والمستقبلية ──
    from apps.leaves.models import Request as LeaveRequest

    history = []
    for r in LeaveRequest.objects.filter(
            employment=emp,
            request_type=RequestType.LEAVE).order_by("-created_at")[:60]:
        p = r.payload or {}
        start = p.get("start_date", "")
        history.append({
            "request_no": r.request_no,
            "leave_type": p.get("leave_type_name") or p.get("leave_type_code", ""),
            "start_date": start,
            "end_date": p.get("end_date", ""),
            "days": str(p.get("charged_days") or p.get("days") or ""),
            "status": r.status,
            "status_label": r.get_status_display(),
            "is_future": bool(start and start > str(date.today())),
        })

    return Response({
        "year": year,
        "employee_no": emp.employee_no,
        "balances": balances,
        "event_types": event_types,
        "history": history,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_letters(request):
    """
    خطاباتي — الشهادات التي صدرت لي (ق-58).

    الشهادة صالحة 30 يومًا من إصدارها (ق-54).
    """
    from datetime import date

    from apps.leaves.models import Request as LeaveRequest
    from apps.leaves.models import RequestStatus, RequestType

    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    rows = []
    for r in LeaveRequest.objects.filter(
            employment=emp,
            request_type=RequestType.CERTIFICATE).order_by("-created_at"):
        p = r.payload or {}
        valid_until = p.get("valid_until", "")
        expired = bool(valid_until and valid_until < str(date.today()))
        rows.append({
            "id": r.id,
            "request_no": r.request_no,
            "certificate_type": p.get("certificate_type", ""),
            "addressed_to": p.get("addressed_to", ""),
            "include_salary": bool(p.get("include_salary")),
            "status": r.status,
            "status_label": r.get_status_display(),
            "issued_at": p.get("issued_at", ""),
            "valid_until": valid_until,
            "expired": expired,
            "downloadable": (r.status == RequestStatus.APPROVED
                             and not expired),
        })

    return Response(rows)


# ══════════════════ معاينة الطلبات (ق-59) ══════════════════

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_request(request):
    """
    معاينة أثر الطلب قبل تقديمه.

    ق-59: النظام يحتسب ما يستطيع احتسابه — الموظف يختار تاريخين
    ويرى الأيام المخصومة ورصيده بعدها، لا يُدخل رقمًا يُشتق منهما.
    """
    from datetime import date, datetime

    from apps.leaves.models import (
        LeaveBalance, LeaveType, Request as Req, RequestStatus, RequestType,
    )
    from apps.leaves.services.balances import (
        LeaveError, compute_days_between,
    )

    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    rtype = request.data.get("request_type", "")
    p = request.data.get("payload") or {}

    # ── إجازة: من/إلى → أيام مخصومة ──
    if rtype == RequestType.LEAVE:
        code = p.get("leave_type_code", "")
        lt = LeaveType.objects.filter(
            company_id=emp.company_id, code=code).first()
        if lt is None:
            return Response({"detail": "اختر نوع الإجازة"}, status=400)

        try:
            start = date.fromisoformat(str(p["start_date"]))
            end = date.fromisoformat(str(p["end_date"]))
        except (KeyError, ValueError):
            return Response({"detail": "حدّد تاريخي البداية والنهاية"},
                            status=400)

        try:
            calc = compute_days_between(
                company=emp.company, leave_type=lt,
                start_date=start, end_date=end)
        except LeaveError as e:
            return Response({"detail": str(e)}, status=400)

        bal = LeaveBalance.objects.filter(
            employment=emp, leave_type=lt, year=start.year).first()
        available = float(bal.available) if bal else None
        charged = float(calc.charged_days)

        warnings = []
        if available is not None and charged > available:
            warnings.append(
                f"الرصيد المتاح {available:.2f} يومًا "
                f"والمطلوب {charged:.0f} — سيُخصم الفارق من الأجر")
        if start < date.today():
            warnings.append("تاريخ البداية في الماضي")

        return Response({
            "leave_type": lt.name_ar,
            "calendar_days": calc.calendar_days,
            "charged_days": f"{charged:.0f}",
            "excluded_days": calc.extended_days,
            "excluded": calc.excluded,
            "start_date": str(start),
            "end_date": str(end),
            "return_date": str(end + timedelta(days=1)),
            "available_before": (f"{available:.2f}" if available is not None
                                 else None),
            "available_after": (f"{available - charged:.2f}"
                                if available is not None else None),
            "is_paid": lt.is_paid,
            "warnings": warnings,
        })

    # ── تصحيح البصمة: منع التكرار لنفس اليوم ──
    if rtype == RequestType.ATTENDANCE_FIX:
        try:
            work_date = date.fromisoformat(str(p["work_date"]))
        except (KeyError, ValueError):
            return Response({"detail": "حدّد التاريخ"}, status=400)

        existing = Req.objects.filter(
            employment=emp, request_type=RequestType.ATTENDANCE_FIX,
            status__in=[RequestStatus.PENDING, RequestStatus.APPROVED],
            payload__work_date=str(work_date)).first()

        from apps.attendance.models import AttendanceDay
        day = AttendanceDay.objects.filter(
            employment=emp, work_date=work_date).first()

        return Response({
            "work_date": str(work_date),
            "duplicate": existing is not None,
            "duplicate_no": existing.request_no if existing else "",
            "current": {
                "status": day.get_status_display() if day else "لا سجل",
                "first_in": (timezone.localtime(day.first_in).strftime("%H:%M")
                             if day and day.first_in else ""),
                "last_out": (timezone.localtime(day.last_out).strftime("%H:%M")
                             if day and day.last_out else ""),
                "late_minutes": day.late_minutes if day else 0,
            } if day else None,
        })

    # ── العمل الإضافي: من/إلى ساعة → دقائق ──
    if rtype == RequestType.OVERTIME:
        try:
            h1, m1 = map(int, str(p["from_time"]).split(":")[:2])
            h2, m2 = map(int, str(p["to_time"]).split(":")[:2])
        except (KeyError, ValueError):
            return Response({"detail": "حدّد وقتي البداية والنهاية"},
                            status=400)

        minutes = (h2 * 60 + m2) - (h1 * 60 + m1)
        if minutes <= 0:
            minutes += 24 * 60      # امتد بعد منتصف الليل

        hours = minutes // 60
        rem = minutes % 60
        return Response({
            "minutes": minutes,
            "hours": hours,
            "remaining_minutes": rem,
            "label": (f"{hours} ساعة" + (f" و{rem} دقيقة" if rem else "")),
            "warnings": (["أكثر من 10 ساعات — راجع الاحتساب"]
                         if minutes > 600 else []),
        })

    # ── رحلة العمل: مغادرة/عودة → أيام ──
    if rtype == RequestType.BUSINESS_TRIP:
        try:
            start = date.fromisoformat(str(p["start_date"]))
            end = date.fromisoformat(str(p["end_date"]))
        except (KeyError, ValueError):
            return Response({"detail": "حدّد تاريخي المغادرة والعودة"},
                            status=400)
        if end < start:
            return Response({"detail": "تاريخ العودة قبل المغادرة"},
                            status=400)
        days = (end - start).days + 1
        return Response({
            "days": days,
            "start_date": str(start),
            "end_date": str(end),
            "note": "رحلة عمل — لا تُخصم من أي رصيد إجازات",
        })

    # ── إنهاء العقد: مدة الإشعار ──
    if rtype == RequestType.RESIGNATION:
        # ق-60: المدة تتبع السبب لا رقمًا ثابتًا
        from apps.payroll.services.eosb import ALL_REASONS, notice_days_for

        code = p.get("termination_reason", "")
        if not code:
            return Response({"detail": "اختر سبب الإنهاء"}, status=400)

        days = notice_days_for(code)
        label = ALL_REASONS.get(code, code)

        if days is None:
            note = "مدة الإشعار بالاتفاق بين الطرفين"
            expected = None
        elif days == 0:
            note = "لا تُشترط مدة إشعار لهذا السبب"
            expected = None
        else:
            note = (f"مدة الإشعار {days} يومًا تبدأ من تاريخ الاعتماد "
                    "النهائي لا من التقديم")
            expected = str(date.today() + timedelta(days=days))

        return Response({
            "reason": label,
            "notice_days": days,
            "note": note,
            "expected_last_day": expected,
            "expected_note": ("آخر يوم عمل متوقع لو اعتُمد اليوم"
                              if expected else ""),
            "reference": "المادة 75 — تعديل م/44 لعام 1446هـ",
        })

    return Response({"detail": "لا معاينة لهذا النوع"}, status=400)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_editable_fields(request):
    """
    الحقول التي يطلب الموظف تعديلها بقيمها الحالية (ق-65).

    الراتب والعقد غائبان — قرارات إدارية والتزامات تعاقدية.
    """
    from apps.leaves.services.requests import (
        EDITABLE_BY_EMPLOYEE, current_value,
    )

    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    return Response({
        "employee_no": emp.employee_no,
        "fields": [{
            "key": key,
            "label": label,
            "current": current_value(emp, key),
            "kind": ("date" if key.endswith("_date")
                     else "select" if key == "marital_status"
                     else "text"),
        } for key, label in EDITABLE_BY_EMPLOYEE.items()],
        "note": "الراتب والعقد لا يُعدَّلان بطلب — راجع الموارد البشرية",
    })
