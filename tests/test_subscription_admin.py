"""
حرّاس التفعيل اليدويّ والتمديد وفرق الموظفين (ق-108، ق-112).

⚠️ ماليّة كلّها: التفعيل يُثبّت العدد المتفق عليه، وفاتورة الفرق
ترفعه عند سدادها، والمرجع لا يتصادم بين الحسابات.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account
from apps.accounts.models_billing import Plan, PlanPriceTier
from apps.accounts.models_billing_v2 import (
    AccountSubscription, BillingCycle, Invoice, InvoiceStatus,
    Payment, PaymentStatus, SubscriptionState)
from apps.accounts.services import billing_v2 as billing
from apps.accounts.services.payments.service import _on_paid
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope


@pytest.fixture
def plan(db):
    p = Plan.objects.create(code="adm-basic", name_ar="اختبار",
                            base_fee_monthly=Decimal("0"),
                            min_billable_employees=1, trial_days=7)
    PlanPriceTier.objects.create(
        plan=p, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("15"),
        price_per_employee_yearly=Decimal("180"))
    return p


@pytest.fixture
def env(db, plan):
    r = provision_account(slug="adm-sub", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    return {"account_id": r.account_id, "plan": plan}


def test_manual_activation_pins_agreed_employees(env):
    """
    ⚠️ التفعيل اليدويّ يُثبّت **العدد المتفق عليه** لا ذروة موظفيه.

    فمن اتفق على ٤٥ لا يُفوتَر على ١٣ ولا العكس.
    """
    with account_scope(env["account_id"]):
        sub = AccountSubscription.objects.get(account_id=env["account_id"])
        billing.activate_manually(
            subscription=sub, plan=env["plan"],
            cycle=BillingCycle.ANNUAL, period_start=date(2026, 1, 1),
            activated_by=None, employees=45, note="تحويل بنكي")
        sub.refresh_from_db()
        assert sub.state == SubscriptionState.ACTIVE
        assert sub.subscribed_employees == 45
        assert sub.current_period_end == date(2026, 12, 31)


def test_extend_grace_moves_the_deadline(env):
    """التمديد يمدّ المهلة إلى التاريخ المختار."""
    until = date.today() + timedelta(days=30)
    with account_scope(env["account_id"]):
        sub = AccountSubscription.objects.get(account_id=env["account_id"])
        billing.extend_grace(subscription=sub, until=until,
                             extended_by=None, note="تجربة")
        sub.refresh_from_db()
        assert sub.grace_until == until


def test_paid_overage_raises_subscribed_count(env):
    """
    ⚠️ فاتورة الفرق المسدَّدة **ترفع العدد المشترَك به** — فلا
    يُطالَب العميل بنفس الزيادة مرّتين في الفترة نفسها.
    """
    with account_scope(env["account_id"]):
        sub = AccountSubscription.objects.get(account_id=env["account_id"])
        sub.plan = env["plan"]
        sub.cycle = BillingCycle.MONTHLY
        sub.state = SubscriptionState.ACTIVE
        sub.subscribed_employees = 10
        sub.current_period_start = date.today()
        sub.current_period_end = date.today() + timedelta(days=30)
        sub.save()

        inv = Invoice.objects.create(
            account_id=env["account_id"],
            invoice_no=billing._next_invoice_no(),
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            cycle=sub.cycle, subtotal=Decimal("45"),
            total_before_vat=Decimal("45"), vat_amount=Decimal("6.75"),
            total=Decimal("51.75"), headcount=3,
            status=InvoiceStatus.ISSUED,
            is_overage=True, overage_employees=3)

        pay = Payment.objects.create(
            account_id=env["account_id"], invoice=inv,
            amount=inv.total, status=PaymentStatus.PAID,
            moyasar_payment_id="t-ov")
        _on_paid(pay, {"metadata": {}})

        sub.refresh_from_db()
        assert sub.subscribed_employees == 13, "العدد لم يرتفع"


def test_ordinary_invoice_does_not_raise_count(env):
    """وفاتورة الفترة العادية لا ترفعه — العلم هو الفارق."""
    with account_scope(env["account_id"]):
        sub = AccountSubscription.objects.get(account_id=env["account_id"])
        sub.plan = env["plan"]
        sub.cycle = BillingCycle.MONTHLY
        sub.subscribed_employees = 10
        sub.current_period_start = date.today()
        sub.current_period_end = date.today() + timedelta(days=30)
        sub.save()

        inv = Invoice.objects.create(
            account_id=env["account_id"],
            invoice_no=billing._next_invoice_no(),
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            cycle=sub.cycle, subtotal=Decimal("150"),
            total_before_vat=Decimal("150"), vat_amount=Decimal("22.50"),
            total=Decimal("172.50"), headcount=10,
            status=InvoiceStatus.ISSUED)

        pay = Payment.objects.create(
            account_id=env["account_id"], invoice=inv,
            amount=inv.total, status=PaymentStatus.PAID,
            moyasar_payment_id="t-normal")
        _on_paid(pay, {"metadata": {}})

        sub.refresh_from_db()
        assert sub.subscribed_employees == 10


def test_reference_prefix_is_sub_not_inv(env):
    """
    المرجع الداخليّ بادئته SUB — **وليس فاتورة زكاتية**.

    فالفاتورة الضريبية تصدر من معتمد المحاسبي (ق-111)، وتسميته
    INV توهم المطوّر والعميل معًا.
    """
    with account_scope(env["account_id"]):
        assert billing._next_invoice_no().startswith("SUB-")


def test_reference_does_not_collide_across_accounts(env, plan,
                                                   rls_enforced_late):
    """
    ⚠️ المرجع لا يتصادم بين الحسابات.

    والعدّ داخل عزل الحساب كان يبدأ بكل حساب من واحد — فيصطدم
    بقيد التفرّد أول ما يشترك حسابان.
    """
    other = provision_account(slug="adm-sub2", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)

    # العزل يُفرض الآن: فالعدّ داخل الحساب لا يرى فواتير غيره —
    # وهو ما كان يجعل كل حساب يبدأ من واحد فيتصادم.
    rls_enforced_late()

    refs = set()
    for aid in (env["account_id"], other.account_id, env["account_id"]):
        with account_scope(aid):
            no = billing._next_invoice_no()
            assert no not in refs, f"مرجع مكرّر: {no}"
            Invoice.objects.create(
                account_id=aid, invoice_no=no,
                period_start=date.today(),
                period_end=date.today() + timedelta(days=30),
                cycle=BillingCycle.MONTHLY, subtotal=Decimal("10"),
                total=Decimal("11.50"), status=InvoiceStatus.DRAFT)
            refs.add(no)


def test_effect_applies_once_only(env):
    """
    ⚠️⚠️ الأثر مرّة واحدة مهما تكرّر التأكيد.

    صفحة نتيجة الدفع تستدعي التأكيد في **كل فتح** — وكان كل
    استدعاء يرفع العدد ثانيةً. فمن فتحها عشر مرّات رُفع عدده
    ثلاثين موظفًا، ويُفوتَر عليهم في التجديد.
    """
    with account_scope(env["account_id"]):
        sub = AccountSubscription.objects.get(account_id=env["account_id"])
        sub.plan = env["plan"]
        sub.cycle = BillingCycle.MONTHLY
        sub.state = SubscriptionState.ACTIVE
        sub.subscribed_employees = 10
        sub.current_period_start = date.today()
        sub.current_period_end = date.today() + timedelta(days=30)
        sub.save()

        inv = Invoice.objects.create(
            account_id=env["account_id"],
            invoice_no=billing._next_invoice_no(),
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            cycle=sub.cycle, subtotal=Decimal("45"),
            total_before_vat=Decimal("45"), vat_amount=Decimal("6.75"),
            total=Decimal("51.75"), headcount=3,
            status=InvoiceStatus.ISSUED,
            is_overage=True, overage_employees=3)

        pay = Payment.objects.create(
            account_id=env["account_id"], invoice=inv,
            amount=inv.total, status=PaymentStatus.PAID,
            moyasar_payment_id="t-repeat")

        for _ in range(5):
            _on_paid(pay, {"metadata": {}})

        sub.refresh_from_db()
        assert sub.subscribed_employees == 13, (
            f"تضاعف الأثر: {sub.subscribed_employees}")
