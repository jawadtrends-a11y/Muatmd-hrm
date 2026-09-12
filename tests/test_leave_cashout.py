"""
حرّاس مخالصة الإجازة (ق-138).

⚠️ **صرف بدل الإجازة بلا استخدامٍ فعليّ ولا انتهاء علاقة مخالفٌ
لنظام العمل** (المادة ١٠٩) — والمسؤولية على صاحب العمل.

فلا نمنعه، **وننبّه عليه**، ونجعله خيارًا مطفأً افتراضًا (قرار
جواد).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import LeaveBalance, LeaveType
from apps.payroll.models import PayComponent, PayrollSettings
from apps.payroll.services import leave_cashout as svc


@pytest.fixture
def env(db):
    r = provision_account(slug="lc-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        housing = PayComponent.objects.filter(
            company=comp, code="HOUSING").first()

        p, _ = create_person(
            account=acc, first_name_ar="مشعل", family_name_ar="الغامدي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1099900033", mobile="0509990003")
        lines = [(basic, Decimal("9000"))]
        if housing:
            lines.append((housing, Decimal("3000")))
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="C-1",
            join_date=date(2024, 1, 1), salary_lines=lines)

        st = PayrollSettings.objects.get(company=comp)
        st.eosb_wage_basis = "basic_housing"
        st.save(update_fields=["eosb_wage_basis"])

        annual = LeaveType.objects.get(company=comp, code="ANNUAL")
        b, _ = LeaveBalance.objects.get_or_create(
            employment=emp, leave_type=annual,
            year=timezone.localdate().year,
            defaults={"account": acc, "company": comp})
        b.accrued = Decimal("20")
        b.consumed = Decimal("0")
        b.save()

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "settings": st, "annual": annual}


def test_cashout_is_off_by_default(env):
    """
    ⚠️ الأهمّ: **مطفأةٌ افتراضًا**.

    فالصرف أثناء الخدمة مخالفة — ولا نجعله سلوكًا تلقائيًّا.
    """
    with account_scope(env["account_id"]):
        assert env["settings"].allow_leave_cashout is False
        with pytest.raises(svc.CashoutError) as e:
            svc.cash_out(employment=env["emp"], days=3)
        assert "غير مفعَّلة" in str(e.value)


def test_preview_carries_the_legal_warning(env):
    """
    **والمعاينة تحمل التنبيه النظاميّ** — فمن يفعّلها يفعّلها
    على بصيرة.
    """
    with account_scope(env["account_id"]):
        p = svc.preview(employment=env["emp"], days=5)
        assert "المادة ١٠٩" in p["warning"]
        assert p["allowed"] is False


def test_amount_uses_the_configured_basis(env):
    """
    ⚠️ **والأساس من الإعدادات** لا الأساسيّ وحده.

    فبدل الإجازة يُحسب على الأجر الفعليّ (المادة ١٠٩) — والشركة
    تحدّد ما يدخل فيه.
    """
    with account_scope(env["account_id"]):
        p = svc.preview(employment=env["emp"], days=1)
        # 9000 + 3000 = 12000 ÷ 30 = 400
        assert p["daily_rate"] == "400.00", p
        assert p["monthly_wage"] == "12000.00", p


def test_basic_only_basis_lowers_it(env):
    """وتغيير الأساس يغيّر المبلغ — فهو قرار الشركة."""
    with account_scope(env["account_id"]):
        env["settings"].eosb_wage_basis = "basic_only"
        env["settings"].save(update_fields=["eosb_wage_basis"])
        p = svc.preview(employment=env["emp"], days=1)
        assert p["daily_rate"] == "300.00", p


def test_cashout_consumes_the_balance(env):
    """والصرف يخصم من الرصيد — فلا يُصرف مرّتين."""
    with account_scope(env["account_id"]):
        env["settings"].allow_leave_cashout = True
        env["settings"].save(update_fields=["allow_leave_cashout"])

        before = svc.available_days(env["emp"])
        svc.cash_out(employment=env["emp"], days=5)
        after = svc.available_days(env["emp"])
        assert after == before - Decimal("5"), (before, after)


def test_cannot_cash_out_more_than_balance(env):
    """
    ⚠️ **ولا يُصرف أكثر من الرصيد**: فصرفُ ما لا يملكه دَينٌ عليه
    لا بدل.
    """
    with account_scope(env["account_id"]):
        env["settings"].allow_leave_cashout = True
        env["settings"].save(update_fields=["allow_leave_cashout"])

        with pytest.raises(svc.CashoutError) as e:
            svc.cash_out(employment=env["emp"], days=100)
        assert "الرصيد المتاح" in str(e.value)


def test_zero_or_negative_days_refused(env):
    """وصفرٌ أو سالبٌ يُرفض."""
    with account_scope(env["account_id"]):
        for d in (0, -3):
            with pytest.raises(svc.CashoutError):
                svc.preview(employment=env["emp"], days=d)
