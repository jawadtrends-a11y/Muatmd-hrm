"""
حارس عودة الدفع (ق-109).

⚠️ ماليّ: العميل يعود من البنك **بلا جلسة**، فلا سياق حساب — وRLS
يحجب الفاتورة. فكان تأكيد دفعةٍ نجحت فعلًا يسقط بـ«غير موجودة»،
والعميل قد دفع.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection

from apps.accounts.models import Account
from apps.accounts.models_billing import Plan, PlanPriceTier
from apps.accounts.models_billing_v2 import (
    BillingCycle, Invoice, InvoiceStatus)
from apps.accounts.services import billing_v2 as billing
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope


@pytest.fixture
def env(db):
    r = provision_account(slug="pay-cb", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    plan = Plan.objects.create(code="cb-basic", name_ar="اختبار",
                               base_fee_monthly=Decimal("0"),
                               min_billable_employees=1, trial_days=7)
    PlanPriceTier.objects.create(
        plan=plan, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("15"),
        price_per_employee_yearly=Decimal("180"))
    with account_scope(r.account_id):
        sub = billing.ensure_trial(Account.objects.get(id=r.account_id))
        sub.plan = plan
        sub.cycle = BillingCycle.MONTHLY
        sub.subscribed_employees = 10
        sub.save()
        inv, _ = billing.create_invoice(subscription=sub, headcount=10)
        billing.issue_invoice(inv)
    return {"account_id": r.account_id, "invoice_id": inv.id, "plan": plan}


def test_invoice_account_is_readable_without_context(env):
    """
    ⚠️ الأهمّ: رقم حساب الفاتورة يُقرأ بلا سياق.

    وبدونه يسقط تأكيد الدفع للعائد من البنك — وقد دفع فعلًا.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT account_id FROM app_invoice_account(%s)",
                    [env["invoice_id"]])
        row = cur.fetchone()
    assert row is not None, "الفاتورة محجوبة عن العائد من البنك"
    assert row[0] == env["account_id"]


def test_lookup_returns_nothing_for_unknown_invoice(env):
    """فاتورة لا وجود لها لا تُرجع حسابًا."""
    with connection.cursor() as cur:
        cur.execute("SELECT account_id FROM app_invoice_account(%s)",
                    [999999])
        assert cur.fetchone() is None


def test_lookup_exposes_account_id_only(env):
    """
    الدالّة ترجع رقم الحساب وحده — لا مبالغ ولا بيانات.

    فالمعزول ذاتيًّا يُبقي أقلّ ما يلزم مكشوفًا.
    """
    with connection.cursor() as cur:
        cur.execute("SELECT * FROM app_invoice_account(%s)",
                    [env["invoice_id"]])
        assert len(cur.description) == 1
        assert cur.description[0].name == "account_id"


def test_paid_invoice_activates_subscription(env):
    """الفاتورة المسدَّدة تُفعّل الاشتراك وتفتح فترته."""
    from apps.accounts.models_billing_v2 import (
        AccountSubscription, SubscriptionState)

    with account_scope(env["account_id"]):
        inv = Invoice.objects.get(id=env["invoice_id"])
        billing.mark_paid(inv)
        inv.refresh_from_db()
        assert inv.status == InvoiceStatus.PAID

        sub = AccountSubscription.objects.get(account_id=env["account_id"])
        assert sub.state == SubscriptionState.ACTIVE
        assert sub.current_period_end is not None
        assert sub.current_period_end > date.today()
