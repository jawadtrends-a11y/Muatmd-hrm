"""
الأدوار الافتراضية — قوالب تُنسخ لكل حساب.

المبدأ الحاكم (قرار المالك): النظام ينظّم ولا يصادر السلطة الإدارية.
كل شركة تملك نسختها وتعدّلها بحرية، ما عدا الحد الأدنى المحمي الذي
يمنع أن يقفل المالك الباب على نفسه.
"""
from django.db import transaction

from apps.accounts.models_access import Role, RoleCode, RolePermission
from apps.core.access.catalog import (
    PERMISSION_KEYS, PROTECTED_OWNER_PERMISSIONS, Scope, validate_keys,
)

DEFAULT_ROLES = {
    RoleCode.OWNER: {
        "name_ar": "مالك الحساب",
        "scope": Scope.ACCOUNT,
        "permissions": "*",
    },
    RoleCode.HR_MANAGER: {
        "name_ar": "مدير الموارد البشرية",
        "scope": Scope.COMPANY,
        "permissions": [
            "account.view", "company.view", "org.view", "org.manage",
            "employees.view", "employees.create", "employees.edit",
            "employees.terminate", "employees.documents",
            "attendance.view", "attendance.edit", "attendance.approve",
            "attendance.shifts",
            "leaves.view", "leaves.create", "leaves.approve", "leaves.manage",
            "requests.view", "requests.create", "requests.approve",
            "requests.manage",
            "payroll.view", "payroll.create", "payroll.submit",
            "payroll.approve", "payroll.export", "payroll.structures",
            "payslips.view_own", "payslips.view_team", "payslips.view_all",
            "saudization.view", "compliance.view",
            "access.view", "access.manage", "approvals.manage",
        ],
    },
    RoleCode.HR_STAFF: {
        "name_ar": "موظف موارد بشرية",
        "scope": Scope.COMPANY,
        # ينشئ المسير ويرفعه للاعتماد ويصدّره — ولا يعتمده.
        # مَن يعتمد وبكم درجة تحدده سلسلة الاعتماد لا هذا الدور.
        "permissions": [
            "company.view", "org.view",
            "employees.view", "employees.create", "employees.edit",
            "employees.documents",
            "attendance.view", "attendance.edit",
            "leaves.view", "leaves.create",
            "requests.view", "requests.create",
            "payroll.view", "payroll.create", "payroll.submit",
            "payroll.export",
            "payslips.view_own", "payslips.view_all",
            "compliance.view",
        ],
    },
    RoleCode.DEPT_MANAGER: {
        "name_ar": "مدير إدارة",
        "scope": Scope.DEPARTMENT,
        "permissions": [
            "org.view", "employees.view",
            "attendance.view", "attendance.approve",
            "leaves.view", "leaves.create", "leaves.approve",
            "requests.view", "requests.create", "requests.approve",
            "payslips.view_own", "payslips.view_team",
        ],
    },
    RoleCode.SUPERVISOR: {
        "name_ar": "مشرف",
        "scope": Scope.TEAM,
        # يرى قسائم مرؤوسيه بعد صدور المسير واعتماده فقط.
        "permissions": [
            "employees.view", "attendance.view",
            "leaves.view", "leaves.create", "leaves.approve",
            "requests.view", "requests.create", "requests.approve",
            "payslips.view_own", "payslips.view_team",
        ],
    },
    RoleCode.EMPLOYEE: {
        "name_ar": "موظف",
        "scope": Scope.OWN,
        "permissions": [
            "employees.view", "attendance.view",
            "leaves.view", "leaves.create",
            "requests.view", "requests.create",
            "payslips.view_own",
        ],
    },
}


def _keys_for(spec):
    return set(PERMISSION_KEYS) if spec["permissions"] == "*" else set(spec["permissions"])


@transaction.atomic
def provision_roles_for_account(account_id):
    """
    ينسخ الأدوار الافتراضية لحساب جديد. آمن للتكرار.
    النسخ لا المشاركة: تعديل شركة لا يمس غيرها.
    """
    created = []
    for code, spec in DEFAULT_ROLES.items():
        keys = _keys_for(spec)
        validate_keys(keys)
        role, is_new = Role.objects.get_or_create(
            account_id=account_id, code=code.value,
            defaults={
                "name_ar": spec["name_ar"],
                "default_scope": spec["scope"].value,
                "is_system": code == RoleCode.OWNER,
            },
        )
        if is_new:
            RolePermission.objects.bulk_create(
                [RolePermission(role=role, permission_key=k) for k in sorted(keys)]
            )
            created.append(code.value)
    return created


class ProtectedPermissionError(PermissionError):
    """محاولة نزع صلاحية من الحد الأدنى المحمي لدور المالك."""


@transaction.atomic
def set_role_permissions(role, permission_keys):
    """
    يضبط صلاحيات دور. الحد الأدنى المحمي يمنع قفل الحساب على صاحبه.
    ما عدا ذلك، كل شيء قابل للتعديل — النظام ينظّم ولا يصادر.
    """
    keys = set(permission_keys)
    validate_keys(keys)

    if role.code == RoleCode.OWNER.value:
        missing = PROTECTED_OWNER_PERMISSIONS - keys
        if missing:
            raise ProtectedPermissionError(
                "لا يمكن نزع هذه الصلاحيات من دور المالك: "
                + "، ".join(sorted(missing))
            )

    existing = set(role.permissions.values_list("permission_key", flat=True))
    RolePermission.objects.bulk_create(
        [RolePermission(role=role, permission_key=k) for k in sorted(keys - existing)]
    )
    role.permissions.filter(permission_key__in=existing - keys).delete()
    return sorted(keys)
