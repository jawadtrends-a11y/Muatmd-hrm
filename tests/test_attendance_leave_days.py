"""
حارس: من في إجازة معتمدة لا يُعدّ غائبًا.

⚠️ الفجوة التي يسدّها: معالجة الحضور كانت تمرّر is_on_leave=False
ثابتة، فمن في إجازة سنوية ولم يبصم يُسجَّل ABSENT — والمسير يقرأ
الغياب من ملخّص الحضور، فيُخصم من راتبه أجر يوم هو إجازة مأذونة.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.core.access.catalog import Scope
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay, DayStatus
from apps.attendance.services.processing import process_employment_days
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import Request, RequestStatus, RequestType
from apps.leaves.services.leave_requests import leave_dates_in_range
from apps.organization.services.structure import create_holiday


@pytest.fixture
def env(db):
    r = provision_account(slug="att-lv", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="الغامدي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077788899", mobile="0507778889")
        emp, _, _ = create_employment(person=p, company=comp,
                                      employee_no="A-1",
                                      join_date=date(2024, 1, 1))

        # مدير موارد ليُفتح به لوح الحضور عبر HTTP
        u = User.objects.create_user(username="att.hr", password="Pw@2026xx")
        m = AccountMembership.objects.create(user=u, account=acc,
                                             active_company=comp)
        RoleAssignment.objects.create(
            membership=m, role=Role.objects.get(account=acc,
                                                code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)
        hp, _ = create_person(
            account=acc, first_name_ar="هدى", family_name_ar="القحطاني",
            gender="female", nationality_code="SA", id_type="national_id",
            id_number="1066677788", mobile="0506667778", user=u)
        create_employment(person=hp, company=comp, employee_no="A-HR",
                          join_date=date(2024, 1, 1))

        yield {"account_id": r.account_id, "company": comp,
               "employment": emp}


def _approved_leave(emp, start, end, applied=True):
    return Request.objects.create(
        account=emp.account, company=emp.company, employment=emp,
        request_no=f"LV-{start}", request_type=RequestType.LEAVE,
        status=RequestStatus.APPROVED,
        payload={"start_date": str(start), "end_date": str(end),
                 "applied": applied, "is_paid": True})


def test_approved_leave_is_not_absence(env):
    """⚠️ الأهمّ: يوم الإجازة حالته LEAVE لا ABSENT."""
    emp = env["employment"]
    with account_scope(env["account_id"]):
        _approved_leave(emp, date(2026, 3, 2), date(2026, 3, 4))
        process_employment_days(employment=emp,
                                start_date=date(2026, 3, 1),
                                end_date=date(2026, 3, 5), force=True)
        for d in (date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4)):
            a = AttendanceDay.objects.get(employment=emp, work_date=d)
            assert a.status == DayStatus.LEAVE, \
                f"{d} سُجّل {a.status} لا إجازة — يُخصم من راتبه"


def test_unapplied_leave_is_ignored(env):
    """المعتمد غير المطبَّق لا يعلّم حضورًا — التطبيق قرار مستقلّ."""
    emp = env["employment"]
    with account_scope(env["account_id"]):
        _approved_leave(emp, date(2026, 4, 6), date(2026, 4, 7),
                        applied=False)
        days = leave_dates_in_range(emp, date(2026, 4, 1),
                                    date(2026, 4, 30))
        assert days == set()


def test_holiday_is_not_absence(env):
    """يوم العطلة حالته HOLIDAY."""
    emp = env["employment"]
    with account_scope(env["account_id"]):
        create_holiday(company=env["company"], name_ar="اليوم الوطني",
                       start_date=date(2026, 9, 23),
                       end_date=date(2026, 9, 26))
        process_employment_days(employment=emp,
                                start_date=date(2026, 9, 23),
                                end_date=date(2026, 9, 26), force=True)
        for d in (date(2026, 9, 23), date(2026, 9, 26)):
            a = AttendanceDay.objects.get(employment=emp, work_date=d)
            assert a.status == DayStatus.HOLIDAY


def test_holiday_accepts_string_dates(env):
    """
    التواريخ تصل نصوصًا من الـAPI — وكانت تكسر المقارنة بـ500
    ثم تفشل في احتساب days بعد الحفظ.
    """
    with account_scope(env["account_id"]):
        h = create_holiday(company=env["company"], name_ar="عيد الفطر",
                           start_date="2026-04-20", end_date="2026-04-23")
        assert h.days == 4


def test_daily_board_shows_calendar_status(env):
    """
    يوم بلا بصمة يُعرض بحقيقته: عطلة أو راحة أو إجازة.

    وعرضه «لا سجل» يُخفي الحقيقة ويُقلق المدير بلا سبب — فسجلّ
    الحضور لا يُنشأ ليوم لا بصمة فيه أصلًا.
    """
    from django.test import Client

    emp = env["employment"]
    with account_scope(env["account_id"]):
        create_holiday(company=env["company"], name_ar="عيد",
                       start_date=date(2026, 5, 10),
                       end_date=date(2026, 5, 12))

    c = Client()
    r = c.post("/api/auth/login/",
               data={"identifier": "att.hr", "password": "Pw@2026xx"},
               content_type="application/json")
    assert r.status_code == 200, r.content
    c = Client(HTTP_AUTHORIZATION="Bearer " + r.json()["token"])
    rr = c.get("/api/attendance/daily/?date=2026-05-11")
    assert rr.status_code == 200
    labels = {x["status_label"] for x in rr.json()["rows"]}
    assert "عطلة" in labels, f"ظهر: {labels}"
