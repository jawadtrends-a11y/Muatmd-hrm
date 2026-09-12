"""
حرّاس معامِل الإضافي (ق-137).

**قرار جواد:** الموظف يختار ×1.5 أو ×2 في الطلب، والمعتمِد **يقبل
أو يرفض ولا يعدّل** — فالتعديل بعد التقديم يجعله يوقّع على غير ما
طلب.

⚠️ **والخيار لا يظهر إلا إن سمحت الموارد** — وأساس ×2 من
الإعدادات لا مفروضًا.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendanceDay, DayStatus
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import RequestType
from apps.leaves.services.requests import RequestError, create_request
from apps.payroll.models import (
    PayComponent, PayrollRunType, PayrollSettings)
from apps.payroll.services import engine

TODAY = date.today()


@pytest.fixture
def env(db):
    r = provision_account(slug="ot-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="راشد", family_name_ar="العمري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1088899922", mobile="0508889992")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="O-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])
        st = PayrollSettings.objects.get(company=comp)
        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "settings": st}


def _overtime(env, rate=None, on=None):
    payload = {"work_date": str(on or TODAY - timedelta(days=1)),
               "from_time": "18:00", "to_time": "21:00", "hours": 3}
    if rate:
        payload["rate_choice"] = rate
    return create_request(employment=env["emp"],
                          request_type=RequestType.OVERTIME,
                          payload=payload)


def test_x2_refused_when_not_allowed(env):
    """
    ⚠️ الأهمّ: **×2 لا يُطلب إن لم تسمح به الموارد**.

    فشركةٌ بأساسٍ واحد لا تُسأل سؤالًا لا معنى له — ولا يُحتسب
    لموظفٍ معامِلٌ لم تُقرّه.
    """
    with account_scope(env["account_id"]):
        assert env["settings"].allow_overtime_rate_choice is False
        with pytest.raises(RequestError) as e:
            _overtime(env, rate="x2")
        assert "غير مفعَّل" in str(e.value)


def test_x2_allowed_when_enabled(env):
    """وبتفعيلها يمرّ."""
    with account_scope(env["account_id"]):
        env["settings"].allow_overtime_rate_choice = True
        env["settings"].save(update_fields=["allow_overtime_rate_choice"])
        assert _overtime(env, rate="x2") is not None


def test_default_rate_always_works(env):
    """والأساس الافتراضي يمرّ دائمًا — فهو الحدّ النظاميّ."""
    with account_scope(env["account_id"]):
        assert _overtime(env) is not None


def test_unknown_rate_is_refused(env):
    """ومعامِلٌ مجهول يُرفض."""
    with account_scope(env["account_id"]):
        with pytest.raises(RequestError):
            _overtime(env, rate="x9")


def test_rate_is_stored_with_the_minutes(env):
    """
    ⚠️ **والمعامِل يُحفظ مع دقائقه**.

    فالدقائق تصل المسير مجمّعةً — وبلا حفظه يُحتسب الجميع بأساسٍ
    واحد، ويضيع ما اعتُمد بـ×2.
    """
    with account_scope(env["account_id"]):
        env["settings"].allow_overtime_rate_choice = True
        env["settings"].save(update_fields=["allow_overtime_rate_choice"])

        day = TODAY - timedelta(days=2)
        AttendanceDay.objects.create(
            account_id=env["account_id"], company=env["comp"],
            employment=env["emp"], work_date=day,
            status=DayStatus.PRESENT, worked_minutes=480)

        _overtime(env, rate="x2", on=day)
        d = AttendanceDay.objects.get(employment=env["emp"],
                                      work_date=day)
        assert d.overtime_rate_choice == "x2"
        assert d.approved_overtime_minutes == 180


def test_payslip_splits_by_rate(env):
    """
    ⚠️⚠️ **والمسير يفصّل بالمعامِل** لا يجمع بأساسٍ واحد.

    فمن اعتُمد له ×2 يُحتسب به، ومن اعتُمد له الأساس بأساسه —
    وجمعُهما يظلم أحدهما.
    """
    with account_scope(env["account_id"]):
        env["settings"].allow_overtime_rate_choice = True
        env["settings"].save(update_fields=["allow_overtime_rate_choice"])

        for i, rate in ((5, None), (6, "x2")):
            day = date(2026, 9, i)
            AttendanceDay.objects.create(
                account_id=env["account_id"], company=env["comp"],
                employment=env["emp"], work_date=day,
                status=DayStatus.PRESENT, worked_minutes=480,
                approved_overtime_minutes=120,
                overtime_rate_choice=rate or "")

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        slip = run.payslips.first()
        parts = (slip.calculation_trace or {}).get("overtime", {}).get(
            "parts", [])
        assert len(parts) == 2, parts
        rates = {p["rate"] for p in parts}
        assert rates == {"default", "x2"}, rates
