"""
API إدارة الصلاحيات والأدوار.

المبدأ الحاكم (قرار المالك): النظام ينظّم ولا يصادر السلطة الإدارية.
كل دور قابل للتعديل عدا الحد الأدنى المحمي لدور المالك.
"""
from django.db import transaction
from django.utils import timezone
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def transfer_ownership(request, employment_id):
    """
    نقل ملكية الحساب لموظف آخر (ق-76).

    الملكية سيطرة إدارية على النظام، والمدير العام دور وظيفي —
    وأكثر المديرين العامين لا يتفرّغون لمتابعة أنظمة الأتمتة.
    فتنزل الملكية للدرجة المناسبة.

    وينقلها المالك الحالي، أو ينتزعها المدير العام: فهو صاحب
    السلطة العليا في الشركة ولو لم يُدر النظام.
    """
    from apps.accounts.models_access import AccountMembership
    from apps.employees.models import Employment

    me = getattr(request.user, "account_membership", None)
    if me is None:
        return Response({"detail": "لا عضوية لحسابك"}, status=403)

    is_ceo = any(a.role.code == "ceo"
                 for a in me.role_assignments.select_related("role"))
    if not (me.is_account_owner or is_ceo):
        return Response(
            {"detail": "ينقل الملكية مالك الحساب الحالي أو المدير العام",
             "code": "not_allowed"}, status=403)

    company_id = getattr(getattr(request, "account_ctx", None),
                         "active_company_id", None)
    # معزول ذاتيًا: مقيَّد بحساب المنفّذ نفسه.
    #
    # ولا يُفلتر بـaccess.manage: المدير العام يمنح الملكية (ق-76)
    # ولا يدير الصلاحيات (ق-78) — فالفلترة بها تمنعه مما يملكه.
    emp = Employment.objects.filter(
        id=employment_id, account_id=me.account_id,
        company_id=company_id).select_related("person__user").first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    user = getattr(emp.person, "user", None)
    target = getattr(user, "account_membership", None) if user else None
    if target is None:
        return Response(
            {"detail": "لا حساب دخول لهذا الموظف — أنشئه أولًا"}, status=400)

    grant = request.data.get("grant", True)

    if grant:
        if target.is_account_owner:
            return Response({"detail": "هو مالك أصلًا"}, status=400)

        with transaction.atomic():
            # الملكية تُضاف ولا تُنقل (ق-79): الشركات الكبرى تحتاج
            # أكثر من مالك لئلا يتوقف كل شيء بغياب واحد.
            #
            # وأول مالك يُوسم مؤسسًا: لا تُنزع ملكيته إلا بحذفه
            # نهائيًا من الشركة، ويخلفه أقدم مالك بعده.
            first = not AccountMembership.objects.filter(
                account_id=me.account_id, is_account_owner=True).exists()
            target.is_account_owner = True
            target.is_founding_owner = first
            target.owner_since = timezone.now()
            target.save(update_fields=["is_account_owner",
                                       "is_founding_owner", "owner_since"])
        summary = f"مُنحت ملكية الحساب لـ{emp.person.display_name}"

    else:
        if not target.is_account_owner:
            return Response({"detail": "ليس مالكًا"}, status=400)

        if target.is_founding_owner:
            return Response(
                {"detail": "المالك المؤسس لا تُنزع ملكيته — تُنقل بحذفه "
                           "نهائيًا من الشركة",
                 "code": "founding_owner"}, status=400)

        others = AccountMembership.objects.filter(
            account_id=me.account_id, is_account_owner=True
        ).exclude(id=target.id).count()
        if others == 0:
            return Response(
                {"detail": "لا يُزال آخر مالك — امنح الملكية لغيره أولًا",
                 "code": "last_owner"}, status=400)

        target.is_account_owner = False
        target.owner_since = None
        target.save(update_fields=["is_account_owner", "owner_since"])
        summary = f"نُزعت ملكية الحساب عن {emp.person.display_name}"

    from apps.core.services.audit import log_action
    log_action(
        instance=target, action="update",
        actor=getattr(request.user, "person", None),
        label=emp.employee_no, summary=summary, channel="web")

    owners = AccountMembership.objects.filter(
        account_id=me.account_id, is_account_owner=True
    ).select_related("user").order_by("owner_since")

    return Response({
        "granted": bool(grant),
        "owners": [{"username": o.user.username,
                    "is_founding": o.is_founding_owner} for o in owners],
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_login(request, employment_id):
    """
    حذف حساب الدخول — لا الملف الوظيفي (ق-79).

    فالسجل لا يُمحى (ق-44): الموظف يبقى بملفه وطلباته وسجل
    عملياته، ويُنزع وصوله وحده.

    ولو كان مالكًا مؤسسًا خلفه أقدم مالك بعده. ولو زال الملاك
    جميعًا ناب مدير الموارد، فإن لم يكن فموظف الموارد — فلا يُترك
    حساب بلا من يديره.
    """
    from apps.accounts.models_access import (AccountMembership, Role,
                                             RoleAssignment)
    from apps.employees.models import Employment

    me = getattr(request.user, "account_membership", None)
    if me is None:
        return Response({"detail": "لا عضوية لحسابك"}, status=403)

    is_ceo = any(a.role.code == "ceo"
                 for a in me.role_assignments.select_related("role"))
    if not (me.is_account_owner or is_ceo):
        return Response(
            {"detail": "يحذف حسابات الدخول مالك الحساب أو المدير العام",
             "code": "not_allowed"}, status=403)

    # معزول ذاتيًا: مقيَّد بحساب المنفّذ نفسه
    emp = Employment.objects.filter(
        id=employment_id, account_id=me.account_id
    ).select_related("person__user").first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    user = getattr(emp.person, "user", None)
    target = getattr(user, "account_membership", None) if user else None
    if target is None:
        return Response({"detail": "لا حساب دخول لهذا الموظف"}, status=400)

    if target.id == me.id:
        return Response(
            {"detail": "لا تحذف حسابك بنفسك — اطلب من مالك آخر",
             "code": "self_delete"}, status=400)

    out = {}
    with transaction.atomic():
        was_owner = target.is_account_owner
        was_founding = target.is_founding_owner

        target.delete()      # العضوية وإسناداتها
        user.is_active = False
        user.save(update_fields=["is_active"])

        if was_owner:
            out.update(_reassign_ownership(me.account_id, was_founding))

    from apps.core.services.audit import log_action
    log_action(
        instance=emp, action="update",
        actor=getattr(request.user, "person", None),
        label=emp.employee_no,
        summary=(f"حُذف حساب دخول {emp.person.display_name}"
                 + (f" — {out['new_owner']} يخلفه في الملكية"
                    if out.get("new_owner") else "")),
        channel="web")

    return Response({"removed": True, **out})


def _reassign_ownership(account_id, was_founding):
    """
    يعيد توزيع الملكية بعد حذف مالك (ق-79).

    المؤسس يخلفه أقدم مالك بعده بنفس الحماية. وإن زال الملاك
    جميعًا ناب مدير الموارد، فإن لم يكن فموظف الموارد.
    """
    from apps.accounts.models_access import AccountMembership, RoleAssignment

    # معزول ذاتيًا: مقيَّد بالحساب المُمرَّر من مسار فحص صلاحيته
    remaining = AccountMembership.objects.filter(account_id=account_id, is_account_owner=True).order_by("owner_since")

    heir = remaining.first()
    if heir is not None:
        if was_founding and not remaining.filter(
                is_founding_owner=True).exists():
            heir.is_founding_owner = True
            heir.save(update_fields=["is_founding_owner"])
            return {"new_owner": heir.user.username,
                    "founding": True}
        return {}

    # لا مالك — الموارد ينوب (مديرها أولًا)
    for code in ("hr_manager", "hr_staff"):
        a = RoleAssignment.objects.filter(role__code=code, membership__account_id=account_id).select_related(
            "membership__user").order_by("id").first()
        if a is None:
            continue
        m = a.membership
        m.is_account_owner = True
        m.is_founding_owner = True
        m.owner_since = timezone.now()
        m.save(update_fields=["is_account_owner", "is_founding_owner",
                              "owner_since"])
        return {"new_owner": m.user.username, "founding": True,
                "by_fallback": code}

    return {"warning": "لا مالك ولا موارد — الحساب بلا سيطرة"}
