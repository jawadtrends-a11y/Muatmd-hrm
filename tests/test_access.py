"""حرّاس بوابة الصلاحيات والأدوار."""
import pytest

from apps.accounts.models_access import Role, RoleCode
from apps.accounts.services.provisioning import provision_account
from apps.accounts.services.roles import (
    DEFAULT_ROLES, ProtectedPermissionError, set_role_permissions,
)
from apps.core.access.catalog import (
    PERMISSION_KEYS, PROTECTED_OWNER_PERMISSIONS, Scope,
)
from apps.core.access.gate import Gate, UnknownPermission
from apps.core.tenancy.context import account_scope


@pytest.fixture
def account(db):
    return provision_account(
        slug="gate-test", display_name_ar="حساب اختبار",
        company_name_ar="شركة اختبار", is_sandbox=True,
    )


@pytest.mark.django_db(transaction=True)
def test_every_account_gets_default_roles(account):
    """
    كل حساب يُهيَّأ بالأدوار السبعة (ق-76: المدير العام دور وظيفي
    منفصل عن مالك الحساب).
    """
    from apps.accounts.services.roles import DEFAULT_ROLES

    with account_scope(account.account_id):
        codes = set(Role.objects.filter(
            account_id=account.account_id).values_list("code", flat=True))
    want = {c.value for c in DEFAULT_ROLES}
    assert codes == want, f"ناقص: {want - codes} | زائد: {codes - want}"


@pytest.mark.django_db(transaction=True)
def test_roles_are_per_account_not_shared(account):
    """تعديل دور في حساب لا يمس نفس الدور في حساب آخر."""
    other = provision_account(
        slug="gate-test-2", display_name_ar="حساب ثانٍ",
        company_name_ar="شركة ثانية", is_sandbox=True,
    )
    with account_scope(account.account_id):
        r = Role.objects.get(account_id=account.account_id, code="employee")
        set_role_permissions(r, ["employees.view"])
    with account_scope(other.account_id):
        r2 = Role.objects.get(account_id=other.account_id, code="employee")
        assert len(r2.permission_keys) > 1, "التعديل تسرّب بين الحسابات"


@pytest.mark.django_db(transaction=True)
def test_owner_protected_permissions_cannot_be_removed(account):
    with account_scope(account.account_id):
        owner = Role.objects.get(account_id=account.account_id, code="owner")
        with pytest.raises(ProtectedPermissionError):
            set_role_permissions(owner, ["employees.view"])


@pytest.mark.django_db(transaction=True)
def test_non_owner_roles_fully_editable(account):
    """النظام ينظّم ولا يصادر — أي دور غير المالك قابل للتعديل الكامل."""
    with account_scope(account.account_id):
        for code in ("hr_manager", "hr_staff", "supervisor", "employee"):
            r = Role.objects.get(account_id=account.account_id, code=code)
            set_role_permissions(r, ["employees.view"])
            r.refresh_from_db()
            assert r.permission_keys == {"employees.view"}


@pytest.mark.django_db
def test_gate_rejects_unknown_permission():
    class Anon:
        is_authenticated = False
    with pytest.raises(UnknownPermission):
        Gate.check(Anon(), "not.registered")


@pytest.mark.django_db
def test_gate_denies_anonymous():
    class Anon:
        is_authenticated = False
    d = Gate.check(Anon(), "employees.view")
    assert not d.allowed and d.scope is Scope.OWN


@pytest.mark.django_db
def test_default_roles_use_registered_permissions_only():
    """لا صلاحية في أي دور افتراضي خارج الكتالوج."""
    for code, spec in DEFAULT_ROLES.items():
        keys = PERMISSION_KEYS if spec["permissions"] == "*" else set(spec["permissions"])
        unknown = keys - PERMISSION_KEYS
        assert not unknown, f"{code}: صلاحيات غير مسجّلة {unknown}"


@pytest.mark.django_db
def test_hr_staff_cannot_approve_payroll():
    """قرار المالك: موظف الموارد ينشئ ويرفع ولا يعتمد."""
    keys = set(DEFAULT_ROLES[RoleCode.HR_STAFF]["permissions"])
    assert "payroll.create" in keys
    assert "payroll.submit" in keys
    assert "payroll.approve" not in keys


@pytest.mark.django_db
def test_supervisor_sees_team_payslips():
    """قرار المالك: المشرف يرى قسائم مرؤوسيه بعد الاعتماد."""
    keys = set(DEFAULT_ROLES[RoleCode.SUPERVISOR]["permissions"])
    assert "payslips.view_team" in keys
    assert "payroll.structures" not in keys
