"""حرّاس دورة طلب الإجازة وأثرها على الحضور (ق-32، ق-33)."""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay, DayStatus, Shift, ShiftAssignment
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import ApprovalDecision, LeaveType, RequestStatus
from apps.leaves.services.approvals import decide
from apps.leaves.services.balances import LeaveError, accrue
from apps.leaves.services.leave_requests import (
    apply_approved_leave, create_leave_request, unpaid_leave_days_in_period,
)
from apps.organization.services.structure import create_holiday


@pytest.fixture
def env(db):
    r = provision_account(slug="lvr-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        pm, _ = create_person(
            account=acc, first_name_ar="خالد", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011122233", mobile="0501112223")
        mgr, _, _ = create_employment(person=pm, company=comp,
                                       employee_no="M-1",
                                       join_date=date(2019, 1, 1))
        pe, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556")
        emp, _, _ = create_employment(person=pe, company=comp,
                                       employee_no="E-1",
                                       join_date=date(2020, 1, 1),
                                       direct_manager=mgr)
        sh = Shift.objects.create(
            account=acc, company=comp, code="DAY", name_ar="صباحي",
            start_time="08:00", end_time="16:00", working_days=[0, 1, 2, 3, 4])
        ShiftAssignment.objects.create(account=acc, company=comp,
                                       employment=emp, shift=sh,
                                       effective_from=date(2020, 1, 1))
        annual = LeaveType.objects.get(company=comp, code="ANNUAL")
        accrue(emp, annual, as_of=date(2026, 12, 31))
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "mgr": mgr, "emp": emp, "annual": annual,
               "unpaid": LeaveType.objects.get(company=comp, code="UNPAID")}


def _approve_and_apply(env, req):
    approved = decide(request_obj=req, approver_employment=env["mgr"],
                      decision=ApprovalDecision.APPROVED)
    return approved, apply_approved_leave(approved)


@pytest.mark.django_db(transaction=True)
def test_leave_extends_over_holidays(env):
    """ق-33: العطل تُمدّد الإجازة ولا تُخصم."""
    with account_scope(env["account_id"]):
        create_holiday(company=env["comp"], name_ar="عيد",
                       start_date=date(2026, 4, 5), end_date=date(2026, 4, 8))
        res = create_leave_request(
            employment=env["emp"], leave_type_code="ANNUAL",
            start_date=date(2026, 4, 1), requested_days=5)
        assert res.charged_days == D("5")
        assert res.extended_days == 4
        assert res.end_date == date(2026, 4, 9)


@pytest.mark.django_db(transaction=True)
def test_overlapping_leave_blocked(env):
    with account_scope(env["account_id"]):
        create_leave_request(employment=env["emp"], leave_type_code="ANNUAL",
                             start_date=date(2026, 4, 1), requested_days=5)
        with pytest.raises(LeaveError):
            create_leave_request(employment=env["emp"],
                                 leave_type_code="ANNUAL",
                                 start_date=date(2026, 4, 3),
                                 requested_days=2)


@pytest.mark.django_db(transaction=True)
def test_leave_days_marked_as_leave_not_absent(env):
    """
    ق-32: يوم الإجازة لا يُحتسب غيابًا — الغياب مخالفة والإجازة
    حق مأذون.
    """
    with account_scope(env["account_id"]):
        res = create_leave_request(
            employment=env["emp"], leave_type_code="ANNUAL",
            start_date=date(2026, 4, 1), requested_days=3)
        _approve_and_apply(env, res.request)

        days = AttendanceDay.objects.filter(employment=env["emp"])
        assert days.count() == 3
        assert all(d.status == DayStatus.LEAVE for d in days)
        assert not days.filter(status=DayStatus.ABSENT).exists()


