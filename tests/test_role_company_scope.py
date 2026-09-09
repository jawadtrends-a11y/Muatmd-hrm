"""
حارس ترشيح الأدوار بالشركة النشطة (ق-114).

⚠️ ثغرة أمنية كانت قائمة: البوابة تقرأ **كل** أدوار العضوية بلا
نظرٍ لأي شركة تخصّ — فمن هو «مدير موارد» في شركة و«موظف» في أخرى
كان يحمل صلاحيات المدير في الشركتين.
"""
import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.accounts.services.roles import provision_roles_for_account
from apps.core.access.catalog import Scope
from apps.core.access.gate import Gate
from apps.core.tenancy.context import account_scope


@pytest.fixture
def env(db):
    r = provision_account(slug="role-scope", display_name_ar="حساب",
                          company_name_ar="الأولى", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        c1 = Company.objects.get(id=r.company_id)
        c2 = Company.objects.create(account=acc, code="C2",
                                    legal_name_ar="الثانية")

        u = User.objects.create_user(username="two.co", password="Pw@2026xx")
        m = AccountMembership.objects.create(user=u, account=acc,
                                             active_company=c1)
        # مدير موارد في الأولى، وموظف في الثانية
        RoleAssignment.objects.create(
            membership=m, role=Role.objects.get(account=acc,
                                                code="hr_manager"),
            company=c1, scope=Scope.COMPANY.value)
        RoleAssignment.objects.create(
            membership=m, role=Role.objects.get(account=acc, code="employee"),
            company=c2, scope=Scope.OWN.value)
        yield {"account_id": r.account_id, "user": u, "m": m,
               "c1": c1, "c2": c2}


def test_role_applies_only_in_its_company(env):
    """
    ⚠️ الأهمّ: دور شركةٍ لا يسري في غيرها.

    فمن نشطت شركته الثانية (وهو فيها موظف) لا يحمل صلاحيات مدير
    الموارد التي له في الأولى.
    """
    u, m = env["user"], env["m"]

    with account_scope(env["account_id"]):
        # في الأولى: مدير موارد
        m.active_company = env["c1"]
        m.save(update_fields=["active_company"])
        u.refresh_from_db()
        assert Gate.check(u, "employees.view_all").allowed

        # في الثانية: موظف وحسب
        m.active_company = env["c2"]
        m.save(update_fields=["active_company"])
        u = User.objects.get(id=u.id)
        assert not Gate.check(u, "employees.view_all").allowed, (
            "دور الشركة الأولى سرى في الثانية — ثغرة")


def test_permission_set_follows_active_company(env):
    """وقائمة الصلاحيات كذلك — فالواجهة تُبنى منها."""
    u, m = env["user"], env["m"]

    with account_scope(env["account_id"]):
        m.active_company = env["c1"]
        m.save(update_fields=["active_company"])
        u = User.objects.get(id=u.id)
        many = Gate.accessible_permissions(u)

        m.active_company = env["c2"]
        m.save(update_fields=["active_company"])
        u = User.objects.get(id=u.id)
        few = Gate.accessible_permissions(u)

        assert len(few) < len(many), (
            f"لم تتقلّص الصلاحيات: {len(few)} مقابل {len(many)}")


def test_account_wide_role_applies_everywhere(env):
    """
    والدور بلا شركة عامٌّ على الحساب — كنمط الاستثناءات الشخصية.

    فالترشيح لا يُلغي الأدوار العامّة.
    """
    u, m = env["user"], env["m"]

    with account_scope(env["account_id"]):
        acc = Account.objects.get(id=env["account_id"])
        RoleAssignment.objects.create(
            membership=m, role=Role.objects.get(account=acc, code="ceo"),
            company=None, scope=Scope.ACCOUNT.value)

        for comp in (env["c1"], env["c2"]):
            m.active_company = comp
            m.save(update_fields=["active_company"])
            u = User.objects.get(id=u.id)
            assert Gate.check(u, "employees.view_all").allowed, (
                f"الدور العامّ لم يسرِ في {comp.code}")


# ══════════ الدور على التوظيف (ق-115) ══════════

@pytest.fixture
def emp_env(db):
    """موظف بتوظيفين في شركتين، ودورين مختلفين."""
    from apps.employees.services.hiring import (
        create_employment, create_person)
    from datetime import date

    r = provision_account(slug="role-emp", display_name_ar="حساب",
                          company_name_ar="الأولى", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        c1 = Company.objects.get(id=r.company_id)
        c2 = Company.objects.create(account=acc, code="C2",
                                    legal_name_ar="الثانية")

        u = User.objects.create_user(username="dual", password="Pw@2026xx")
        p, _ = create_person(
            account=acc, first_name_ar="خالد", family_name_ar="الزهراني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556", user=u)
        e1, _, _ = create_employment(person=p, company=c1,
                                     employee_no="D-1",
                                     join_date=date(2024, 1, 1))
        e2, _, _ = create_employment(person=p, company=c2,
                                     employee_no="D-2",
                                     join_date=date(2024, 1, 1))

        m = AccountMembership.objects.create(user=u, account=acc,
                                             active_company=c1)
        RoleAssignment.objects.create(
            membership=m, employment=e1,
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=c1, scope=Scope.COMPANY.value)
        RoleAssignment.objects.create(
            membership=m, employment=e2,
            role=Role.objects.get(account=acc, code="employee"),
            company=c2, scope=Scope.OWN.value)

        yield {"account_id": r.account_id, "user": u, "m": m,
               "c1": c1, "c2": c2, "e1": e1, "e2": e2}


def test_employment_role_is_scoped_to_its_company(emp_env):
    """
    ⚠️ الدور على التوظيف: من يعمل في شركتين له دوران مستقلّان.

    والشركة تأتي من التوظيف نفسه — فلا حقل يُنسى كما نُسي في
    ق-114.
    """
    u, m = emp_env["user"], emp_env["m"]
    with account_scope(emp_env["account_id"]):
        m.active_company = emp_env["c1"]
        m.save(update_fields=["active_company"])
        assert Gate.check(User.objects.get(id=u.id),
                          "employees.view_all").allowed

        m.active_company = emp_env["c2"]
        m.save(update_fields=["active_company"])
        assert not Gate.check(User.objects.get(id=u.id),
                              "employees.view_all").allowed


def test_terminated_employment_grants_nothing(emp_env):
    """
    ⚠️⚠️ **التوظيف المنتهي لا يمنح شيئًا**.

    فمن أُنهيت خدمته تُنزع صلاحياته فورًا بلا تدخّل — وبقاؤها
    يعني موظفًا مفصولًا يقرأ ملفّات زملائه.
    """
    from apps.employees.models import Employment, EmploymentStatus

    u, m = emp_env["user"], emp_env["m"]
    with account_scope(emp_env["account_id"]):
        m.active_company = emp_env["c1"]
        m.save(update_fields=["active_company"])
        assert Gate.check(User.objects.get(id=u.id),
                          "employees.view_all").allowed

        Employment.objects.filter(id=emp_env["e1"].id).update(
            status=EmploymentStatus.TERMINATED)

        assert not Gate.check(User.objects.get(id=u.id),
                              "employees.view_all").allowed, (
            "موظف مفصول ما زال يحمل صلاحياته")


def test_owner_without_employment_keeps_access(emp_env):
    """
    ومالك الحساب يعمل قبل أن يُضيف نفسه موظفًا.

    فإسناده بلا توظيف، ويُرشَّح بحقل الشركة كالسابق — ولولا ذلك
    لبقي المالك بلا صلاحيات حتى يوظّف نفسه.
    """
    with account_scope(emp_env["account_id"]):
        acc = Account.objects.get(id=emp_env["account_id"])
        u2 = User.objects.create_user(username="owner2", password="Pw@2026xx")
        m2 = AccountMembership.objects.create(
            user=u2, account=acc, active_company=emp_env["c1"],
            is_account_owner=False)
        RoleAssignment.objects.create(
            membership=m2, employment=None,
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=emp_env["c1"], scope=Scope.COMPANY.value)

        assert Gate.check(User.objects.get(id=u2.id),
                          "employees.view_all").allowed
