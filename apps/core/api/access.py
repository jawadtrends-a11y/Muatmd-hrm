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


# ══════════ صلاحيات موظف بعينه (ق-67 وق-78) ══════════

@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def member_permissions(request, employment_id):
    """
    صلاحيات موظف بعينه — قراءةً وتعديلًا.

    مدير الحساب يفتح موظفًا فيرى كل الكتالوج بمفاتيح، ويميّز
    الموروث من دوره عن الاستثناء الشخصي (ق-67). والصلاحية تحمل
    مداها في اسمها فلا يُسأل عن نطاق (ق-78).
    """
    from apps.accounts.models_access import PermissionOverride
    from apps.core.access.catalog import PERMISSION_KEYS, validate_keys
    from apps.employees.models import Employment

    Gate.require(request.user, "access.manage")

    company_id = getattr(getattr(request, "account_ctx", None),
                         "active_company_id", None)
    emp = Gate.filter_queryset(
        request.user, "access.manage", Employment.objects.all()
    ).filter(id=employment_id, company_id=company_id).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    user = getattr(emp.person, "user", None)
    membership = getattr(user, "account_membership", None) if user else None
    if membership is None:
        return Response({"detail": "لا حساب دخول لهذا الموظف"}, status=404)

    def role_keys():
        """صلاحيات أدواره — بلا الاستثناءات الشخصية."""
        if membership.is_account_owner:
            return set(PERMISSION_KEYS)
        keys = set()
        for a in membership.role_assignments.select_related("role"):
            keys |= a.role.permission_keys
        return keys

    if request.method == "PUT":
        wanted = set(request.data.get("permissions") or [])
        try:
            validate_keys(wanted)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        from_role = role_keys()

        # الاستثناء يُسجَّل للفرق وحده: ما زاد عن الدور يُمنح، وما
        # نقص عنه يُنزع. فلا نكرّر ما يمنحه الدور أصلًا — وتعديل
        # الدور لاحقًا يسري على الجميع كما ينبغي.
        with transaction.atomic():
            # معزول ذاتيًا: مقيَّد بعضوية الموظف المفتوح وشركته
            PermissionOverride.objects.filter(membership=membership, company_id=company_id).delete()
            PermissionOverride.objects.bulk_create(
                [PermissionOverride(membership=membership,
                                    company_id=company_id,
                                    permission_key=k, granted=True)
                 for k in sorted(wanted - from_role)]
                + [PermissionOverride(membership=membership,
                                      company_id=company_id,
                                      permission_key=k, granted=False)
                   for k in sorted(from_role - wanted)])

    from_role = role_keys()
    overrides = {
        o.permission_key: o.granted
        for o in membership.permission_overrides.all()
        if o.company_id in (None, company_id)
    }

    modules = {}
    for p in PERMISSIONS:
        inherited = p.key in from_role
        modules.setdefault(p.module, []).append({
            "key": p.key,
            "name_ar": p.name_ar,
            "granted": overrides.get(p.key, inherited),
            "inherited": inherited,
            "is_override": p.key in overrides,
        })

    return Response({
        "employment_id": emp.id,
        "employee_no": emp.employee_no,
        "name_ar": emp.person.display_name,
        "roles": [a.role.name_ar
                  for a in membership.role_assignments.select_related("role")],
        "is_account_owner": membership.is_account_owner,
        "modules": [{"module": m, "permissions": v}
                    for m, v in modules.items()],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def member_list(request):
    """
    المستخدمون — موظفو المنشأة بحسابات دخولهم وأدوارهم.

    مدخل شاشة الصلاحيات: يفتح مدير الحساب موظفًا منها فيعدّل
    صلاحياته (ق-67).
    """
    from apps.employees.models import Employment, EmploymentStatus

    Gate.require(request.user, "access.manage")
    company_id = getattr(getattr(request, "account_ctx", None),
                         "active_company_id", None)

    qs = Gate.filter_queryset(
        request.user, "access.manage", Employment.objects.all()
    ).filter(company_id=company_id,
             status=EmploymentStatus.ACTIVE).select_related(
        "person__user", "department").order_by("employee_no")

    rows = []
    for e in qs:
        user = getattr(e.person, "user", None)
        m = getattr(user, "account_membership", None) if user else None
        rows.append({
            "id": e.id,
            "employee_no": e.employee_no,
            "name_ar": e.person.display_name,
            "department": e.department.name_ar if e.department else None,
            "username": user.username if user else None,
            "roles": ([a.role.name_ar
                       for a in m.role_assignments.select_related("role")]
                      if m else []),
        })
    return Response(rows)
