"""
الإعفاءات من الحضور والانصراف (ق-104).

عرضٌ وإلغاء فقط — والإنشاء يمرّ بطلب معتمد لا بزرّ مباشر: فمن
أُعفي من البصمة لا يُطالَب بها، وذلك قرار يوثَّق ويُعتمد.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.attendance.models_exemption import AttendanceExemption
from apps.core.access.gate import Gate


def _serialize(x, locale="ar"):
    emp = x.employment
    person = emp.person
    return {
        "id": x.id,
        "employment_id": emp.id,
        "employee_no": emp.employee_no,
        "name": person.name_for(locale),
        "department": (emp.department.name_ar if emp.department else ""),
        "start_date": str(x.start_date),
        "end_date": str(x.end_date) if x.end_date else None,
        "reason": x.reason,
        "is_active": x.is_active,
        "request_no": x.request.request_no if x.request_id else "",
        # ق-229: والمصدر ظاهر — بطلبٍ معتمد أو يدويًّا
        "source": "request" if x.request_id else "manual",
        "granted_by_person_id": x.granted_by_person_id,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def exemptions(request):
    """قائمة المعفيّين — السارية أولًا. وPOST إعفاءٌ يدويّ (ق-229)."""
    from apps.core.i18n import request_locale

    if request.method == "POST":
        return _grant_manual(request)

    Gate.require(request.user, "attendance.view")
    qs = Gate.filter_queryset(
        request.user, "attendance.view",
        AttendanceExemption.objects.all()
    ).select_related("employment__person", "employment__department",
                     "request").order_by("-is_active", "-start_date")

    if request.GET.get("active") == "1":
        qs = qs.filter(is_active=True)

    locale = request_locale(request)
    return Response([_serialize(x, locale) for x in qs[:200]])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def revoke_exemption(request, exemption_id):
    """
    إلغاء إعفاء — لا حذفه.

    فمن أُعفي ثم أُعيد للبصمة يبقى أثره في السجلّ: المسير الماضي
    احتُسب على أساسه، ومحوُه يجعل شهرًا مضى غير مفهوم.
    """
    from django.utils import timezone

    Gate.require(request.user, "attendance.edit")
    qs = Gate.filter_queryset(request.user, "attendance.edit",
                              AttendanceExemption.objects.all())
    x = qs.filter(id=exemption_id).first()
    if x is None:
        return Response({"detail": "غير موجود"},
                        status=status.HTTP_404_NOT_FOUND)
    if not x.is_active:
        return Response({"detail": "ملغى أصلًا"},
                        status=status.HTTP_409_CONFLICT)

    x.is_active = False
    x.revoked_at = timezone.now()
    x.save(update_fields=["is_active", "revoked_at", "updated_at"])
    return Response({"revoked": True, "id": x.id})


def _grant_manual(request):
    """
    إعفاءٌ يدويّ من مدير الموارد (ق-229).

    \u26a0\u26a0 **والتوثيق باقٍ — روح ق-104**: السبب إلزاميّ والفاعل
    يُنسب. فالطريق صار اثنين، **والقرار ما زال يوثَّق**.
    """
    from datetime import date

    from apps.attendance.services.exemptions import (
        ExemptionError, grant_exemption)
    from apps.core.i18n import request_locale
    from apps.employees.models import Employment

    Gate.require(request.user, "attendance.edit")
    d = request.data
    emp = Gate.filter_queryset(
        request.user, "attendance.edit", Employment.objects.all()
    ).filter(id=d.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"},
                        status=status.HTTP_404_NOT_FOUND)
    reason = str(d.get("reason") or "").strip()
    if not reason:
        return Response({"detail": "سبب الإعفاء مطلوب"}, status=400)
    try:
        start = date.fromisoformat(str(d.get("start_date")))
        end = (date.fromisoformat(str(d["end_date"]))
               if d.get("end_date") else None)
    except (TypeError, ValueError):
        return Response({"detail": "التاريخ غير صحيح"}, status=400)

    me = getattr(request.user, "person", None)
    try:
        ex = grant_exemption(employment=emp, start=start, end=end,
                             reason=reason,
                             by_person_id=me.id if me else None)
    except ExemptionError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_serialize(ex, request_locale(request)),
                    status=status.HTTP_201_CREATED)