@pytest.mark.django_db(transaction=True)
def test_extended_holiday_days_not_marked_as_leave(env):
    """الأيام المُمدَّدة امتداد لا إجازة — لا تُعلَّم ولا تُخصم."""
    with account_scope(env["account_id"]):
        create_holiday(company=env["comp"], name_ar="عيد",
                       start_date=date(2026, 4, 5), end_date=date(2026, 4, 8))
        res = create_leave_request(
            employment=env["emp"], leave_type_code="ANNUAL",
            start_date=date(2026, 4, 1), requested_days=5)
        _, applied = _approve_and_apply(env, res.request)
        assert applied["attendance_days_marked"] == 5
        for d in (date(2026, 4, 5), date(2026, 4, 8)):
            assert not AttendanceDay.objects.filter(
                employment=env["emp"], work_date=d,
                status=DayStatus.LEAVE).exists()


@pytest.mark.django_db(transaction=True)
def test_balance_consumed_on_apply(env):
    with account_scope(env["account_id"]):
        res = create_leave_request(
            employment=env["emp"], leave_type_code="ANNUAL",
            start_date=date(2026, 4, 1), requested_days=4)
        _, applied = _approve_and_apply(env, res.request)
        assert applied["consumed_days"] == "4"


@pytest.mark.django_db(transaction=True)
def test_unpaid_leave_warns_and_counts_for_deduction(env):
    """
    ق-32: الإجازة بلا أجر لا تُحتسب غيابًا لكن يُخصم أجر الأيام.
    """
    with account_scope(env["account_id"]):
        res = create_leave_request(
            employment=env["emp"], leave_type_code="UNPAID",
            start_date=date(2026, 5, 4), requested_days=3)
        assert res.warnings and "بلا أجر" in res.warnings[0]

        _, applied = _approve_and_apply(env, res.request)
        assert applied["is_paid"] is False

        days = AttendanceDay.objects.filter(employment=env["emp"])
        assert all(d.status == DayStatus.LEAVE for d in days), \
            "الإجازة بلا أجر عُلّمت غيابًا"

        assert unpaid_leave_days_in_period(env["emp"], 2026, 5) == D("3")


@pytest.mark.django_db(transaction=True)
def test_paid_leave_not_counted_for_deduction(env):
    """الإجازة المدفوعة لا تُخصم من الراتب."""
    with account_scope(env["account_id"]):
        res = create_leave_request(
            employment=env["emp"], leave_type_code="ANNUAL",
            start_date=date(2026, 5, 4), requested_days=3)
        _approve_and_apply(env, res.request)
        assert unpaid_leave_days_in_period(env["emp"], 2026, 5) == D("0")


@pytest.mark.django_db(transaction=True)
def test_apply_is_idempotent(env):
    with account_scope(env["account_id"]):
        res = create_leave_request(
            employment=env["emp"], leave_type_code="ANNUAL",
            start_date=date(2026, 4, 1), requested_days=3)
        approved, _ = _approve_and_apply(env, res.request)
        second = apply_approved_leave(approved)
        assert second.get("already_applied") is True


@pytest.mark.django_db(transaction=True)
def test_cannot_apply_unapproved_request(env):
    with account_scope(env["account_id"]):
        res = create_leave_request(
            employment=env["emp"], leave_type_code="ANNUAL",
            start_date=date(2026, 4, 1), requested_days=3)
        assert res.request.status == RequestStatus.PENDING
        with pytest.raises(LeaveError):
            apply_approved_leave(res.request)


@pytest.mark.django_db(transaction=True)
def test_attachment_required_for_sick_leave(env):
    with account_scope(env["account_id"]):
        with pytest.raises(LeaveError):
            create_leave_request(
                employment=env["emp"], leave_type_code="SICK",
                start_date=date(2026, 4, 1), requested_days=3)


@pytest.mark.django_db(transaction=True)
def test_ineligible_leave_rejected(env):
    """العدّة للإناث — الذكر يُرفض عند التقديم."""
    with account_scope(env["account_id"]):
        with pytest.raises(LeaveError):
            create_leave_request(
                employment=env["emp"], leave_type_code="IDDAH",
                start_date=date(2026, 4, 1), requested_days=10)
