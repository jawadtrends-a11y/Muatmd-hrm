"""
حرّاس آثار الأنواع الجديدة (ق-124).

⚠️ **طلبٌ يُعتمد بلا أثر ورقةٌ لا أكثر** — فلكلٍّ أثره في مكانه:
الحضور أو الفترة أو التوظيف.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import (
    AttendanceDay, DayStatus, Shift, ShiftAssignment)
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import Request, RequestStatus, RequestType
from apps.leaves.services.requests import apply_effect

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="eff-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        p, _ = create_person(
            account=acc, first_name_ar="بدر", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1066677788", mobile="0506667778")
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="E-1",
            join_date=TODAY - timedelta(days=400),
            salary_lines=[(basic, Decimal("6000"))])
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp}


def _req(env, rtype, payload):
    return Request.objects.create(
        account_id=env["account_id"], company=env["comp"],
        employment=env["emp"], request_type=rtype,
        request_no=f"T-{rtype}", payload=payload,
        status=RequestStatus.APPROVED)


def test_swap_restday_marks_both_days(env):
    """
    ⚠️ تبديل يوم راحة يعكس اليومين معًا.

    فبلا تعليم الراحة البديلة يُحسب الموظف غائبًا فيها — وهو
    يستحقّها.
    """
    with account_scope(env["account_id"]):
        work, rest = TODAY, TODAY + timedelta(days=3)
        req = _req(env, RequestType.SWAP_RESTDAY,
                   {"work_date": str(work), "rest_date": str(rest),
                    "reason": "ظرف تشغيليّ"})
        apply_effect(req)

        d1 = AttendanceDay.objects.get(employment=env["emp"],
                                       work_date=work)
        d2 = AttendanceDay.objects.get(employment=env["emp"],
                                       work_date=rest)
        assert d1.status == DayStatus.PRESENT
        assert d2.status == DayStatus.WEEKEND


def test_offsite_marks_present_without_punch(env):
    """الدوام خارج المكتب حضورٌ كامل بلا بصمة."""
    with account_scope(env["account_id"]):
        start = TODAY
        end = TODAY + timedelta(days=2)
        req = _req(env, RequestType.OFFSITE,
                   {"work_date": str(start), "end_date": str(end),
                    "location": "موقع العميل", "reason": "تركيب"})
        out = apply_effect(req)

        assert out["days_marked"] == 3
        for i in range(3):
            d = AttendanceDay.objects.get(
                employment=env["emp"], work_date=start + timedelta(days=i))
            assert d.status == DayStatus.PRESENT
            assert d.worked_minutes == 480


def test_shift_change_closes_the_previous_assignment(env):
    """
    ⚠️ تغيير الفترة **يُغلق السابق ولا يمحوه**.

    فأيامٌ عُولجت بالفترة القديمة تبقى صحيحة، وإلا تبدّلت مخالفات
    شهرٍ مضى.
    """
    with account_scope(env["account_id"]):
        # الشركة الجديدة قد تكون بلا فترات مبذورة — فننشئها
        old_shift = Shift.objects.filter(company=env["comp"]).first()
        if old_shift is None:
            old_shift = Shift.objects.create(
                account_id=env["account_id"], company=env["comp"],
                code="DAY", name_ar="صباحية",
                start_time="08:00", end_time="16:00", is_default=True)
        new_shift = Shift.objects.create(
            account_id=env["account_id"], company=env["comp"],
            code="EVE", name_ar="مسائية",
            start_time="14:00", end_time="22:00")
        ShiftAssignment.objects.create(
            account_id=env["account_id"], company=env["comp"],
            employment=env["emp"], shift=old_shift,
            effective_from=TODAY - timedelta(days=100))

        start = TODAY + timedelta(days=1)
        req = _req(env, RequestType.SHIFT_CHANGE,
                   {"shift_id": new_shift.id, "start_date": str(start),
                    "reason": "ظرف شخصيّ"})
        apply_effect(req)

        old_a = ShiftAssignment.objects.get(
            employment=env["emp"], shift=old_shift)
        assert old_a.effective_to == start - timedelta(days=1)
        assert ShiftAssignment.objects.filter(
            employment=env["emp"], shift=new_shift,
            effective_from=start, effective_to__isnull=True).exists()


def test_salary_fix_ends_probation(env):
    """تثبيت الراتب يُنهي فترة التجربة."""
    with account_scope(env["account_id"]):
        eff = TODAY
        req = _req(env, RequestType.SALARY_FIX,
                   {"reason": "اجتاز التجربة", "effective_date": str(eff)})
        apply_effect(req)
        env["emp"].refresh_from_db()
        assert env["emp"].probation_end_date == eff


def test_custom_payment_is_explicit_about_manual(env):
    """
    والصرف المخصّص **يُصرّح بأنه يدويّ** — لا يُوهم بأثرٍ لا يقع.

    فالإضافات تُبنى وقت تشغيل المسير ولا جدولَ ينتظرها بعد.
    """
    with account_scope(env["account_id"]):
        req = _req(env, RequestType.CUSTOM_PAYMENT,
                   {"amount": "500", "reason": "مكافأة"})
        out = apply_effect(req)
        assert out.get("pending_manual") is True
        assert "يدويًّا" in out.get("note", "")
