"""
الباقات الافتراضية — بذرة قابلة للتعديل بالكامل من لوحة السوبر أدمن.

قرار تجاري (الوثيقة المعمارية 3): واتساب ومحاكي نطاقات في الباقة
الأعلى وحدها — هما الميزتان اللتان لا يملكهما المنافسون، ويبرران
فارق السعر.
"""
from decimal import Decimal

from django.db import transaction

from apps.accounts.models_billing import (
    Feature, Plan, PlanFeature, PlanPriceTier,
)
from apps.core.features.catalog import CORE_FEATURE_KEYS, FEATURES, validate_feature_keys

DEFAULT_PLANS = {
    "basic": {
        "name_ar": "الباقة الأساسية",
        "tier": 1,
        "trial_days": 14,
        "min_billable": 1,
        "tiers": [
            (1, 25, Decimal("15.00")),
            (26, 100, Decimal("12.00")),
            (101, None, Decimal("10.00")),
        ],
        "features": {
            **{k: "true" for k in CORE_FEATURE_KEYS},
            "max_branches": "2",
            "max_companies": "1",
        },
    },
    "premium": {
        "name_ar": "الباقة المميزة",
        "tier": 2,
        "trial_days": 14,
        "min_billable": 1,
        "tiers": [
            (1, 25, Decimal("25.00")),
            (26, 100, Decimal("20.00")),
            (101, None, Decimal("17.00")),
        ],
        "features": {
            **{k: "true" for k in CORE_FEATURE_KEYS},
            "letter_templates": "true",
            "employee_tracking": "true",
            "advanced_reports": "true",
            "approval_chains": "true",
            "custom_roles": "true",
            "compliance_dashboard": "true",
            "max_branches": "10",
            "max_companies": "5",
        },
    },
    "enterprise": {
        "name_ar": "الباقة المؤسسية",
        "tier": 3,
        "trial_days": 30,
        "min_billable": 10,
        "tiers": [
            (1, 100, Decimal("40.00")),
            (101, 500, Decimal("32.00")),
            (501, None, Decimal("25.00")),
        ],
        "features": {
            **{k: "true" for k in CORE_FEATURE_KEYS},
            "letter_templates": "true",
            "employee_tracking": "true",
            "advanced_reports": "true",
            "approval_chains": "true",
            "custom_roles": "true",
            "compliance_dashboard": "true",
            # الميزتان الحاسمتان — هنا وحدهما
            "whatsapp_ess": "true",
            "nitaqat_simulator": "true",
            "biometric_integration": "true",
            "api_access": "true",
            "max_branches": "0",     # 0 = بلا حد
            "max_companies": "0",
        },
    },
}


@transaction.atomic
def sync_feature_registry():
    """يزامن سجل المزايا من الكتالوج. آمن للتكرار."""
    for i, spec in enumerate(FEATURES):
        Feature.objects.update_or_create(
            feature_key=spec.key,
            defaults={
                "module": spec.module,
                "name_ar": spec.name_ar,
                "value_type": spec.value_type,
                "is_core": spec.is_core,
                "sort_order": i,
            },
        )
    return Feature.objects.count()


@transaction.atomic
def sync_default_plans():
    """يزامن الباقات الافتراضية. آمن للتكرار."""
    results = {}
    for code, spec in DEFAULT_PLANS.items():
        validate_feature_keys(spec["features"].keys())

        plan, _ = Plan.objects.update_or_create(
            code=code,
            defaults={
                "name_ar": spec["name_ar"],
                "tier_order": spec["tier"],
                "trial_days": spec["trial_days"],
                "min_billable_employees": spec["min_billable"],
                "is_public": True,
                "is_active": True,
            },
        )

        plan.price_tiers.all().delete()
        PlanPriceTier.objects.bulk_create([
            PlanPriceTier(plan=plan, from_employees=lo, to_employees=hi,
                          price_per_employee_monthly=price,
                          price_per_employee_yearly=price * Decimal("10"))
            for lo, hi, price in spec["tiers"]
        ])

        plan.features.all().delete()
        PlanFeature.objects.bulk_create([
            PlanFeature(plan=plan, feature_key=k, value=v)
            for k, v in sorted(spec["features"].items())
        ])
        results[code] = len(spec["features"])
    return results
