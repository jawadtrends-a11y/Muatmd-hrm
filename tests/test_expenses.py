"""
حرّاس المصروفات (ق-139).

⚠️ **المصروف يُثبَت لا يُدّعى**: الفاتورة إلزامية — فتعويضٌ بلا
إثبات يفتح بابًا لا يُغلق.

**والسقف والصلاحية وآلية الصرف من إعدادات الشركة** (قرار جواد) —
لا نفرضها.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    ExpenseCategory, ExpenseStatus, PayComponent, PayrollSettings)
from apps.payroll.services import expenses as svc

TODAY = date.today()


@pytest.fixture
def env(db):
    r = provision_account(slug="exp-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="تركي", family_name_ar="المالكي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1010011144", mobile="0501001114")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="X-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("7000"))])

        st = PayrollSettings.objects.get(company=comp)
        st.expenses_enabled = True
        st.save(update_fields=["expenses_enabled"])

        cat = ExpenseCategory.objects.create(
            account=acc, company=comp, code="FUEL", name_ar="وقود",
            max_per_claim=Decimal("300"),
            max_per_month=Decimal("800"))

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "cat": cat, "settings": st}


def _claim(env, amount=100, days_ago=2, receipt="/f/r.png", cat=None):
    return svc.submit(
        employment=env["emp"], category=cat or env["cat"],
        spent_on=TODAY - timedelta(days=days_ago),
        amount=amount, description="تعبئة وقود",
        receipt_url=receipt)


def test_receipt_is_required(env):
    """
    ⚠️ الأهمّ: **لا مطالبة بلا فاتورة**.

    فتعويضٌ بلا إثبات يفتح بابًا لا يُغلق.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.ExpenseError) as e:
            _claim(env, receipt="")
        assert "الفاتورة" in str(e.value)


def test_disabled_by_default_in_settings(env):
    """
    **والمصروفات تُفعَّل من الإعدادات** — لا تعمل بلا قرار.
    """
    with account_scope(env["account_id"]):
        env["settings"].expenses_enabled = False
        env["settings"].save(update_fields=["expenses_enabled"])
        with pytest.raises(svc.ExpenseError) as e:
            _claim(env)
        assert "غير مفعَّلة" in str(e.value)


def test_claim_cap_is_enforced(env):
    """وسقف المطالبة الواحدة يُحترم."""
    with account_scope(env["account_id"]):
        with pytest.raises(svc.ExpenseError) as e:
            _claim(env, amount=500)
        assert "سقف وقود" in str(e.value)


def test_monthly_cap_counts_previous_claims(env):
    """
    ⚠️ **وسقف الشهر يجمع ما سبق** — وإلا التُفّ عليه بمطالباتٍ
    صغيرة متتابعة.
    """
    with account_scope(env["account_id"]):
        for _ in range(3):
            _claim(env, amount=250)
        with pytest.raises(svc.ExpenseError) as e:
            _claim(env, amount=250)
        assert "سقف الشهر" in str(e.value)


def test_age_limit_from_settings(env):
    """
    ⚠️ **وقِدَم المطالبة محدود** — ومن الإعدادات لا مفروضًا.

    فمطالبةٌ بعد سنة يتعذّر التحقّق منها، ودفترها أُغلق.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.ExpenseError) as e:
            _claim(env, days_ago=200)
        assert "مضى على المصروف" in str(e.value)

        env["settings"].expense_max_age_days = 365
        env["settings"].save(update_fields=["expense_max_age_days"])
        assert _claim(env, days_ago=200) is not None


def test_future_date_refused(env):
    """ولا مطالبة بمصروفٍ لم يقع بعد."""
    with account_scope(env["account_id"]):
        with pytest.raises(svc.ExpenseError):
            _claim(env, days_ago=-5)


def test_rejected_is_not_settled(env):
    """
    ⚠️ **والمرفوضة لا تُصرف**: فالقرار يُحترم، ولا يُلتفّ عليه.
    """
    with account_scope(env["account_id"]):
        c = _claim(env, amount=200)
        svc.decide(claim=c, approve=False, note="بلا مبرّر")
        assert c.status == ExpenseStatus.REJECTED

        with pytest.raises(svc.ExpenseError) as e:
            svc.settle(claim=c, method="outside")
        assert "المعتمدة" in str(e.value)


def test_approved_can_be_settled_outside(env):
    """والمعتمدة تُصرف — وخارج المسير يُوثَّق متى."""
    with account_scope(env["account_id"]):
        c = _claim(env, amount=200)
        svc.decide(claim=c, approve=True)
        svc.settle(claim=c, method="outside", paid_note="نقدًا")
        c.refresh_from_db()
        assert c.status == ExpenseStatus.SETTLED
        assert c.paid_on is not None


def test_decision_is_final(env):
    """والقرار لا يُعاد — فمطالبةٌ حُسمت لا تُحسم ثانيةً."""
    with account_scope(env["account_id"]):
        c = _claim(env, amount=150)
        svc.decide(claim=c, approve=True)
        with pytest.raises(svc.ExpenseError):
            svc.decide(claim=c, approve=False)


def test_claim_numbers_do_not_repeat(env):
    """والأرقام لا تتكرّر."""
    with account_scope(env["account_id"]):
        nums = {_claim(env, amount=50).claim_no for _ in range(3)}
        assert len(nums) == 3, nums
