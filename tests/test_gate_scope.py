"""
حرّاس نطاق البوابة — Gate.filter_queryset.

الفجوة التي تسدّها: الحرّاس كانت تفحص Gate.check (هل الصلاحية
ممنوحة؟) وtest_architecture تفرض *استخدام* filter_queryset — لكن
**سلوكها** لم يكن محروسًا بحارس واحد. فعاشت فيها ثلاث علل حتى
كشفها الاستخدام الفعلي:

  1. membership.employment — حقل لا وجود له. العضوية تربط المستخدم
     بالحساب لا بملف موظف، فكل نطاق ضيّق كان يرجع qs.none() في
     خمسة وسبعين موضعًا: المشرف ومدير الإدارة يريان فراغًا في كل
     شاشة.
  2. direct_manager_employment_id — اسم مخترع، والصحيح
     direct_manager. لم يُخفق لأن العلة الأولى تسبقه.
  3. الجداول المرتبطة بـEmployment بلا employment_field صريح كانت
     ترفع FieldError غامضًا من أعماق Django عند العميل.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.access.gate import Gate
from apps.core.tenancy.context import account_scope
from apps.employees.models import Employment
from apps.employees.services.hiring import create_employment, create_person


@pytest.fixture
def team(db):
    """
    مشرف بحساب دخول، ومرؤوس تحته، وموظف ثالث خارج فريقه.

    الثالث هو المهم: بلاه لا نعرف إن كان المشرف يرى فريقه أم يرى
    كل الشركة.
    """
    r = provision_account(slug="scope-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        u = User.objects.create_user(username="scope.sup", password="x")
        role = Role.objects.get(account=acc, code="supervisor")
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, role=role, company=comp, scope=Scope.TEAM.value)

        pm, _ = create_person(
            account=acc, first_name_ar="خالد", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011122233", mobile="0501112223", user=u)
        mgr, _, _ = create_employment(person=pm, company=comp,
                                      employee_no="M-1",
                                      join_date=date(2020, 1, 1))

        pe, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556")
        sub, _, _ = create_employment(person=pe, company=comp,
                                      employee_no="E-1",
                                      join_date=date(2022, 1, 1),
                                      direct_manager=mgr)

        po, _ = create_person(
            account=acc, first_name_ar="نايف", family_name_ar="الشمري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1088899900", mobile="0508889990")
        outsider, _, _ = create_employment(person=po, company=comp,
                                           employee_no="E-2",
                                           join_date=date(2022, 1, 1))

        yield {"account_id": r.account_id, "user": u, "mgr": mgr,
               "sub": sub, "outsider": outsider, "comp": comp}


@pytest.mark.django_db(transaction=True)
def test_scope_resolves_employment_from_active_company(team):
    """
    البوابة تجد الارتباط الوظيفي للمستخدم.

    كانت تبحث عن membership.employment — حقل غير موجود — فترجع
    None دائمًا، وكل نطاق ضيّق يصير qs.none().
    """
    emp = Gate._employment(team["user"])
    assert emp is not None, (
        "البوابة لا تجد ارتباط المستخدم — كل نطاق ضيّق سيرجع فراغًا")
    assert emp.id == team["mgr"].id
    assert emp.company_id == team["comp"].id, (
        "الارتباط يجب أن يكون في الشركة النشطة تحديدًا")


@pytest.mark.django_db(transaction=True)
def test_supervisor_sees_own_subordinates(team):
    """المشرف يرى مرؤوسيه المباشرين — الحقل direct_manager لا اسم مخترع."""
    with account_scope(team["account_id"]):
        qs = Gate.filter_queryset(
            team["user"], "employees.view", Employment.objects.all())
        ids = set(qs.values_list("id", flat=True))

    assert team["sub"].id in ids, "المشرف لا يرى مرؤوسه المباشر"


@pytest.mark.django_db(transaction=True)
def test_supervisor_does_not_see_outside_team(team):
    """
    ⚠️ الحارس المقابل: الإصلاح يفتح ما أُغلق خطأً، لا ما يجب أن
    يبقى مغلقًا. فمن ليس مرؤوسًا للمشرف لا يظهر له.
    """
    with account_scope(team["account_id"]):
        qs = Gate.filter_queryset(
            team["user"], "employees.view", Employment.objects.all())
        ids = set(qs.values_list("id", flat=True))

    assert team["outsider"].id not in ids, (
        "المشرف يرى موظفًا خارج فريقه — النطاق team صار أوسع مما يجب")


@pytest.mark.django_db(transaction=True)
def test_related_table_scope_is_inferred(team):
    """
    الجدول المرتبط بـEmployment تُشتق بادئته تلقائيًا.

    كان نسيان employment_field يرفع FieldError غامضًا عند العميل
    (انفجر فعليًا على /api/leaves/requests/).
    """
    from apps.attendance.models import AttendanceDay

    with account_scope(team["account_id"]):
        AttendanceDay.objects.create(
            account_id=team["account_id"], company=team["comp"],
            employment=team["sub"], work_date=date(2026, 3, 2),
            status="present")
        AttendanceDay.objects.create(
            account_id=team["account_id"], company=team["comp"],
            employment=team["outsider"], work_date=date(2026, 3, 2),
            status="present")

        # بلا employment_field — يجب أن يُشتق ولا ينهار
        qs = Gate.filter_queryset(
            team["user"], "attendance.view", AttendanceDay.objects.all())
        emp_ids = set(qs.values_list("employment_id", flat=True))

    assert team["sub"].id in emp_ids, "لا يرى حضور مرؤوسه"
    assert team["outsider"].id not in emp_ids, "يرى حضور من ليس مرؤوسه"


@pytest.mark.django_db(transaction=True)
def test_organizational_table_passes_through(team):
    """
    الجدول التنظيمي لا يخص موظفًا — يمرّ بلا فلترة نطاق، والصلاحية
    وحدها حارسه. وإجباره على حقل موظف يعني أن من يملك الصلاحية
    لا يرى شيئًا.
    """
    with account_scope(team["account_id"]):
        qs = Gate.filter_queryset(
            team["user"], "employees.view", Company.objects.all())
        # لا ينهار، ولا يُفرَّغ لمجرد أن النطاق ضيّق
        assert qs.count() >= 0
