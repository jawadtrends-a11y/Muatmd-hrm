"""
حرّاس الحضور اللحظي والتقسيم، والاستثناء الشخصي (ق-67).

العلل التي تمنعها:
  1. اللوحة الشهرية كانت تقرأ AttendanceMonthlySummary — جدول
     ملخّص لم يُبنَ قط (صفر صفوف مقابل 4509 سجل يومي)، فتظهر
     «لا سجلات» دائمًا. والمدير يدخل في منتصف يوم العمل فيجب أن
     يرى بصمة اليوم فورًا لا بعد مهمة ليلية.
  2. العدّادات كانت تُحسب على الصفحة المعروضة بعد التقسيم —
     فـ«حاضر 20» تعني العشرين الظاهرين لا الشركة، وهو رقم مضلّل.
  3. سجل الموظف كان يُرجع كل أيامه بلا حد: موظف بعشرين سنة يعني
     سبعة آلاف صف في رد واحد.
  4. ق-67: الاستثناء الشخصي — مدير الحساب يزيد أو ينقص لموظف
     بعينه بلا تغيير دوره ولا التأثير على بقية أصحاب الدور.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (AccountMembership, PermissionOverride,
                                         Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay
from apps.core.access.catalog import Scope
from apps.core.access.gate import Gate
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person


@pytest.fixture
def env(db):
    """مدير موارد، وثلاثة موظفين بسجلات حضور في مارس."""
    r = provision_account(slug="live-b", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        u = User.objects.create_user(username="live.hr", password="x")
        role = Role.objects.get(account=acc, code="hr_manager")
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, role=role, company=comp, scope=Scope.COMPANY.value)

        # أسماء مختلفة تمامًا: حارس التشابه يرفض المتقاربة
        names = [("سعد", "القحطاني"), ("نايف", "الشمري"),
                 ("بدر", "العتيبي")]
        emps = []
        for i, (first, family) in enumerate(names):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA", id_type="national_id",
                id_number=f"10111222{i}0", mobile=f"05011122{i}0")
            e, _, _ = create_employment(person=p, company=comp,
                                        employee_no=f"E-{i}",
                                        join_date=date(2024, 1, 1))
            emps.append(e)

        # ثلاثة أيام حضور للموظف الأول: حاضر، حاضر بتأخير، غائب
        for d, status, late in ((2, "present", 0), (3, "present", 15),
                                (4, "absent", 0)):
            AttendanceDay.objects.create(
                account=acc, company=comp, employment=emps[0],
                work_date=date(2026, 3, d), status=status,
                late_minutes=late)

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "user": u, "membership": m, "emps": emps}


def _client(env):
    c = Client()
    c.force_login(env["user"])
    return c


@pytest.mark.django_db(transaction=True)
def test_monthly_board_computes_live(env):
    """
    الشهرية تُحتسب من سجلات الأيام لا من جدول ملخّص.

    كانت تقرأ AttendanceMonthlySummary الفارغ فتقول «لا سجلات»
    بينما آلاف السجلات اليومية موجودة.
    """
    d = _client(env).get("/api/attendance/monthly/?year=2026&month=3").json()

    row = next(r for r in d["rows"] if r["employee_no"] == "E-0")
    assert row["worked_days"] == "2", (
        f"أيام العمل تُقرأ من ملخّص فارغ لا من السجلات: {row}")
    assert row["absent_days"] == "1"
    assert row["late_minutes"] == 15


@pytest.mark.django_db(transaction=True)
def test_daily_board_counts_cover_whole_scope(env):
    """
    ⚠️ العدّادات تشمل النطاق كاملًا لا الصفحة المعروضة.

    «حاضر 20» يجب أن تعني الشركة، وإلا كان الرقم مضلّلًا لمن
    يقرأه — والرسالة تخبر بما حدث.
    """
    c = _client(env)
    full = c.get("/api/attendance/daily/?date=2026-03-02").json()
    paged = c.get(
        "/api/attendance/daily/?date=2026-03-02&page_size=1&page=1").json()

    assert len(paged["rows"]) == 1, "التقسيم لا يعمل"
    assert paged["total"] == full["total"], "المجموع تغيّر بتغيّر الصفحة"
    assert paged["counts"] == full["counts"], (
        "العدّادات تُحسب على الصفحة لا على النطاق — رقم مضلّل")


@pytest.mark.django_db(transaction=True)
def test_employee_record_is_paged_newest_first(env):
    """
    سجل الموظف مقسّم والأحدث أولًا.

    السجل متاح من تاريخ الالتحاق ولو كان قبل عشرين سنة — لكن لا
    يُجلب كاملًا في رد واحد.
    """
    emp = env["emps"][0]
    d = _client(env).get(
        f"/api/attendance/{emp.id}/days/?page_size=2").json()

    assert d["total"] == 3
    assert d["pages"] == 2
    assert len(d["rows"]) == 2, "التقسيم لا يعمل على سجل الموظف"
    assert d["rows"][0]["work_date"] > d["rows"][1]["work_date"], (
        "الترتيب ليس من الأحدث للأقدم")
    assert "join_date" in d, "تاريخ الالتحاق ناقص — به يُعرف مدى السجل"


@pytest.mark.django_db(transaction=True)
def test_personal_override_grants_wider_scope(env):
    """
    ق-67: الاستثناء الشخصي يوسّع نطاق صلاحية واحدة بلا تغيير الدور.

    الواقع المهني يكلّف موظفًا بمهمة إضافية بلا ترقية.
    """
    u = User.objects.create_user(username="live.emp", password="x")
    with account_scope(env["account_id"]):
        role = Role.objects.get(account=env["acc"], code="employee")
        m = AccountMembership.objects.create(
            user=u, account=env["acc"], active_company=env["comp"])
        RoleAssignment.objects.create(
            membership=m, role=role, company=env["comp"],
            scope=Scope.OWN.value)

        before = Gate.check(u, "attendance.view")
        assert before.scope is Scope.OWN

        PermissionOverride.objects.create(
            membership=m, company=env["comp"],
            permission_key="attendance.view", granted=True,
            scope=Scope.DEPARTMENT.value, note="حارس ق-67")

        after = Gate.check(u, "attendance.view")
        assert after.scope is Scope.DEPARTMENT, (
            "الاستثناء الشخصي لا يوسّع النطاق — ق-67 مكسور")
        assert [a.role.code for a in m.role_assignments.all()] == ["employee"], (
            "الدور تغيّر — والاستثناء يجب ألا يمسّه")


@pytest.mark.django_db(transaction=True)
def test_personal_override_can_revoke(env):
    """
    ق-67 بالاتجاه الآخر: النزع كما المنح.

    مدير الحساب قد يمنع مشرفًا من صلاحية يمنحها دوره.
    """
    u = User.objects.create_user(username="live.rev", password="x")
    with account_scope(env["account_id"]):
        role = Role.objects.get(account=env["acc"], code="hr_manager")
        m = AccountMembership.objects.create(
            user=u, account=env["acc"], active_company=env["comp"])
        RoleAssignment.objects.create(
            membership=m, role=role, company=env["comp"],
            scope=Scope.COMPANY.value)

        assert Gate.check(u, "attendance.view").allowed is True

        PermissionOverride.objects.create(
            membership=m, company=env["comp"],
            permission_key="attendance.view", granted=False,
            note="حارس النزع")

        d = Gate.check(u, "attendance.view")
        assert d.allowed is False, "النزع الشخصي لا يعمل"
