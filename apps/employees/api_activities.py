"""مسارات أنشطة العمل (ق-143)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import (
    ActivityStatus, Employment, EmploymentStatus, PayBasis, PayEffect,
    WorkActivity)
from apps.employees.services import activities as svc


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


def _json(a):
    return {
        "id": a.id, "work_date": a.work_date,
        "employment_id": a.employment_id,
        "employee": a.employment.person.display_name,
        "title": a.title, "description": a.description,
        "target_count": a.target_count, "unit": a.unit,
        "status": a.status, "status_label": a.get_status_display(),
        "done_count": a.done_count,
        "done_note": a.done_note, "pending_note": a.pending_note,
        "achievement": a.achievement,
        "pay_effect": a.pay_effect,
        "pay_basis": a.pay_basis,
        "bonus_amount": (str(a.bonus_amount)
                         if a.bonus_amount is not None else None),
        "deduction_amount": (str(a.deduction_amount)
                             if a.deduction_amount is not None else None),
        "is_reviewed": a.is_reviewed,
        "settled_amount": (str(a.settled_amount)
                           if a.settled_amount is not None else None),
        "is_paid": a.is_paid,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def activities(request):
    """أنشطة الفريق — عرضًا وإسنادًا."""
    Features.require(_company_id(request), "work_activities")

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = (WorkActivity.objects
              .filter(company_id=_company_id(request))
              .select_related("employment__person"))
        qs = Gate.filter_queryset(
            request.user, "employees.view", qs,
            employment_field="employment")

        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        if request.GET.get("from"):
            qs = qs.filter(work_date__gte=request.GET["from"])
        if request.GET.get("to"):
            qs = qs.filter(work_date__lte=request.GET["to"])
        if request.GET.get("pending_review") == "1":
            qs = qs.exclude(status=ActivityStatus.PENDING).filter(
                is_reviewed=False)

        return Response({
            "activities": [_json(a) for a in qs[:400]],
            "statuses": [{"value": v, "label": lbl}
                         for v, lbl in ActivityStatus.choices],
            "effects": [{"value": v, "label": lbl}
                        for v, lbl in PayEffect.choices],
            "bases": [{"value": v, "label": lbl}
                      for v, lbl in PayBasis.choices],
            "deduction_warning": svc.DEDUCTION_WARNING,
        })

    Gate.require(request.user, "employees.edit")
    d = request.data

    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=d.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    try:
        start = date.fromisoformat(str(d.get("start_date")))
        end = date.fromisoformat(str(d.get("end_date") or d["start_date"]))
    except (TypeError, ValueError, KeyError):
        return Response({"detail": "تاريخ غير صالح"}, status=400)

    def _dec(k):
        v = d.get(k)
        if v in (None, ""):
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, TypeError):
            return None

    actor = _me(request)
    try:
        out = svc.assign(
            employment=emp, title=d.get("title", ""),
            start_date=start, end_date=end,
            description=d.get("description", ""),
            target_count=d.get("target_count") or None,
            unit=d.get("unit", ""),
            pay_effect=d.get("pay_effect") or PayEffect.NONE,
            pay_basis=d.get("pay_basis") or PayBasis.PER_ACTIVITY,
            bonus_amount=_dec("bonus_amount"),
            deduction_amount=_dec("deduction_amount"),
            by_employment_id=actor.id if actor else None,
            skip_weekends=bool(d.get("skip_weekends", True)))
    except svc.ActivityError as e:
        return Response({"detail": str(e)}, status=400)

    return Response(out, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_activities(request):
    """أنشطتي — وما ينتظر إقراري أوّلًا."""
    Features.require(_company_id(request), "work_activities")

    me = _me(request)
    if me is None:
        return Response({"activities": []})

    qs = WorkActivity.objects.filter(employment=me).select_related(
        "employment__person")
    if request.GET.get("from"):
        qs = qs.filter(work_date__gte=request.GET["from"])
    if request.GET.get("to"):
        qs = qs.filter(work_date__lte=request.GET["to"])

    rows = sorted(qs[:200],
                  key=lambda a: (a.status != ActivityStatus.PENDING,
                                 -a.work_date.toordinal()))
    return Response({
        "activities": [_json(a) for a in rows],
        "statuses": [{"value": v, "label": lbl}
                     for v, lbl in ActivityStatus.choices
                     if v != ActivityStatus.PENDING],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def report_activity(request, activity_id):
    """
    إقرار الموظف — **ولا يُقرّ عن غيره**.
    """
    Features.require(_company_id(request), "work_activities")

    me = _me(request)
    a = WorkActivity.objects.filter(
        id=activity_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "غير موجود"}, status=404)
    if me is None or a.employment_id != me.id:
        return Response({"detail": "هذا نشاط غيرك"}, status=403)

    try:
        svc.report(activity=a, status=request.data.get("status"),
                   done_count=request.data.get("done_count"),
                   done_note=request.data.get("done_note", ""),
                   pending_note=request.data.get("pending_note", ""))
    except svc.ActivityError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_json(a))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def review_activity(request, activity_id):
    """
    مراجعة المدير — **وبها وحدها يقع الأثر الماليّ**.
    """
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "work_activities")

    a = WorkActivity.objects.filter(
        id=activity_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "غير موجود"}, status=404)

    override = request.data.get("override")
    actor = getattr(request.user, "person", None)
    try:
        svc.review(activity=a, by_person_id=actor.id if actor else None,
                   note=request.data.get("note", ""),
                   override=override if override not in (None, "") else None)
    except svc.ActivityError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_json(a))
