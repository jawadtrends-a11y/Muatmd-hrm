"""حرّاس الاشتراكات والفوترة وبوابة المزايا."""
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Company
from apps.accounts.models_billing import (
    CompanyHeadcountDaily, CompanySubscription, SubscriptionStatus,
)
from apps.accounts.services.plans import sync_default_plans, sync_feature_registry
from apps.accounts.services.provisioning import provision_account
from apps.accounts.services.subscriptions import (
    SubscriptionError, change_plan, compute_charge, subscribe_company,
)
from apps.core.features.catalog import CORE_FEATURE_KEYS, FEATURES
from apps.core.features.gate import Features, FeatureNotInPlan, UnknownFeature
from apps.core.tenancy.context import account_scope


@pytest.fixture
def plans(db):
    sync_feature_registry()
    return sync_default_plans()


@pytest.fixture
def company(db, plans):
    acct = provision_account(
        slug="bill-test", display_name_ar="حساب فوترة",
        company_name_ar="شركة فوترة", is_sandbox=True,
    )
    with account_scope(acct.account_id):
        return Company.objects.get(id=acct.company_id)


@pytest.mark.django_db(transaction=True)
def test_core_features_available_without_subscription(company):
    """المزايا الأساسية متاحة حتى بلا اشتراك — لا يُقفل النظام."""
    for key in CORE_FEATURE_KEYS:
        assert Features.enabled(company.id, key)


@pytest.mark.django_db(transaction=True)
def test_enterprise_only_features(company):
    """واتساب ونطاقات في المؤسسية وحدها — قرار تجاري."""
    with account_scope(company.account_id):
        sub = subscribe_company(company=company, plan_code="premium")
        assert not Features.enabled(company.id, "whatsapp_ess")
        assert not Features.enabled(company.id, "nitaqat_simulator")
        change_plan(subscription=sub, new_plan_code="enterprise")
        assert Features.enabled(company.id, "whatsapp_ess")
        assert Features.enabled(company.id, "nitaqat_simulator")


@pytest.mark.django_db(transaction=True)
def test_feature_not_in_plan_raises_402(company):
    with account_scope(company.account_id):
        subscribe_company(company=company, plan_code="basic")
        with pytest.raises(FeatureNotInPlan) as exc:
            Features.require(company.id, "whatsapp_ess")
        assert exc.value.status_code == 402


@pytest.mark.django_db(transaction=True)
def test_unknown_feature_rejected(company):
    with pytest.raises(UnknownFeature):
        Features.enabled(company.id, "not_a_real_feature")


@pytest.mark.django_db(transaction=True)
def test_billing_uses_peak_not_last_day(company):
    """الذروة لا آخر يوم — يمنع التحايل بإيقاف الموظفين قبل الفوترة."""
    with account_scope(company.account_id):
        sub = subscribe_company(company=company, plan_code="basic")
        for i, n in enumerate([5, 20, 7, 3]):
            CompanyHeadcountDaily.objects.update_or_create(
                company=company,
                snapshot_date=sub.current_period_start + timedelta(days=i),
                defaults={"account_id": company.account_id,
                          "active_employments": n, "billable_employments": n},
            )
        line = compute_charge(sub)
        assert line.billed_headcount == 20, "الفوترة لم تعتمد الذروة"
        assert line.snapshot["peak_headcount"] == 20


@pytest.mark.django_db(transaction=True)
def test_min_billable_applies(company):
    """الحد الأدنى للفوترة يُطبَّق حتى لو قلّ العدد."""
    with account_scope(company.account_id):
        sub = subscribe_company(company=company, plan_code="enterprise")
        CompanyHeadcountDaily.objects.create(
            account_id=company.account_id, company=company,
            snapshot_date=sub.current_period_start,
            active_employments=3, billable_employments=3,
        )
        line = compute_charge(sub)
        assert line.billed_headcount == 10, "الحد الأدنى لم يُطبَّق"


@pytest.mark.django_db(transaction=True)
def test_price_tier_selected_by_headcount(company):
    """شريحة السعر تُختار حسب العدد — خصم الحجم يعمل."""
    with account_scope(company.account_id):
        sub = subscribe_company(company=company, plan_code="basic")
        CompanyHeadcountDaily.objects.create(
            account_id=company.account_id, company=company,
            snapshot_date=sub.current_period_start,
            active_employments=150, billable_employments=150,
        )
        line = compute_charge(sub)
        assert line.unit_price == Decimal("10.00"), "لم تُختر الشريحة الصحيحة"


@pytest.mark.django_db(transaction=True)
def test_downgrade_locks_never_deletes(company):
    """التنزيل يقفل ولا يحذف — قرار المالك."""
    with account_scope(company.account_id):
        sub = subscribe_company(company=company, plan_code="enterprise")
        r = change_plan(subscription=sub, new_plan_code="basic")
        assert r["direction"] == "downgrade"
        assert r["data_deleted"] is False
        assert "whatsapp_ess" in r["locked_features"]
        assert not Features.enabled(company.id, "whatsapp_ess")
        for key in CORE_FEATURE_KEYS:
            assert Features.enabled(company.id, key), "ميزة أساسية أُقفلت"


@pytest.mark.django_db(transaction=True)
def test_one_active_subscription_per_company(company):
    with account_scope(company.account_id):
        subscribe_company(company=company, plan_code="basic")
        with pytest.raises(SubscriptionError):
            subscribe_company(company=company, plan_code="premium")


@pytest.mark.django_db(transaction=True)
def test_suspended_blocks_writes_not_exports(company):
    """الإيقاف يمنع الكتابة لا القراءة والتصدير — قرار أخلاقي."""
    with account_scope(company.account_id):
        sub = subscribe_company(company=company, plan_code="basic")
        sub.status = SubscriptionStatus.SUSPENDED
        sub.save()
        assert not sub.allows_writes
        assert not sub.allows_payroll
        sub.status = SubscriptionStatus.GRACE
        assert sub.allows_writes
        assert not sub.allows_payroll, "فترة السماح يجب أن توقف الرواتب"


@pytest.mark.django_db(transaction=True)
def test_all_registry_features_registered(company):
    from apps.accounts.models_billing import Feature
    assert Feature.objects.count() == len(FEATURES)
