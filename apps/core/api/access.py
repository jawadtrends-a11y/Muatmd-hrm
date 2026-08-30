"""
API إدارة الصلاحيات والأدوار.

المبدأ الحاكم (قرار المالك): النظام ينظّم ولا يصادر السلطة الإدارية.
كل دور قابل للتعديل عدا الحد الأدنى المحمي لدور المالك.
"""
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models_access import Role
from apps.core.access.catalog import (
    PERMISSIONS, PROTECTED_OWNER_PERMISSIONS, Scope,
)
from apps.core.access.gate import Gate


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def permission_catalog(request):
    """الكتالوج مجمّعًا بالوحدات — لشاشة التوزيع بفئات مطوية."""
    Gate.require(request.user, "access.view")

    modules = {}
    for p in PERMISSIONS:
        modules.setdefault(p.module, []).append({
            "key": p.key,
            "name_ar": p.name_ar,
            "is_protected": p.key in PROTECTED_OWNER_PERMISSIONS,
        })

    return Response({
        "modules": [
            {"key": k, "permissions": v} for k, v in sorted(modules.items())
        ],
        "scopes": [
            {"value": s.value, "rank": s.rank} for s in Scope
        ],
        "total": len(PERMISSIONS),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def role_list(request):
    """أدوار الحساب مع عدد صلاحيات كل دور."""
    Gate.require(request.user, "access.view")
    qs = Gate.filter_queryset(request.user, "access.view", Role.objects.all())

    return Response([
        {
            "id": r.id,
            "code": r.code,
            "name_ar": r.name_ar,
            "default_scope": r.default_scope,
            "is_system": r.is_system,
            "permission_count": r.permissions.count(),
            "assigned_users": r.assignments.count(),
        }
        for r in qs.prefetch_related("permissions", "assignments")
    ])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def role_detail(request, role_id):
    Gate.require(request.user, "access.view")
    qs = Gate.filter_queryset(request.user, "access.view", Role.objects.all())
    role = qs.filter(id=role_id).first()
    if role is None:
        return Response({"detail": "الدور غير موجود"}, status=404)

    return Response({
        "id": role.id,
        "code": role.code,
        "name_ar": role.name_ar,
        "default_scope": role.default_scope,
        "is_system": role.is_system,
        "permissions": sorted(role.permission_keys),
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def role_permissions_update(request, role_id):
    """
    يضبط صلاحيات دور. الحد الأدنى المحمي يمنع قفل الحساب على صاحبه،
    وما عداه حر بالكامل.
    """
    from apps.accounts.services.roles import (
        ProtectedPermissionError, set_role_permissions,
    )

    Gate.require(request.user, "access.manage")
    qs = Gate.filter_queryset(request.user, "access.manage", Role.objects.all())
    role = qs.filter(id=role_id).select_for_update().first()
    if role is None:
        return Response({"detail": "الدور غير موجود"}, status=404)

    keys = request.data.get("permissions")
    if not isinstance(keys, list):
        return Response(
            {"detail": "الحقل permissions مطلوب ويجب أن يكون قائمة"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        applied = set_role_permissions(role, keys)
    except ProtectedPermissionError as e:
        return Response({"detail": str(e), "code": "protected_permission"},
                        status=status.HTTP_409_CONFLICT)
    except ValueError as e:
        return Response({"detail": str(e), "code": "unknown_permission"},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response({"id": role.id, "permissions": applied,
                     "count": len(applied)})
