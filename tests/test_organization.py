"""حرّاس الهيكل التنظيمي."""
from datetime import date

import pytest

from apps.accounts.models import Company
from apps.accounts.services.plans import sync_default_plans, sync_feature_registry
from apps.accounts.services.provisioning import provision_account
from apps.accounts.services.subscriptions import subscribe_company
from apps.core.tenancy.context import account_scope
from apps.organization.models import Branch, Department, Holiday
from apps.organization.services.structure import (
    LimitExceeded, StructureError, create_branch, create_department,
    create_holiday, department_tree, holidays_in_range, move_department,
)


@pytest.fixture
def company(db):
    sync_feature_registry()
    sync_default_plans()
    acct = provision_account(
        slug="org-test", display_name_ar="حساب الهيكل",
        company_name_ar="شركة الهيكل", is_sandbox=True,
    )
    with account_scope(acct.account_id):
        return Company.objects.get(id=acct.company_id)


@pytest.mark.django_db(transaction=True)
def test_branch_limit_from_plan(company):
    """حد الفروع يأتي من الباقة لا من الكود."""
    with account_scope(company.account_id):
        subscribe_company(company=company, plan_code="basic")   # حد 2
        create_branch(company=company, code="B1", name_ar="فرع ١")
        create_branch(company=company, code="B2", name_ar="فرع ٢")
        with pytest.raises(LimitExceeded) as exc:
            create_branch(company=company, code="B3", name_ar="فرع ٣")
        assert exc.value.limit == 2


@pytest.mark.django_db(transaction=True)
def test_enterprise_has_no_branch_limit(company):
    """الباقة المؤسسية: max_branches=0 يعني بلا حد."""
    with account_scope(company.account_id):
        subscribe_company(company=company, plan_code="enterprise")
        for i in range(5):
            create_branch(company=company, code=f"B{i}", name_ar=f"فرع {i}")
        assert Branch.objects.filter(company=company).count() == 5


@pytest.mark.django_db(transaction=True)
def test_department_path_built_automatically(company):
    with account_scope(company.account_id):
        root = create_department(company=company, code="R", name_ar="جذر")
        mid = create_department(company=company, code="M", name_ar="وسط", parent=root)
        leaf = create_department(company=company, code="L", name_ar="ورقة", parent=mid)
        assert root.path == str(root.id)
        assert mid.path == f"{root.id}/{mid.id}"
        assert leaf.path == f"{root.id}/{mid.id}/{leaf.id}"
        assert (root.depth, mid.depth, leaf.depth) == (0, 1, 2)


@pytest.mark.django_db(transaction=True)
def test_descendants_single_query(company):
    with account_scope(company.account_id):
        root = create_department(company=company, code="R", name_ar="جذر")
        a = create_department(company=company, code="A", name_ar="أ", parent=root)
        create_department(company=company, code="B", name_ar="ب", parent=a)
        create_department(company=company, code="C", name_ar="ج", parent=root)
        assert root.descendants.count() == 3
        assert a.descendants.count() == 1


@pytest.mark.django_db(transaction=True)
def test_move_department_updates_child_paths(company):
    """نقل قسم يُحدّث مسارات كل أبنائه — وإلا انكسرت الشجرة."""
    with account_scope(company.account_id):
        r1 = create_department(company=company, code="R1", name_ar="جذر١")
        r2 = create_department(company=company, code="R2", name_ar="جذر٢")
        child = create_department(company=company, code="C", name_ar="ابن", parent=r1)
        grand = create_department(company=company, code="G", name_ar="حفيد", parent=child)

        move_department(department=child, new_parent=r2)
        child.refresh_from_db()
        grand.refresh_from_db()
        assert child.path == f"{r2.id}/{child.id}"
        assert grand.path == f"{r2.id}/{child.id}/{grand.id}"
        assert grand.depth == 2


@pytest.mark.django_db(transaction=True)
def test_move_prevents_cycle(company):
    with account_scope(company.account_id):
        root = create_department(company=company, code="R", name_ar="جذر")
        child = create_department(company=company, code="C", name_ar="ابن", parent=root)
        with pytest.raises(StructureError):
            move_department(department=root, new_parent=child)
        with pytest.raises(StructureError):
            move_department(department=root, new_parent=root)


@pytest.mark.django_db(transaction=True)
def test_holiday_overlap_rejected(company):
    with account_scope(company.account_id):
        create_holiday(company=company, name_ar="عطلة",
                       start_date=date(2027, 5, 1), end_date=date(2027, 5, 5))
        with pytest.raises(StructureError):
            create_holiday(company=company, name_ar="متداخلة",
                           start_date=date(2027, 5, 4), end_date=date(2027, 5, 8))


@pytest.mark.django_db(transaction=True)
def test_holiday_days_count(company):
    with account_scope(company.account_id):
        h = create_holiday(company=company, name_ar="عيد",
                           start_date=date(2027, 5, 1), end_date=date(2027, 5, 7))
        assert h.days == 7


@pytest.mark.django_db(transaction=True)
def test_no_platform_holiday_table():
    """
    قرار المالك: العطل تديرها الشركة وحدها.
    لا يجوز وجود جدول عطل على مستوى المنصة.
    """
    from django.apps import apps as dj_apps
    names = {m.__name__ for m in dj_apps.get_models()
             if m._meta.app_label == "organization"}
    assert "PublicHoliday" not in names, "عاد جدول عطل المنصة — مخالف لقرار المالك"
    h = Holiday._meta.get_field("company")
    assert not h.null, "العطلة يجب أن تكون مرتبطة بشركة إلزاميًا"


@pytest.mark.django_db(transaction=True)
def test_org_isolated_between_accounts(company, rls_enforced_late):
    other = provision_account(
        slug="org-other", display_name_ar="آخر",
        company_name_ar="شركة أخرى", is_sandbox=True,
    )
    with account_scope(company.account_id):
        subscribe_company(company=company, plan_code="enterprise")
        create_branch(company=company, code="X", name_ar="فرع")
        create_department(company=company, code="D", name_ar="قسم")

    rls_enforced_late()
    with account_scope(other.account_id):
        assert Branch.objects.count() == 0, "تسريب فروع بين الحسابات"
        assert Department.objects.count() == 0, "تسريب أقسام بين الحسابات"
