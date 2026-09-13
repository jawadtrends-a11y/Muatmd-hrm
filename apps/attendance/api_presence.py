"""مسارات تتبّع التواجد (ق-144)."""
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.attendance.models import PresenceDay
from apps.attendance.services import presence as svc
from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import Employment, EmploymentStatus


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


def _day_json(d):
    return {
        "id": d.id, "work_date": d.work_date,
        "employment_id": d.employment_id,
        "employee": d.employment.person.display_name,
        "employee_no": d.employment.employee_no,
        "inside_minutes": d.inside_minutes,
        "outside_minutes": d.outside_minutes,
        "no_signal_minutes": d.no_signal_minutes,
        "deductible_minutes": d.deductible_minutes,
        "suggested_amount": (str(d.suggested_amount)
                             if d.suggested_amount is not None else None),
        "is_reviewed": d.is_reviewed,
        "approved_amount": (str(d.approved_amount)
                            if d.approved_amount is not None else None),
        "review_note": d.review_note,
        "is_applied": d.is_applied,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ping(request):
    """
    نبضةٌ من جهاز الموظف.

    ⚠️ **ولا تُحفظ الإحداثيّات** — إنما حكمُها: داخل أو خارج.
    """
    Features.require(_company_id(request), "employee_tracking")

    me = _me(request)
    if me is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"},
                        status=404)

    def _dec(k):
        v = request.data.get(k)
        if v in (None, ""):
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, TypeError):
            return None

    try:
        p = svc.record(employment=me, latitude=_dec("latitude"),
                       longitude=_dec("longitude"))
    except svc.PresenceError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({"state": p.state,
                     "distance_meters": p.distance_meters,
                     "at": p.at},
                    status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_presence(request):
    """
    تواجدي — **فالتتبّع بعلمي لا خفية**.
    """
    Features.require(_company_id(request), "employee_tracking")

    me = _me(request)
    if me is None:
        return Response({"tracked": False, "days": []})

    site = svc.active_site(me)
    qs = (PresenceDay.objects.filter(employment=me)
          .select_related("employment__person")[:60])
    return Response({
        "tracked": site is not None,
        "site": site.name_ar if site else "",
        "within_shift": svc.is_within_shift(me),
        "days": [_day_json(d) for d in qs],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def presence_days(request):
    """تواجد الفريق — وما ينتظر مراجعةً أوّلًا."""
    Gate.require(request.user, "attendance.view")
    Features.require(_company_id(request), "employee_tracking")

    qs = (PresenceDay.objects
          .filter(company_id=_company_id(request))
          .select_related("employment__person"))
    qs = Gate.filter_queryset(request.user, "attendance.view", qs,
                              employment_field="employment")

    if request.GET.get("pending") != "0":
        qs = qs.filter(is_reviewed=False, deductible_minutes__gt=0)
    if request.GET.get("from"):
        qs = qs.filter(work_date__gte=request.GET["from"])
    if request.GET.get("to"):
        qs = qs.filter(work_date__lte=request.GET["to"])

    return Response({
        "days": [_day_json(d) for d in qs[:300]],
        "warning": svc.DEDUCTION_WARNING,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def review_day(request, day_id):
    """
    قرار الموارد — **وبه وحده يقع الخصم**.

    ⚠️ فساعة البريك مرنة، والاقتراح ليس حكمًا.
    """
    Gate.require(request.user, "attendance.edit")
    Features.require(_company_id(request), "employee_tracking")

    d = PresenceDay.objects.filter(
        id=day_id, company_id=_company_id(request)).first()
    if d is None:
        return Response({"detail": "غير موجود"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.review(presence_day=d,
                   approved_amount=request.data.get("approved_amount"),
                   by_person_id=actor.id if actor else None,
                   note=request.data.get("note", ""))
    except svc.PresenceError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_day_json(d))
