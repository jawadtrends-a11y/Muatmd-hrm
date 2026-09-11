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

# ق-123: توزيع المزايا على الباقات — **تراكميّ**: كلٌّ تشمل ما
# دونها، فالعرض يقول «تشمل مزايا الأساسية بالإضافة إلى…».
#
# ⚠️ **بالرموز لا بالأسماء**: الأسماء تُعدَّل من اللوحة والرموز
# تبقى. وما لا مفتاح له في الكتالوج يُرفض عند المزامنة.
BASIC_FEATURES = [
    "employee_list", "org_structure", "employee_directory",
    "mobile_punch", "web_punch", "shifts", "manager_add_punch",
    "manager_edit_hours", "attendance_exemption",
    "leaves",
    "req_leave", "req_permission", "req_attendance_fix",
    "req_asset", "req_resignation", "req_salary_letter", "ess_mobile",
    "payroll", "pay_additions", "pay_deductions",
    "attendance_deductions", "wps_export", "payroll_types",
    "custom_dashboards", "reports_basic", "support_basic",
]

PREMIUM_FEATURES = BASIC_FEATURES + [
    "allowances", "employee_tags", "tasks",
    "manager_edit_shift", "work_activities",
    "custom_leave_types", "leave_settlement",
    "req_advance", "req_travel_ticket", "req_overtime",
    "req_secondment", "req_remote_work", "req_profile_update",
    "req_swap_restday", "req_custom_payment", "req_grievance",
    "req_offsite", "req_purchase", "req_shift_change",
    "req_salary_certificate", "req_delegate_manager",
    "approval_chains", "advances", "expenses",
    "recurring_adjustments", "payslip_defer", "payroll_approval_chain",
    "penalties", "auto_attendance_penalties",
    # ق-130: التنقيح المؤرَّخ — تحتاجه الشركات المتوسطة فصاعدًا
    "penalty_policy_versions",
    "dashboard_widgets", "advanced_reports",
    "letter_templates", "custom_roles", "support_group_courses",
]

ENTERPRISE_FEATURES = PREMIUM_FEATURES + [
    "biometric_devices", "employee_tracking", "req_custom",
    "payroll_excel_templates", "custom_report_builder",
    "performance", "training", "policies",
    "third_party_services", "erp_integration", "api_access",
    "whatsapp_ess", "support_pro",
]

# ⚠️ **مخفيّة حتى الاعتماد** كمورّد لدى الجهات (قرار جواد) —
# فلا نبيع ربطًا لا نملك صلاحيته.
GOVERNMENT_FEATURES = ENTERPRISE_FEATURES + [
    "gov_gosi", "gov_mudad", "gov_qiwa", "gov_muqeem",
    "nitaqat_simulator", "compliance_dashboard", "support_advanced",
]


def _feats(keys, **limits):
    out = {k: "true" for k in keys}
    out.update(limits)
    return out


DEFAULT_PLANS = {
    "basic": {
        "name_ar": "الباقة الأساسية",
        "tier": 1,
        "trial_days": 7,
        "min_billable": 1,
        "tiers": [(1, None, Decimal("15.00"))],
        "features": _feats(BASIC_FEATURES, max_branches="2",
                           max_companies="1", max_employees="0"),
    },
    "premium": {
        "name_ar": "الباقة المميزة",
        "tier": 2,
        "trial_days": 7,
        "min_billable": 1,
        "tiers": [(1, None, Decimal("25.00"))],
        "features": _feats(PREMIUM_FEATURES, max_branches="10",
                           max_companies="3", max_employees="0"),
    },
    "enterprise": {
        "name_ar": "الباقة المؤسسية",
        "tier": 3,
        "trial_days": 7,
        "min_billable": 10,
        "tiers": [(1, None, Decimal("40.00"))],
        "features": _feats(ENTERPRISE_FEATURES, max_branches="0",
                           max_companies="0", max_employees="0"),
    },
    "government": {
        "name_ar": "الباقة الحكومية",
        "tier": 4,
        "trial_days": 7,
        "min_billable": 10,
        "is_public": False,
        "tiers": [(1, None, Decimal("60.00"))],
        "features": _feats(GOVERNMENT_FEATURES, max_branches="0",
                           max_companies="0", max_employees="0"),
    },
}


@transaction.atomic
def sync_feature_registry():
    """
    يزرع سجل المزايا من الكتالوج — **بذرةٌ لا سيادة** (ق-123).

    ⚠️ القاعدة مصدر الحقيقة: ما عدّله المشغّل من اللوحة لا
    يُداس. فالاسم والوصف والترتيب تُزرع مرّةً ثم تُترك، ويبقى
    الكتالوج مرجعًا لـ**الحراسة** وحدها (`is_implemented`
    و`guarded_at`) — إذ لا يعرفها إلا الكود.
    """
    created = 0
    for i, spec in enumerate(FEATURES):
        obj, is_new = Feature.objects.get_or_create(
            feature_key=spec.key,
            defaults={
                "module": spec.module,
                "name_ar": spec.name_ar,
                "value_type": spec.value_type,
                "is_core": spec.is_core,
                "sort_order": i * 10,
            },
        )
        created += int(is_new)
        # الحراسة من الكود دائمًا — فهي حقيقةٌ تقنية لا تفضيل
        # مشغّل: ميزةٌ بلا حارس لا تصير محروسة بضغطة زرّ.
        if (obj.is_implemented != spec.implemented
                or obj.guarded_at != spec.guarded_at):
            obj.is_implemented = spec.implemented
            obj.guarded_at = spec.guarded_at
            obj.save(update_fields=["is_implemented", "guarded_at"])
    return {"total": Feature.objects.count(), "created": created}


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
                # ⚠️ ق-123: المخفيّة تبقى مخفيّة — الحكومية لا
                # تُعرض حتى الاعتماد كمورّد لدى الجهات.
                "is_public": spec.get("is_public", True),
                "is_active": True,
            },
        )

        plan.price_tiers.all().delete()
        PlanPriceTier.objects.bulk_create([
            PlanPriceTier(plan=plan, from_employees=lo, to_employees=hi,
                          price_per_employee_monthly=price,
                          # السعر السنوي = الشهري × 12 بلا خصم مدفون.
                          # الخصم السنوي قرار تجاري يضبطه السوبر
                          # أدمن من لوحة الخصومات (ق-47) — فيبقى
                          # مرئيًا ومتغيّرًا لا رقمًا في الكود
                          price_per_employee_yearly=price * Decimal("12"))
            for lo, hi, price in spec["tiers"]
        ])

        plan.features.all().delete()
        PlanFeature.objects.bulk_create([
            PlanFeature(plan=plan, feature_key=k, value=v)
            for k, v in sorted(spec["features"].items())
        ])
        results[code] = len(spec["features"])
    return results
