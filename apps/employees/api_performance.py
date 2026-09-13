"""مسارات تقييم الأداء (ق-146)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import (
    ApprovalState, Employment, EmploymentStatus, KPI, KPIAssignment,
    KPIDirection, KPIKind, KPIScale, PeerReview, ReviewCycle,
    ReviewKind)
from apps.employees.services import performance as svc


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


def _kpi_json(k):
    return {
        "id": k.id, "code": k.code, "name_ar": k.name_ar,
        "description": k.description,
        "department": k.department.name_ar,
        "department_id": k.department_id,
        "kind": k.kind, "kind_label": k.get_kind_display(),
        "scale": k.scale, "scale_label": k.get_scale_display(),
        "direction": k.direction,
        "direction_label": k.get_direction_display(),
        "unit": k.unit,
        "default_target": (str(k.default_target)
                           if k.default_target is not None else None),
        "state": k.state, "state_label": k.get_state_display(),
        "decision_note": k.decision_note,
        "is_usable": k.is_usable,
    }


def _assign_json(a):
    sc = a.score
    return {
        "id": a.id, "cycle_id": a.cycle_id,
        "employment_id": a.employment_id,
        "employee": a.employment.person.display_name,
        "employee_no": a.employment.employee_no,
        "kpi": a.kpi.name_ar, "kpi_id": a.kpi_id,
        "scale": a.kpi.scale, "unit": a.kpi.unit,
        "target": str(a.target), "weight": a.weight,
        "actual": str(a.actual) if a.actual is not None else None,
        "score": round(float(sc), 1) if sc is not None else None,
        "state": a.state, "state_label": a.get_state_display(),
        "entry_note": a.entry_note, "decision_note": a.decision_note,
    }


# ══════════ الدورات ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def cycles(request):
    """دورات التقييم."""
    Features.require(_company_id(request), "performance")

    if request.method == "GET":
        qs = ReviewCycle.objects.filter(company_id=_company_id(request))
        return Response([{
            "id": c.id, "code": c.code, "name_ar": c.name_ar,
            "start_date": c.start_date, "end_date": c.end_date,
            "is_open": c.is_open,
            "self_review_enabled": c.self_review_enabled,
            "upward_review_enabled": c.upward_review_enabled,
        } for c in qs])

    Gate.require(request.user, "employees.edit")
    from apps.accounts.models import Company

    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    code = str(d.get("code") or "").strip().upper()
    if not code:
        return Response({"detail": "الرمز مطلوب"}, status=400)
    if ReviewCycle.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    try:
        start = date.fromisoformat(str(d["start_date"]))
        end = date.fromisoformat(str(d["end_date"]))
    except (KeyError, TypeError, ValueError):
        return Response({"detail": "تاريخ غير صالح"}, status=400)
    if end < start:
        return Response({"detail": "نهاية الدورة قبل بدايتها"},
                        status=400)

    c = ReviewCycle.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=d.get("name_ar", code), start_date=start, end_date=end,
        self_review_enabled=bool(d.get("self_review_enabled", True)),
        upward_review_enabled=bool(d.get("upward_review_enabled",
                                         True)))
    return Response({"id": c.id, "code": c.code},
                    status=status.HTTP_201_CREATED)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def cycle_detail(request, cycle_id):
    """فتح الدورة أو إغلاقها."""
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "performance")

    c = ReviewCycle.objects.filter(
        id=cycle_id, company_id=_company_id(request)).first()
    if c is None:
        return Response({"detail": "غير موجودة"}, status=404)

    for f in ("is_open", "self_review_enabled",
              "upward_review_enabled"):
        if f in request.data:
            setattr(c, f, bool(request.data[f]))
    if "name_ar" in request.data:
        c.name_ar = str(request.data["name_ar"] or "")[:120]
    c.save()
    return Response({"id": c.id, "is_open": c.is_open})


# ══════════ المؤشّرات ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def kpis(request):
    """المؤشّرات — عرضًا وإنشاءً."""
    Features.require(_company_id(request), "performance")

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = (KPI.objects.filter(company_id=_company_id(request))
              .select_related("department"))
        if request.GET.get("state"):
            qs = qs.filter(state=request.GET["state"])
        if request.GET.get("department_id"):
            qs = qs.filter(department_id=request.GET["department_id"])

        from apps.organization.models import Department

        return Response({
            "kpis": [_kpi_json(k) for k in qs],
            "scales": [{"value": v, "label": lbl}
                       for v, lbl in KPIScale.choices],
            "kinds": [{"value": v, "label": lbl}
                      for v, lbl in KPIKind.choices],
            "directions": [{"value": v, "label": lbl}
                           for v, lbl in KPIDirection.choices],
            "departments": [
                {"id": d.id, "name_ar": d.name_ar}
                for d in Department.objects.filter(
                    company_id=_company_id(request))],
        })

    Gate.require(request.user, "employees.edit")
    from apps.organization.models import Department

    dept = Department.objects.filter(
        id=request.data.get("department_id"),
        company_id=_company_id(request)).first()
    if dept is None:
        return Response({"detail": "الإدارة غير موجودة"}, status=404)

    me = _me(request)
    d = request.data

    def _dec(k):
        v = d.get(k)
        if v in (None, ""):
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, TypeError):
            return None

    try:
        k = svc.create_kpi(
            department=dept, code=d.get("code", ""),
            name_ar=d.get("name_ar", ""),
            scale=d.get("scale") or KPIScale.PERCENT,
            direction=d.get("direction") or KPIDirection.HIGHER,
            kind=d.get("kind") or KPIKind.QUANTITATIVE,
            unit=d.get("unit", ""), description=d.get("description", ""),
            default_target=_dec("default_target"),
            by_employment_id=me.id if me else None)
    except svc.PerformanceError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_kpi_json(k), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def decide_kpi(request, kpi_id):
    """
    اعتماد الموارد للمؤشّر.

    ⚠️ **فمؤشّرٌ بلا مراجعة يصير حكمًا بلا ضابط**.
    """
    Gate.require(request.user, "approvals.manage")
    Features.require(_company_id(request), "performance")

    k = KPI.objects.filter(
        id=kpi_id, company_id=_company_id(request)).first()
    if k is None:
        return Response({"detail": "غير موجود"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.decide_kpi(kpi=k, approve=bool(request.data.get("approve")),
                       by_person_id=actor.id if actor else None,
                       note=request.data.get("note", ""))
    except svc.PerformanceError as e:
        return Response({"detail": str(e)}, status=409)
    return Response(_kpi_json(k))


# ══════════ الإسناد والإدخال ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def assignments(request):
    """إسنادات الدورة — عرضًا وإسنادًا."""
    Gate.require(request.user, "employees.view")
    Features.require(_company_id(request), "performance")

    if request.method == "GET":
        qs = (KPIAssignment.objects
              .filter(company_id=_company_id(request))
              .select_related("employment__person", "kpi"))
        qs = Gate.filter_queryset(request.user, "employees.view", qs,
                                  employment_field="employment")
        if request.GET.get("cycle_id"):
            qs = qs.filter(cycle_id=request.GET["cycle_id"])
        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])
        if request.GET.get("pending_approval") == "1":
            qs = qs.filter(state=ApprovalState.PENDING,
                           actual__isnull=False)
        return Response({"assignments": [_assign_json(a)
                                         for a in qs[:400]]})

    Gate.require(request.user, "employees.edit")
    d = request.data

    cycle = ReviewCycle.objects.filter(
        id=d.get("cycle_id"), company_id=_company_id(request)).first()
    if cycle is None:
        return Response({"detail": "الدورة غير موجودة"}, status=404)

    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=d.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    kpi = KPI.objects.filter(
        id=d.get("kpi_id"), company_id=_company_id(request)).first()
    if kpi is None:
        return Response({"detail": "المؤشّر غير موجود"}, status=404)

    try:
        a = svc.assign(cycle=cycle, employment=emp, kpi=kpi,
                       target=d.get("target"), weight=d.get("weight"))
    except (svc.PerformanceError, InvalidOperation, TypeError) as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_assign_json(a), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def enter_actual(request, assignment_id):
    """
    المشرف يُدخل الفعليّ.

    ⚠️ **ولا يُدخل أحدٌ لنفسه**.
    """
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "performance")

    a = KPIAssignment.objects.filter(
        id=assignment_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "غير موجود"}, status=404)

    try:
        svc.enter_actual(assignment=a, actual=request.data.get("actual"),
                         by_employment=_me(request),
                         note=request.data.get("note", ""))
    except (svc.PerformanceError, InvalidOperation, TypeError) as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_assign_json(a))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def approve_actual(request, assignment_id):
    """اعتماد الموارد للمدخَل — **وبه يصير نتيجة**."""
    Gate.require(request.user, "approvals.manage")
    Features.require(_company_id(request), "performance")

    a = KPIAssignment.objects.filter(
        id=assignment_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "غير موجود"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.approve_actual(
            assignment=a, approve=bool(request.data.get("approve", True)),
            by_person_id=actor.id if actor else None,
            note=request.data.get("note", ""))
    except svc.PerformanceError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_assign_json(a))


# ══════════ التقييمات ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_reviews(request):
    """
    تقييماتي — الذاتيّ وتقييم مديري.

    ⚠️ **وتقييم المدير مجهول** — لا يُحفظ اسمك.
    """
    Features.require(_company_id(request), "performance")

    me = _me(request)
    if me is None:
        return Response({"cycles": []})

    if request.method == "GET":
        open_cycles = ReviewCycle.objects.filter(
            company_id=_company_id(request), is_open=True)
        done_self = set(PeerReview.objects.filter(
            kind=ReviewKind.SELF, subject_employment=me
        ).values_list("cycle_id", flat=True))

        mgr = getattr(me, "manager", None)
        return Response({
            "cycles": [{
                "id": c.id, "name_ar": c.name_ar,
                "self_enabled": c.self_review_enabled,
                "upward_enabled": c.upward_review_enabled,
                "self_done": c.id in done_self,
            } for c in open_cycles],
            "manager": (mgr.person.display_name if mgr else ""),
            "manager_id": mgr.id if mgr else None,
            "my_scores": [
                _assign_json(a) for a in KPIAssignment.objects.filter(
                    employment=me, state=ApprovalState.APPROVED
                ).select_related("kpi", "employment__person")[:50]],
        })

    cycle = ReviewCycle.objects.filter(
        id=request.data.get("cycle_id"),
        company_id=_company_id(request)).first()
    if cycle is None:
        return Response({"detail": "الدورة غير موجودة"}, status=404)

    kind = request.data.get("kind")
    d = request.data
    try:
        if kind == "upward":
            mgr = Employment.objects.filter(
                id=d.get("manager_id"),
                company_id=_company_id(request)).first()
            if mgr is None:
                return Response({"detail": "المدير غير موجود"},
                                status=404)
            svc.submit_upward_review(
                cycle=cycle, author_employment=me,
                manager_employment=mgr, score=d.get("score"),
                strengths=d.get("strengths", ""),
                improvements=d.get("improvements", ""),
                comment=d.get("comment", ""))
        else:
            svc.submit_self_review(
                cycle=cycle, employment=me, score=d.get("score"),
                strengths=d.get("strengths", ""),
                improvements=d.get("improvements", ""),
                comment=d.get("comment", ""))
    except (svc.PerformanceError, TypeError, ValueError) as e:
        return Response({"detail": str(e)}, status=400)

    return Response({"submitted": True},
                    status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def scorecard(request, employment_id):
    """
    بطاقة أداء موظفٍ في دورة — **تقريرٌ لا أثر ماليّ**.
    """
    Gate.require(request.user, "employees.view")
    Features.require(_company_id(request), "performance")

    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=employment_id).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    cycle = ReviewCycle.objects.filter(
        id=request.GET.get("cycle_id"),
        company_id=_company_id(request)).first()
    if cycle is None:
        return Response({"detail": "حدّد الدورة"}, status=400)

    out = svc.final_score(cycle, emp)
    out["employee"] = emp.person.display_name
    out["cycle"] = cycle.name_ar

    self_r = PeerReview.objects.filter(
        cycle=cycle, kind=ReviewKind.SELF,
        subject_employment=emp).first()
    out["self_review"] = ({
        "score": self_r.score, "strengths": self_r.strengths,
        "improvements": self_r.improvements,
    } if self_r else None)

    # ⚠️ **وخلاصة تقييم المديرين مجمَّعة** — لا تُنسب لأحد
    out["upward"] = svc.upward_summary(cycle, emp)
    return Response(out)
