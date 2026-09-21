"""مسارا الاستبعاد والإعادة (ق-228)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate


def _run(request, run_id):
    from apps.payroll.api import _company_id
    from apps.payroll.models import PayrollRun
    return Gate.filter_queryset(
        request.user, "payroll.create", PayrollRun.objects.all()
    ).filter(id=run_id, company_id=_company_id(request)).first()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_exclude(request, run_id):
    from apps.employees.models import Employment
    from apps.payroll.services import exclusion as svc

    run = _run(request, run_id)
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)
    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=request.data.get("employment_id"),
             company_id=run.company_id).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)
    me = getattr(request.user, "person", None)
    try:
        ex = svc.exclude(run=run, employment=emp,
                         scope=request.data.get("scope") or "run",
                         reason=request.data.get("reason"),
                         by_person_id=me.id if me else None)
    except svc.ExclusionError as e:
        return Response({"detail": str(e), "code": "exclusion"}, status=400)
    return Response({"exclusion_id": ex.id}, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def exclusion_revoke(request, exclusion_id):
    from apps.payroll.models_exclusion import PayrollExclusion
    from apps.payroll.services import exclusion as svc

    run = _run(request, request.data.get("run_id"))
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)
    ex = PayrollExclusion.objects.filter(
        id=exclusion_id, company_id=run.company_id).first()
    if ex is None:
        return Response({"detail": "الاستبعاد غير موجود"}, status=404)
    me = getattr(request.user, "person", None)
    try:
        svc.revoke(exclusion=ex, run=run, by_person_id=me.id if me else None)
    except svc.ExclusionError as e:
        return Response({"detail": str(e), "code": "exclusion"}, status=400)
    return Response({"revoked": True})
