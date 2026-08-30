"""
نقطة /me/workspace — مصدر الحقيقة الوحيد للواجهة.

الواجهة الأمامية لا تعرف الأدوار إطلاقًا. ترسم ما يصلها من هنا،
فإضافة دور جديد تصير بيانات لا نشر كود.
راجع الوثيقة المعمارية (2) القسم 6.1.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate

# كل مدخل تنقّل يعلن صلاحيته — لا شروط في الواجهة
NAV_ITEMS = [
    {"key": "dashboard",   "path": "/",                "icon": "home",     "permission": None},
    {"key": "employees",   "path": "/employees",       "icon": "users",    "permission": "employees.view"},
    {"key": "attendance",  "path": "/attendance",      "icon": "clock",    "permission": "attendance.view"},
    {"key": "leaves",      "path": "/leaves",          "icon": "calendar", "permission": "leaves.view"},
    {"key": "requests",    "path": "/requests",        "icon": "inbox",    "permission": "requests.view"},
    {"key": "payroll",     "path": "/payroll",         "icon": "wallet",   "permission": "payroll.view"},
    {"key": "payslips",    "path": "/payslips",        "icon": "receipt",  "permission": "payslips.view_own"},
    {"key": "saudization", "path": "/saudization",     "icon": "chart",    "permission": "saudization.view"},
    {"key": "compliance",  "path": "/compliance",      "icon": "shield",   "permission": "compliance.view"},
    {"key": "org",         "path": "/org",             "icon": "sitemap",  "permission": "org.view"},
    {"key": "access",      "path": "/settings/access", "icon": "key",      "permission": "access.view"},
]

WIDGETS = [
    {"key": "my_requests",        "size": "md", "permission": None},
    {"key": "my_leave_balance",   "size": "sm", "permission": None},
    {"key": "my_attendance",      "size": "md", "permission": None},
    {"key": "pending_approvals",  "size": "md", "permission": "requests.approve"},
    {"key": "expiring_documents", "size": "md", "permission": "employees.view"},
    {"key": "payroll_status",     "size": "lg", "permission": "payroll.view"},
    {"key": "nitaqat_band",       "size": "md", "permission": "saudization.view"},
    {"key": "headcount",          "size": "sm", "permission": "employees.view"},
]


def _allowed(permission, perms):
    return permission is None or permission in perms


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def workspace(request):
    user = request.user
    membership = getattr(user, "account_membership", None)
    if membership is None:
        return Response({"detail": "لا عضوية في أي حساب"}, status=403)

    perms = Gate.accessible_permissions(user)
    account = membership.account
    active = membership.active_company
    allowed_ids = membership.company_ids

    return Response({
        "user": {
            "id": user.id,
            "username": user.username,
            "is_account_owner": membership.is_account_owner,
        },
        "account": {
            "id": account.id,
            "slug": account.slug,
            "name_ar": account.display_name_ar,
            "status": account.status,
            "locale": account.default_locale,
        },
        "active_company": (
            {"id": active.id, "name_ar": active.legal_name_ar} if active else None
        ),
        "companies": [
            {"id": c.id, "name_ar": c.legal_name_ar, "code": c.code}
            for c in account.companies.filter(id__in=allowed_ids)
        ],
        "roles": [
            {"code": a.role.code, "name_ar": a.role.name_ar, "scope": a.scope}
            for a in membership.role_assignments.select_related("role")
        ],
        "permissions": sorted(perms),
        "navigation": [
            {k: v for k, v in item.items() if k != "permission"}
            for item in NAV_ITEMS if _allowed(item["permission"], perms)
        ],
        "dashboard_widgets": [
            {"key": w["key"], "size": w["size"]}
            for w in WIDGETS if _allowed(w["permission"], perms)
        ],
    })
