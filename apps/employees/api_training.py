"""مسارات التدريب والدورات (ق-149)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import (
    CourseDeliveryMode, Employment, EmploymentStatus, NominationState,
    TrainingCourse, TrainingNomination, TrainingRequest)
from apps.employees.services import training as svc


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _me(request):
    person = getattr(request.user, "person", None)
    if person is None:
        return None
    return Employment.objects.filter(
        person=person, company_id=_company_id(request),
        status=EmploymentStatus.ACTIVE).first()


def _dec(v):
    if v in (None, ""):
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        return None


def _course_json(c):
    return {
        "id": c.id, "code": c.code, "name_ar": c.name_ar,
        "provider": c.provider, "description": c.description,
        "duration_hours": c.duration_hours,
        "cost": str(c.cost) if c.cost is not None else None,
        "delivery_mode": c.delivery_mode,
        "delivery_label": c.get_delivery_mode_display(),
        "is_active": c.is_active,
    }


def _nom_json(n):
    return {
        "id": n.id, "course": n.course.name_ar, "course_id": n.course_id,
        "provider": n.course.provider,
        "employment_id": n.employment_id,
        "employee": n.employment.person.display_name,
        "employee_no": n.employment.employee_no,
        "scheduled_on": n.scheduled_on,
        "cost": str(n.cost) if n.cost is not None else None,
        "state": n.state, "state_label": n.get_state_display(),
        "decision_note": n.decision_note,
        "score": str(n.score) if n.score is not None else None,
        "passed": n.passed,
        "certificate_url": n.certificate_url,
        "completed_on": n.completed_on,
        "result_note": n.result_note,
    }


def _req_json(r):
    return {
        "id": r.id, "course_name": r.course_name,
        "provider": r.provider,
        "employment_id": r.employment_id,
        "employee": r.employment.person.display_name,
        "estimated_cost": (str(r.estimated_cost)
                           if r.estimated_cost is not None else None),
        "justification": r.justification,
        "reference_url": r.reference_url,
        "state": r.state, "state_label": r.get_state_display(),
        "decision_note": r.decision_note,
        "created_course_id": r.created_course_id,
    }


# ══════════ كتالوج الدورات ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def courses(request):
    """الدورات المتاحة — عرضًا وإضافة."""
    Features.require(_company_id(request), "training")

    if request.method == "GET":
        qs = TrainingCourse.objects.filter(
            company_id=_company_id(request))
        if request.GET.get("active") != "0":
            qs = qs.filter(is_active=True)
        return Response({
            "courses": [_course_json(c) for c in qs],
            "modes": [{"value": v, "label": lbl}
                      for v, lbl in CourseDeliveryMode.choices],
        })

    Gate.require(request.user, "employees.edit")
    from apps.accounts.models import Company

    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    code = str(d.get("code") or "").strip().upper()
    if not code or not str(d.get("name_ar") or "").strip():
        return Response({"detail": "الرمز والاسم مطلوبان"}, status=400)
    if TrainingCourse.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    c = TrainingCourse.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=d.get("name_ar", ""), provider=d.get("provider", ""),
        description=d.get("description", ""),
        duration_hours=d.get("duration_hours") or None,
        cost=_dec(d.get("cost")),
        delivery_mode=d.get("delivery_mode")
        or CourseDeliveryMode.ONSITE)
    return Response(_course_json(c), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def course_detail(request, course_id):
    """
    تعديل دورة أو تعطيلها.

    ⚠️ **والمستعملة تُعطَّل ولا تُحذف**: ترشيحاتٌ تشير إليها.
    """
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "training")

    c = TrainingCourse.objects.filter(
        id=course_id, company_id=_company_id(request)).first()
    if c is None:
        return Response({"detail": "غير موجودة"}, status=404)

    if request.method == "DELETE":
        if c.nominations.exists():
            c.is_active = False
            c.save(update_fields=["is_active"])
            return Response({"deactivated": True,
                             "detail": "مستعملة — عُطّلت ولم تُحذف"})
        c.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "provider", "description"):
        if f in d:
            setattr(c, f, str(d[f] or ""))
    if "duration_hours" in d:
        c.duration_hours = d["duration_hours"] or None
    if "cost" in d:
        c.cost = _dec(d["cost"])
    if d.get("delivery_mode") in CourseDeliveryMode.values:
        c.delivery_mode = d["delivery_mode"]
    if "is_active" in d:
        c.is_active = bool(d["is_active"])
    c.save()
    return Response(_course_json(c))


# ══════════ الترشيحات ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def nominations(request):
    """الترشيحات — عرضًا وترشيحًا."""
    Gate.require(request.user, "employees.view")
    Features.require(_company_id(request), "training")

    if request.method == "GET":
        qs = (TrainingNomination.objects
              .filter(company_id=_company_id(request))
              .select_related("employment__person", "course"))
        qs = Gate.filter_queryset(request.user, "employees.view", qs,
                                  employment_field="employment")
        if request.GET.get("state"):
            qs = qs.filter(state=request.GET["state"])
        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])

        rows = list(qs[:300])
        # ⚠️ وتنبيه الميزانية يُعرض مع المعلَّق — فالقرار على بصيرة
        warnings = {}
        for n in rows:
            if n.state == NominationState.PENDING:
                out = svc.check_budget(n)
                if out["exceeds"]:
                    warnings[n.id] = out["warning"]

        return Response({
            "nominations": [_nom_json(n) for n in rows],
            "budget_warnings": warnings,
            "states": [{"value": v, "label": lbl}
                       for v, lbl in NominationState.choices],
        })

    Gate.require(request.user, "employees.edit")
    d = request.data

    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=d.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    course = TrainingCourse.objects.filter(
        id=d.get("course_id"), company_id=_company_id(request)).first()
    if course is None:
        return Response({"detail": "الدورة غير موجودة"}, status=404)

    on = None
    if d.get("scheduled_on"):
        try:
            on = date.fromisoformat(str(d["scheduled_on"]))
        except ValueError:
            return Response({"detail": "تاريخ غير صالح"}, status=400)

    actor = _me(request)
    try:
        n = svc.nominate(course=course, employment=emp, scheduled_on=on,
                         by_employment_id=actor.id if actor else None)
    except svc.TrainingError as e:
        return Response({"detail": str(e)}, status=400)

    out = _nom_json(n)
    out["budget"] = svc.check_budget(n)
    return Response(out, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def decide_nomination(request, nomination_id):
    """
    اعتماد الموارد للترشيح.

    ⚠️ **فترشيحٌ بلا مراجعة يصرف ميزانيةً بلا ضابط**.
    """
    Gate.require(request.user, "approvals.manage")
    Features.require(_company_id(request), "training")

    n = TrainingNomination.objects.filter(
        id=nomination_id, company_id=_company_id(request)).first()
    if n is None:
        return Response({"detail": "غير موجود"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.decide_nomination(
            nomination=n, approve=bool(request.data.get("approve")),
            by_person_id=actor.id if actor else None,
            note=request.data.get("note", ""))
    except svc.TrainingError as e:
        return Response({"detail": str(e)}, status=409)
    return Response(_nom_json(n))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nomination_result(request, nomination_id):
    """تسجيل الحضور والنتيجة والشهادة."""
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "training")

    n = TrainingNomination.objects.filter(
        id=nomination_id, company_id=_company_id(request)).first()
    if n is None:
        return Response({"detail": "غير موجود"}, status=404)

    d = request.data
    try:
        svc.record_result(
            nomination=n, attended=bool(d.get("attended")),
            score=d.get("score"), passed=d.get("passed"),
            certificate_url=d.get("certificate_url", ""),
            note=d.get("note", ""))
    except svc.TrainingError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_nom_json(n))


# ══════════ طلبات الموظفين ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def training_requests(request):
    """طلبات الدورات غير المتوفّرة."""
    Features.require(_company_id(request), "training")

    me = _me(request)

    if request.method == "GET":
        qs = (TrainingRequest.objects
              .filter(company_id=_company_id(request))
              .select_related("employment__person"))
        # ⚠️ من يرى الموظفين يرى الجميع، وغيره يرى طلباته وحده
        if not Gate.check(request.user, "employees.view").allowed:
            if me is None:
                return Response({"requests": []})
            qs = qs.filter(employment=me)
        if request.GET.get("state"):
            qs = qs.filter(state=request.GET["state"])
        return Response({"requests": [_req_json(r) for r in qs[:200]]})

    if me is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"},
                        status=404)

    d = request.data
    try:
        r = svc.request_course(
            employment=me, course_name=d.get("course_name", ""),
            justification=d.get("justification", ""),
            provider=d.get("provider", ""),
            estimated_cost=d.get("estimated_cost"),
            reference_url=d.get("reference_url", ""))
    except svc.TrainingError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_req_json(r), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def decide_request(request, request_id):
    """قرار الموارد في الطلب — وقد تُضيفه للكتالوج."""
    Gate.require(request.user, "approvals.manage")
    Features.require(_company_id(request), "training")

    r = TrainingRequest.objects.filter(
        id=request_id, company_id=_company_id(request)).first()
    if r is None:
        return Response({"detail": "غير موجود"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.decide_request(
            request_obj=r, approve=bool(request.data.get("approve")),
            by_person_id=actor.id if actor else None,
            note=request.data.get("note", ""),
            create_course=bool(request.data.get("create_course")),
            code=request.data.get("code", ""))
    except svc.TrainingError as e:
        return Response({"detail": str(e)}, status=409)
    return Response(_req_json(r))


# ══════════ تدريبي ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_training(request):
    """
    تدريبي — دوراتي وميزانيتي والمتاح.
    """
    Features.require(_company_id(request), "training")

    me = _me(request)
    if me is None:
        return Response({"nominations": [], "available": []})

    noms = (TrainingNomination.objects.filter(employment=me)
            .select_related("course", "employment__person"))
    reqs = TrainingRequest.objects.filter(
        employment=me).select_related("employment__person")
    avail = TrainingCourse.objects.filter(
        company_id=_company_id(request), is_active=True)

    return Response({
        "nominations": [_nom_json(n) for n in noms[:100]],
        "requests": [_req_json(r) for r in reqs[:50]],
        "available": [_course_json(c) for c in avail],
        "budget": svc.budget_state(me),
    })
