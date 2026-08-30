"""حرّاس API الحضور."""
import json
from datetime import date, datetime

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay, Shift, ShiftAssignment
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person

TZ = timezone.get_current_timezone()


def _iso(d, h, m=0):
    return timezone.make_aware(datetime(2026, 3, d, h, m), TZ).isoformat()


@pytest.fixture
def env(db):
    r = provision_account(slug="attapi", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        c1 = Company.objects.get(id=r.company_id)
        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077788899", mobile="0507778889")
        e, _, _ = create_employment(person=p, company=c1, employee_no="A-1",
                                    join_date=date(2024, 1, 1))
        shift = Shift.objects.create(
            account=acc, company=c1, code="DAY", name_ar="صباحي",
            start_time="08:00", end_time="16:00", break_minutes=60,
            grace_in_minutes=15, working_days=[0, 1, 2, 3, 4])
        ShiftAssignment.objects.create(
            account=acc, company=c1, employment=e, shift=shift,
            effective_from=date(2024, 1, 1))
        yield {"account_id": r.account_id, "acc": acc, "c1": c1,
               "person": p, "emp": e}


def _client(env, role_code, scope=Scope.COMPANY, username="u"):
    u = User.objects.create_user(username=username, password="x")
    with account_scope(env["account_id"]):
        role = Role.objects.get(account_id=env["account_id"], code=role_code)
        m = AccountMembership.objects.create(
            user=u, account_id=env["account_id"], active_company=env["c1"])
        RoleAssignment.objects.create(membership=m, role=role,
                                      company=env["c1"], scope=scope.value)
    c = Client()
    c.force_login(u)
    return c


def _post(c, url, d):
    return c.post(url, data=json.dumps(d), content_type="application/json")


def _put(c, url, d):
    return c.put(url, data=json.dumps(d), content_type="application/json")


@pytest.mark.django_db(transaction=True)
def test_punch_and_process(env):
    c = _client(env, "hr_manager")
    emp_id = env["emp"].id
    for h, ref in ((8, "x1"), (16, "x2")):
        r = _post(c, "/api/attendance/punch/", {
            "employment_id": emp_id, "punched_at": _iso(2, h),
            "source": "device", "external_ref": ref})
        assert r.status_code == 201

    r = _post(c, f"/api/attendance/{emp_id}/days/",
              {"from": "2026-03-02", "to": "2026-03-02"})
    assert r.json()["punches_read"] == 2

    days = c.get(f"/api/attendance/{emp_id}/days/"
                 "?from=2026-03-02&to=2026-03-02").json()
    assert days[0]["status"] == "present"
    assert days[0]["worked_minutes"] == 420


@pytest.mark.django_db(transaction=True)
def test_duplicate_punch_returns_200_not_created(env):
    c = _client(env, "hr_manager")
    emp_id = env["emp"].id
    payload = {"employment_id": emp_id, "punched_at": _iso(2, 8),
               "source": "device", "external_ref": "dup"}
    assert _post(c, "/api/attendance/punch/", payload).status_code == 201
    r = _post(c, "/api/attendance/punch/", payload)
    assert r.status_code == 200
    assert r.json()["created"] is False


@pytest.mark.django_db(transaction=True)
def test_overtime_needs_approval(env):
    c = _client(env, "hr_manager")
    emp_id = env["emp"].id
    for h, ref in ((8, "o1"), (19, "o2")):
        _post(c, "/api/attendance/punch/", {
            "employment_id": emp_id, "punched_at": _iso(5, h),
            "source": "device", "external_ref": ref})
    _post(c, f"/api/attendance/{emp_id}/days/",
          {"from": "2026-03-05", "to": "2026-03-05"})

    day = c.get(f"/api/attendance/{emp_id}/days/"
                "?from=2026-03-05&to=2026-03-05").json()[0]
    assert day["overtime_minutes"] == 180
    assert day["approved_overtime_minutes"] == 0

    r = _put(c, f"/api/attendance/days/{day['id']}/overtime/",
             {"minutes": 120})
    assert r.json()["approved_overtime_minutes"] == 120

    r = _put(c, f"/api/attendance/days/{day['id']}/overtime/",
             {"minutes": 999})
    assert r.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_manual_adjustment_requires_note_and_survives(env):
    c = _client(env, "hr_manager")
    emp_id = env["emp"].id
    _post(c, f"/api/attendance/{emp_id}/days/",
          {"from": "2026-03-09", "to": "2026-03-09"})
    day = c.get(f"/api/attendance/{emp_id}/days/"
                "?from=2026-03-09&to=2026-03-09").json()[0]
    assert day["status"] == "absent"

    assert _put(c, f"/api/attendance/days/{day['id']}/adjust/",
                {"status": "leave", "note": ""}).status_code == 400

    r = _put(c, f"/api/attendance/days/{day['id']}/adjust/",
             {"status": "leave", "note": "إذن شفهي"})
    assert r.json()["is_manually_adjusted"] is True

    res = _post(c, f"/api/attendance/{emp_id}/days/",
                {"from": "2026-03-09", "to": "2026-03-09"}).json()
    assert res["days_skipped"] == 1


@pytest.mark.django_db(transaction=True)
def test_monthly_summary_built(env):
    c = _client(env, "hr_manager")
    emp_id = env["emp"].id
    for h, ref in ((8, "m1"), (16, "m2")):
        _post(c, "/api/attendance/punch/", {
            "employment_id": emp_id, "punched_at": _iso(2, h),
            "source": "device", "external_ref": ref})
    _post(c, f"/api/attendance/{emp_id}/days/",
          {"from": "2026-03-01", "to": "2026-03-10"})
    r = _post(c, f"/api/attendance/{emp_id}/summary/",
              {"year": 2026, "month": 3})
    assert r.status_code == 200
    assert float(r.json()["worked_days"]) > 0


@pytest.mark.django_db(transaction=True)
def test_employee_cannot_approve_overtime(env):
    hr = _client(env, "hr_manager", username="hr1")
    emp_id = env["emp"].id
    _post(hr, f"/api/attendance/{emp_id}/days/",
          {"from": "2026-03-02", "to": "2026-03-02"})
    day = hr.get(f"/api/attendance/{emp_id}/days/"
                 "?from=2026-03-02&to=2026-03-02").json()[0]

    emp_user = _client(env, "employee", Scope.OWN, username="emp1")
    r = _put(emp_user, f"/api/attendance/days/{day['id']}/overtime/",
             {"minutes": 60})
    assert r.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_shift_creation_requires_permission(env):
    staff = _client(env, "hr_staff", username="staff1")
    r = _post(staff, "/api/attendance/shifts/",
              {"code": "NIGHT", "name_ar": "ليلي"})
    assert r.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_attendance_isolated_between_accounts(env, rls_enforced_late):
    other = provision_account(slug="attapi-o", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    c = _client(env, "hr_manager")
    _post(c, "/api/attendance/punch/", {
        "employment_id": env["emp"].id, "punched_at": _iso(2, 8),
        "source": "device", "external_ref": "iso1"})
    rls_enforced_late()
    from apps.attendance.models import AttendancePunch
    with account_scope(other.account_id):
        assert AttendancePunch.objects.count() == 0
