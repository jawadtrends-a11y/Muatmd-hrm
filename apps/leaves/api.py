"""
API الإجازات والطلبات.

المدير يفتح النظام ليرى ما ينتظره لا ليبحث عنه — لذلك
/me/approvals/ نقطة مستقلة.
"""
from datetime import date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.leaves.models import (
    ApprovalDecision, LeaveBalance, LeaveType, Request, RequestApproval,
    RequestStatus,
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

    r = Gate.filter_queryset(
        request.user, "requests.approve", Request.objects.all()
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

    # الإجازة المعتمدة تُطبَّق على الرصيد والحضور
    if updated.status == RequestStatus.APPROVED:
        from apps.leaves.services.leave_requests import apply_approved_leave
        apply_approved_leave(updated)

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
        decision=ApprovalDecision.PENDING,
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
