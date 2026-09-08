"""
حرّاس الإعفاء من البصمة والفترة الافتراضية (ق-104).

⚠️ أثرهما ماليّ: المعفيّ يُعدّ غائبًا فيُخصم أجره، ومن لا فترة له
لا يُحسب حضوره ولا غيابه.
"""
from datetime import date

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay, DayStatus, Shift
from apps.attendance.models_exemption import AttendanceExemption
from apps.attendance.services.processing import process_employment_days
from apps.attendance.services.rules import effective_shift
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import (
    ApprovalChain, Request, RequestStatus, RequestType)
from apps.leaves.services.requests import apply_effect
from apps.leaves.services.seeds import provision_approval_chains


@pytest.fixture
def env(db):
    r = provision_account(slug="exempt-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        shift = Shift.objects.create(
            account=acc, company=comp, code="DAY", name_ar="نهاري",
            start_time="08:00", end_time="17:00",
            working_days=[0, 1, 2, 3, 4], is_default=True)
        p, _ = create_person(
            account=acc, first_name_ar="فيصل", family_name_ar="الشمري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1055566677", mobile="0505556667")
        emp, _, _ = create_employment(person=p, company=comp,
                                      employee_no="X-1",
                                      join_date=date(2024, 1, 1))
        yield {"account_id": r.account_id, "company": comp,
               "employment": emp, "shift": shift}


def test_exempt_day_is_not_absence(env):
    """⚠️ المعفيّ لا يُعدّ غائبًا — وإلا خُصم أجر يوم لا بصمة عليه."""
    emp = env["employment"]
    with account_scope(env["account_id"]):
        AttendanceExemption.objects.create(
            account_id=env["account_id"], company=env["company"],
            employment=emp, start_date=date(2026, 6, 1),
            reason="مندوب خارجي")
        process_employment_days(employment=emp,
                                start_date=date(2026, 6, 8),
                                end_date=date(2026, 6, 9), force=True)
        for d in (date(2026, 6, 8), date(2026, 6, 9)):
            a = AttendanceDay.objects.get(employment=emp, work_date=d)
            assert a.status == DayStatus.EXEMPT, \
                f"{d} سُجّل {a.status} — يُخصم من راتبه"


def test_exemption_respects_its_range(env):
    """الإعفاء بمدّة: ما قبلها وما بعدها لا يُعفى."""
    emp = env["employment"]
    with account_scope(env["account_id"]):
        AttendanceExemption.objects.create(
            account_id=env["account_id"], company=env["company"],
            employment=emp, start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31), reason="مؤقّت")
        process_employment_days(employment=emp,
                                start_date=date(2026, 6, 29),
                                end_date=date(2026, 8, 4), force=True)
        assert AttendanceDay.objects.get(
            employment=emp, work_date=date(2026, 7, 15)
        ).status == DayStatus.EXEMPT
        after = AttendanceDay.objects.get(
            employment=emp, work_date=date(2026, 8, 4))
        assert after.status != DayStatus.EXEMPT, "الإعفاء تجاوز مدّته"


def test_no_employee_without_shift(env):
    """
    ق-104: من لم تُسند له فترة يتبع الافتراضية.

    وبدونها يبقى يومه «خارج جدول العمل» — فلا يُعرف حضوره من
    غيابه ولا تأخيره من انضباطه.
    """
    emp = env["employment"]
    with account_scope(env["account_id"]):
        assert not emp.shift_assignments.exists() \
            if hasattr(emp, "shift_assignments") else True
        sh = effective_shift(emp, date(2026, 6, 10))
        assert sh is not None, "موظف بلا فترة عمل"
        assert sh.is_default


def test_exemption_chain_has_two_steps(env):
    """مدير الإدارة ثم موظف الموارد — ومن أسندها لا يعتمدها."""
    with account_scope(env["account_id"]):
        provision_approval_chains(env["company"])
        ch = ApprovalChain.objects.filter(
            company=env["company"],
            request_type=RequestType.ATTENDANCE_EXEMPTION).first()
        assert ch is not None, "لا سلسلة للإعفاء"
        steps = list(ch.steps.order_by("step_order"))
        assert len(steps) == 2
        assert steps[0].approver_type == "department_head"
        assert steps[1].approver_role_code == "hr_staff"


def test_approved_request_creates_exemption(env):
    """الطلب المعتمد يترك أثرًا حقيقيًّا — سجلّ إعفاء ساري."""
    emp = env["employment"]
    with account_scope(env["account_id"]):
        req = Request.objects.create(
            account=emp.account, company=emp.company, employment=emp,
            request_no="EX-1",
            request_type=RequestType.ATTENDANCE_EXEMPTION,
            status=RequestStatus.APPROVED,
            payload={"start_date": "2026-10-01", "reason": "مدير عام"})
        out = apply_effect(req)
        assert out.get("applied"), out
        ex = AttendanceExemption.objects.get(employment=emp, is_active=True)
        assert ex.start_date == date(2026, 10, 1)
        assert ex.end_date is None
        assert ex.covers(date(2027, 5, 1)), "غير محدّد المدّة لا يغطي"
