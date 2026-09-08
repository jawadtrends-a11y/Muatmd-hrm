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
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exemptions(request):
    """قائمة المعفيّين — السارية أولًا."""
    from apps.core.i18n import request_locale

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
