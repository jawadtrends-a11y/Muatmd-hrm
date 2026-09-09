"""
حرّاس بوّابة المزايا (ق-117).

⚠️ كانت تقرأ `CompanySubscription` المهجور الفارغ — فتُرجع
المزايا الأساسية للجميع: **الباقة أسعارٌ بلا أثر**، ومن دفع
للأساسية استعمل مزايا المؤسسية.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.models_billing import Plan, PlanFeature, PlanPriceTier
from apps.accounts.models_billing_v2 import (
    AccountSubscription, BillingCycle, SubscriptionState)
from apps.accounts.services.provisioning import provision_account
from apps.core.features.gate import Features
from apps.core.tenancy.context import account_scope


@pytest.fixture
def env(db):
    basic = Plan.objects.create(code="fg-basic", name_ar="أساسية",
                                base_fee_monthly=Decimal("0"),
                                min_billable_employees=1)
    PlanPriceTier.objects.create(
        plan=basic, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("15"),
        price_per_employee_yearly=Decimal("180"))
    for k, v in (("payroll", "true"), ("max_branches", "2"),
                 ("max_companies", "1")):
        PlanFeature.objects.create(plan=basic, feature_key=k, value=v)

    top = Plan.objects.create(code="fg-top", name_ar="مؤسسية",
                              base_fee_monthly=Decimal("0"),
                              min_billable_employees=1)
    PlanPriceTier.objects.create(
        plan=top, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("40"),
        price_per_employee_yearly=Decimal("480"))
    for k, v in (("payroll", "true"), ("advanced_reports", "true"),
                 ("api_access", "true"), ("max_branches", "0"),
                 ("max_companies", "0")):
        PlanFeature.objects.create(plan=top, feature_key=k, value=v)

    r = provision_account(slug="feat-gate", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    return {"account_id": r.account_id, "company_id": r.company_id,
            "basic": basic, "top": top}


def _subscribe(env, plan):
    with account_scope(env["account_id"]):
        sub = AccountSubscription.objects.get(account_id=env["account_id"])
        sub.plan = plan
        sub.cycle = BillingCycle.MONTHLY
        sub.state = SubscriptionState.ACTIVE
        sub.current_period_start = date.today()
        sub.current_period_end = date.today() + timedelta(days=30)
        sub.save()
    Features.invalidate(env["company_id"])


def test_plan_features_actually_apply(env):
    """
    ⚠️ الأهمّ: مزايا الباقة تُطبَّق فعلًا.

    فمن اشترك بالأساسية لا يفتح التقارير المتقدمة ولا API.
    """
    _subscribe(env, env["basic"])
    cid = env["company_id"]
    assert Features.enabled(cid, "payroll")
    assert not Features.enabled(cid, "advanced_reports")
    assert not Features.enabled(cid, "api_access")


def test_higher_plan_opens_more(env):
    """والمؤسسية تفتحها — فالفرق بين الباقتين حقيقيّ."""
    _subscribe(env, env["top"])
    cid = env["company_id"]
    assert Features.enabled(cid, "advanced_reports")
    assert Features.enabled(cid, "api_access")


def test_limits_come_from_the_plan(env):
    """والحدود كذلك: فرعان وشركة في الأساسية، وبلا حدّ في المؤسسية."""
    _subscribe(env, env["basic"])
    cid = env["company_id"]
    assert Features.limit(cid, "max_branches") == 2
    assert Features.limit(cid, "max_companies") == 1

    _subscribe(env, env["top"])
    assert Features.limit(cid, "max_branches") == 0   # 0 = بلا حدّ


def test_no_plan_means_core_features_only(env):
    """ومن بلا باقة يبقى على المزايا الأساسية وحدها."""
    with account_scope(env["account_id"]):
        AccountSubscription.objects.filter(
            account_id=env["account_id"]).update(plan=None)
    Features.invalidate(env["company_id"])
    assert not Features.enabled(env["company_id"], "advanced_reports")


def test_read_only_grants_nothing_extra(env):
    """
    ⚠️ ومن صار للقراءة فقط لا يفتح شيئًا.

    فمن انتهى اشتراكه ولم يجدّد يعود للمزايا الأساسية — وإلا
    استعمل الباقة بعد أن انقضت.
    """
    _subscribe(env, env["top"])
    assert Features.enabled(env["company_id"], "api_access")

    with account_scope(env["account_id"]):
        AccountSubscription.objects.filter(
            account_id=env["account_id"]).update(
                state=SubscriptionState.READ_ONLY)
    Features.invalidate(env["company_id"])
    assert not Features.enabled(env["company_id"], "api_access")


# ══════════ ترشيح الترقية (ق-117) ══════════

def test_hint_points_to_the_smallest_plan_that_opens_it(env):
    """
    ⚠️ الترشيح **لأصغر باقة تفتح الميزة** لا لأي باقة أعلى.

    فمن على الأساسية ويريد ميزةً في «المميزة» يُرشَّح للمميزة —
    وترشيحُ الأغلى بلا داعٍ يُنفّره، وقد لا تكون فيها أصلًا.
    """
    from apps.core.features.gate import upgrade_hint

    mid = Plan.objects.create(code="fg-mid", name_ar="مميزة",
                              base_fee_monthly=Decimal("0"),
                              min_billable_employees=1, tier_order=2)
    PlanPriceTier.objects.create(
        plan=mid, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("25"),
        price_per_employee_yearly=Decimal("300"))
    PlanFeature.objects.create(plan=mid, feature_key="advanced_reports",
                               value="true")

    Plan.objects.filter(id=env["basic"].id).update(tier_order=1)
    Plan.objects.filter(id=env["top"].id).update(tier_order=3)

    _subscribe(env, env["basic"])

    h = upgrade_hint(env["company_id"], "advanced_reports")
    assert h is not None
    assert h["plan_code"] == "fg-mid", h
    # وAPI في المؤسسية وحدها
    h2 = upgrade_hint(env["company_id"], "api_access")
    assert h2["plan_code"] == "fg-top", h2


def test_no_hint_for_an_open_feature(env):
    """ولا ترشيح لميزةٍ مفتوحة — فالرسالة تُزعج بلا سبب."""
    from apps.core.features.gate import upgrade_hint

    _subscribe(env, env["basic"])
    assert upgrade_hint(env["company_id"], "payroll") is None


def test_no_hint_when_no_plan_opens_it(env):
    """ولا لميزةٍ لا تفتحها باقةٌ معروضة — فلا نَعِد بما لا نبيع."""
    from apps.core.features.gate import upgrade_hint

    _subscribe(env, env["basic"])
    assert upgrade_hint(env["company_id"], "nitaqat_simulator") is None


# ══════════ لا مزايا مجّانية دائمة (ق-118) ══════════

def test_no_subscription_means_no_features(env):
    """
    ⚠️⚠️ الأهمّ: بلا اشتراك سارٍ **لا تُفتح ميزة**.

    والستّ التي كانت «أساسية مجّانية» هي الباقة الأساسية نفسها،
    تُنال بالاشتراك — وإلا بقي لبّ النظام مجّانًا فأُفرغ الاشتراك
    من معناه.
    """
    with account_scope(env["account_id"]):
        AccountSubscription.objects.filter(
            account_id=env["account_id"]).update(
                state=SubscriptionState.READ_ONLY, plan=None)
    Features.invalidate(env["company_id"])

    assert Features.bundle(env["company_id"]) == {}
    for key in ("attendance", "payroll", "leaves", "employee_files"):
        assert not Features.enabled(env["company_id"], key), key


def test_trial_gets_the_entry_plan(env):
    """
    والتجربة تُمنح **الباقة الأساسية** — أدنى المعروضة ترتيبًا.

    فالمجرّب يرى ما سيشتريه لا أكثر: سبعة أيام على الأساسية
    (قرار جواد).
    """
    Plan.objects.filter(id=env["basic"].id).update(tier_order=1,
                                                   is_public=True)
    Plan.objects.filter(id=env["top"].id).update(tier_order=3,
                                                 is_public=True)
    with account_scope(env["account_id"]):
        AccountSubscription.objects.filter(
            account_id=env["account_id"]).update(
                state=SubscriptionState.TRIAL, plan=None)
    Features.invalidate(env["company_id"])

    assert Features.enabled(env["company_id"], "payroll")
    assert not Features.enabled(env["company_id"], "api_access"), (
        "التجربة فتحت مزايا فوق الأساسية")
