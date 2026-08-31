"""
API سجل عمليات المنشأة (ق-44).

يُعرض في مكان التعديل نفسه: شاشة الموظف تنادي
/api/audit/employment/12/ فتعرض تاريخه أسفلها.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.models_audit import AuditEntry
from apps.core.services.audit import serialize_entry

# من يرى السجل (ق-44): موظف ومدير الموارد البشرية
AUDIT_PERMISSION = "audit.view"

# تسميات الحقول بالعربية — تُعرض بدل أسماء الأعمدة التقنية
FIELD_LABELS = {
    "employee_no": "الرقم الوظيفي", "join_date": "تاريخ المباشرة",
    "service_start_date": "بداية الخدمة المحتسبة",
    "status": "الحالة", "termination_date": "تاريخ انتهاء الخدمة",
    "termination_reason": "سبب انتهاء الخدمة",
    "is_gosi_registered": "مسجّل في التأمينات",
    "is_mol_registered": "مسجّل في قوى",
    "include_in_wps": "في حماية الأجور",
    "gosi_declared_wage": "الأجر المسجّل لدى التأمينات",
    "gosi_borne_by_company": "الشركة تتحمل حصته",
    "iban": "الآيبان", "bank_code": "البنك",
    "payment_method": "طريقة الصرف",
    "department": "القسم", "branch": "الفرع", "job_title": "المسمى الوظيفي",
    "direct_manager": "المدير المباشر",
    "lines": "إجمالي الراتب", "reason": "السبب",
    "effective_from": "سريان من", "effective_to": "سريان إلى",
    "amount": "المبلغ", "repaid_amount": "المسدَّد",
    "value": "القيمة", "expiry_date": "تاريخ الانتهاء",
    "days_per_year": "الأيام السنوية",
    "is_eosb_subject": "يدخل مكافأة نهاية الخدمة",
    "is_gosi_subject": "خاضع للتأمينات",
    "is_absence_base": "أساس خصم الغياب",
    "is_overtime_base": "أساس العمل الإضافي",
    "is_wps_subject": "في حماية الأجور",
}

# أنواع السجلات المسموح الاستعلام عنها — لا يمر غيرها
ALLOWED_TYPES = {
    "employment", "person", "salary_structure", "payroll_run", "payslip",
    "advance", "asset", "document", "request", "leave_balance",
    "pay_component", "payroll_settings", "role", "role_assignment",
    "branch", "department", "shift", "attendance_day", "leave_type",
    "approval_chain", "bank_template",
}


def _account_id(request):
    return getattr(getattr(request, "account_ctx", None), "account_id", None)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def object_history(request, object_type, object_id):
    """
    سجل تعديلات سجل معيّن — يُعرض أسفل شاشته (ق-44).

    الفلترة بـaccount_id ضرورية رغم RLS: الاستعلام يمر بالبوابة
    ثم بالعزل، والطبقتان معًا لا واحدة.
    """
    Gate.require(request.user, AUDIT_PERMISSION)

    if object_type not in ALLOWED_TYPES:
        return Response({
            "detail": f"نوع غير معروف: {object_type}",
            "allowed": sorted(ALLOWED_TYPES)}, status=400)

    account_id = _account_id(request)
    if account_id is None:
        return Response({"detail": "لا حساب نشط"}, status=400)

    try:
        limit = min(int(request.GET.get("limit", 50)), 200)
    except ValueError:
        limit = 50

    entries = AuditEntry.objects.filter(
        account_id=account_id, object_type=object_type,
        object_id=object_id).select_related("actor_person")[:limit]

    return Response({
        "object_type": object_type,
        "object_id": object_id,
        "count": len(entries),
        "entries": [serialize_entry(e, FIELD_LABELS) for e in entries],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def audit_feed(request):
    """
    آخر العمليات في الشركة — للوحة مدير الموارد.

    ليس بديلًا عن العرض في مكان التعديل (ق-44) بل مكمّل: من يريد
    نظرة سريعة على ما جرى اليوم.
    """
    Gate.require(request.user, AUDIT_PERMISSION)

    account_id = _account_id(request)
    company_id = getattr(getattr(request, "account_ctx", None),
                         "active_company_id", None)
    if account_id is None:
        return Response({"detail": "لا حساب نشط"}, status=400)

    qs = AuditEntry.objects.filter(account_id=account_id)
    if company_id:
        qs = qs.filter(company_id=company_id)

    if request.GET.get("object_type"):
        qs = qs.filter(object_type=request.GET["object_type"])
    if request.GET.get("action"):
        qs = qs.filter(action=request.GET["action"])
    if request.GET.get("actor_id"):
        qs = qs.filter(actor_person_id=request.GET["actor_id"])
    if request.GET.get("from"):
        qs = qs.filter(created_at__date__gte=request.GET["from"])
    if request.GET.get("to"):
        qs = qs.filter(created_at__date__lte=request.GET["to"])

    try:
        limit = min(int(request.GET.get("limit", 100)), 500)
    except ValueError:
        limit = 100

    entries = qs.select_related("actor_person")[:limit]

    return Response({
        "count": len(entries),
        "entries": [
            {
                **serialize_entry(e, FIELD_LABELS),
                "object_type": e.object_type,
                "object_id": e.object_id,
                "object_label": e.object_label,
            }
            for e in entries
        ],
    })
