"""
حرّاس سقف الإضافيّ (ق-184).

**قرار جواد:** «بمجرّد يدخل التاريخ وتكون فترة العمل معرَّفة يظهر
له الوقت الزائد كمقترح — وإذا طلبه يُقبل أو يقدر يُقلّل، **أمّا
الزيادة تُرفض من قبل الرفع**».

⚠️⚠️ **فالبصمة هي الحقيقة** — والطلب لا يخلق ساعاتٍ لم تقع.

⚠️ **ولا بصمةَ يعني القبول**: فقد نسي البصم — **وذاك سجلٌّ آخر
لا سببٌ لرفض حقّه**.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import RequestType
from apps.leaves.services.requests import RequestError, create_request
from apps.payroll.models import PayComponent

WORK_DAY = date(2026, 4, 6)


@pytest.fixture
def env(db):
    r = provision_account(slug="otcap", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="فيصل", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1079001100", mobile="0507900110")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="OT-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])

        u = User.objects.create_user(username="ot.emp", password="x")
        p.user = u
        p.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, employment=emp,
            role=Role.objects.get(account=acc, code="employee"),
            company=comp, scope=Scope.OWN.value)

        yield {"account_id": r.account_id, "comp": comp,
               "emp": emp, "user": u}


def _day(env, computed):
    """يومُ حضورٍ بإضافيٍّ محتسب."""
    tz = timezone.get_current_timezone()
    return AttendanceDay.objects.create(
        account_id=env["emp"].account_id,
        company_id=env["emp"].company_id,
        employment=env["emp"], work_date=WORK_DAY, status="present",
        first_in=timezone.make_aware(
            datetime.combine(WORK_DAY, time(8, 0)), tz),
        last_out=timezone.make_aware(
            datetime.combine(WORK_DAY, time(18, 0)), tz),
        overtime_minutes=computed)


def _ask(env, minutes):
    return create_request(
        employment=env["emp"], request_type=RequestType.OVERTIME,
        payload={"work_date": str(WORK_DAY), "minutes": minutes,
                 "from_time": "17:00", "to_time": "18:05"},
        note="اختبار")


def test_request_within_computed_is_accepted(env):
    """**والمساوي للمحتسب يُقبل**."""
    with account_scope(env["account_id"]):
        _day(env, 65)
        req = _ask(env, 65)
        assert req is not None


def test_less_than_computed_is_accepted(env):
    """
    **ويقدر يُقلّل** (قرار جواد): فمن عمل ٦٥ وطلب ٣٠ **حقُّه**.
    """
    with account_scope(env["account_id"]):
        _day(env, 65)
        assert _ask(env, 30) is not None


def test_more_than_computed_is_refused_at_submit(env):
    """
    ⚠️⚠️ الأهمّ: **والزيادة تُرفض من قبل الرفع** (قرار جواد) —
    **لا عند الاعتماد**: فالموظف لا ينتظر أيامًا ليُرفض طلبه.
    """
    with account_scope(env["account_id"]):
        _day(env, 65)
        with pytest.raises(RequestError) as e:
            _ask(env, 70)
        # ⚠️ **والرسالة تُسمّي الرقمين** — فمبدأ جواد: التفصيل
        assert "65" in str(e.value), str(e.value)
        assert "70" in str(e.value), str(e.value)


def test_no_punch_means_accept(env):
    """
    ⚠️⚠️ **ولا بصمةَ يعني القبول** (قرار جواد): **فقد نسي البصم**
    — وذاك سجلٌّ آخر لا سببٌ لرفض حقّه.
    """
    with account_scope(env["account_id"]):
        # بلا يوم حضورٍ أصلًا
        assert _ask(env, 120) is not None


def test_zero_computed_means_accept(env):
    """
    **ويومٌ بلا إضافيٍّ محتسب يُقبل كذلك**: فالبصمة قد تكون ناقصة
    — والمشرف يقرّر.
    """
    with account_scope(env["account_id"]):
        _day(env, 0)
        assert _ask(env, 60) is not None


def test_effect_also_caps(env):
    """
    ⚠️ **والخدمة تفحص كذلك**: فالواجهة تُساعد **لا تحرس** —
    ومسارٌ آخر قد يستدعي الأثر مباشرةً.
    """
    from apps.leaves.models import Request
    from apps.leaves.services.requests import _effect_overtime

    with account_scope(env["account_id"]):
        day = _day(env, 65)
        req = Request.objects.create(
            account_id=env["emp"].account_id,
            company_id=env["emp"].company_id,
            employment=env["emp"], request_no="OT-X1",
            request_type=RequestType.OVERTIME,
            payload={"work_date": str(WORK_DAY), "minutes": 999})

        with pytest.raises(RequestError):
            _effect_overtime(req)

        day.refresh_from_db()
        assert day.approved_overtime_minutes == 0, "اعتُمد المتجاوز"


def test_hint_route_reports_computed(env, client):
    """
    ⚠️ **والمسار يُبلّغ المحتسب** — فالشاشة تعرضه وتملؤه.
    """
    with account_scope(env["account_id"]):
        _day(env, 65)

    client.force_login(env["user"])
    res = client.get(f"/api/me/overtime/?date={WORK_DAY}")
    assert res.status_code == 200, res.content[:200]
    body = res.json()
    assert body["has_record"] is True
    assert body["computed_minutes"] == 65


def test_hint_route_when_no_punch(env, client):
    """**وبلا بصمةٍ يُبلّغ أنه لا سجلّ** — لا خطأً."""
    client.force_login(env["user"])
    res = client.get("/api/me/overtime/?date=2026-04-09")
    assert res.status_code == 200
    assert res.json()["has_record"] is False
