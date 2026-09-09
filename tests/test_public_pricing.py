"""
حرّاس صفحة الأسعار العامّة (ق-116).

⚠️ **بلا توثيق**: تُفتح قبل التسجيل ويُربط إليها من الموقع
الرئيسيّ — فيجب ألّا تكشف شيئًا وراء الأسعار المعلنة.
"""
from decimal import Decimal

import pytest
from django.test import Client

from apps.accounts.models_billing import Plan, PlanPriceTier


@pytest.fixture
def plans(db):
    pub = Plan.objects.create(code="pub", name_ar="معروضة",
                              base_fee_monthly=Decimal("0"),
                              min_billable_employees=1, is_public=True,
                              is_active=True)
    PlanPriceTier.objects.create(
        plan=pub, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("15"),
        price_per_employee_yearly=Decimal("180"))

    hidden = Plan.objects.create(code="hidden", name_ar="مخفية",
                                 base_fee_monthly=Decimal("0"),
                                 min_billable_employees=1, is_public=False,
                                 is_active=True)
    PlanPriceTier.objects.create(
        plan=hidden, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("99"),
        price_per_employee_yearly=Decimal("999"))
    return {"pub": pub, "hidden": hidden}


def test_pricing_is_public(plans):
    """تُفتح بلا توثيق — وإلا لم تُرَ قبل التسجيل."""
    r = Client().get("/api/pricing/")
    assert r.status_code == 200
    codes = [p["code"] for p in r.json()["plans"]]
    assert "pub" in codes


def test_hidden_plans_are_not_listed(plans):
    """
    ⚠️ غير المعروضة لا تظهر.

    فالباقات الخاصّة (سعر متفق عليه لعميل بعينه) تبقى خاصّة.
    """
    r = Client().get("/api/pricing/")
    codes = [p["code"] for p in r.json()["plans"]]
    assert "hidden" not in codes


def test_public_quote_computes_on_server(plans):
    """الحساب في الخادم — ٢٠ × ١٥ + ضريبة."""
    r = Client().get(
        f"/api/pricing/quote/?plan_id={plans['pub'].id}"
        "&employees=20&cycle=monthly")
    assert r.status_code == 200
    j = r.json()
    assert Decimal(j["subscription"]) == Decimal("300.00")
    assert Decimal(j["total"]) == Decimal("345.00")


def test_quote_refuses_hidden_plan(plans):
    """ولا يُسعّر باقةً غير معروضة."""
    r = Client().get(
        f"/api/pricing/quote/?plan_id={plans['hidden'].id}"
        "&employees=10&cycle=monthly")
    assert r.status_code == 404


def test_quote_refuses_absurd_counts(plans):
    """ولا عددًا خياليًّا — فالصفحة عامّة ويُساء استعمالها."""
    for n in (0, 999999):
        r = Client().get(
            f"/api/pricing/quote/?plan_id={plans['pub'].id}"
            f"&employees={n}&cycle=monthly")
        assert r.status_code == 400, n


def test_pricing_exposes_no_customer_data(plans):
    """
    ⚠️ ولا تكشف بيانات عميل: الردّ باقاتٌ ومزايا وأسعار — لا
    حسابات ولا اشتراكات ولا أعداد موظفين.
    """
    j = Client().get("/api/pricing/").json()
    text = str(j)
    for leak in ("account", "subscription_id", "employee_no", "person"):
        assert leak not in text, f"تسريب: {leak}"
