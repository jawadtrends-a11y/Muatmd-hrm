"""
سجل المزايا — كل ميزة في النظام مسجّلة هنا.

الفرق عن الصلاحيات: الميزة تحددها الباقة (ما اشتراه العميل)،
والصلاحية يحددها الدور (ما يخوّله منصبه).
راجع الوثيقة المعمارية (3) القسم 2.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    module: str
    name_ar: str
    value_type: str = "bool"
    is_core: bool = False


def _f(key, module, name_ar, value_type="bool", is_core=False):
    return FeatureSpec(key, module, name_ar, value_type, is_core)


FEATURES = [
    # أساسية — في كل الباقات
    _f("employee_files", "employees", "ملفات الموظفين", is_core=True),
    _f("attendance",     "attendance", "الحضور والانصراف", is_core=True),
    _f("leaves",         "leaves", "الإجازات", is_core=True),
    _f("requests",       "requests", "الطلبات", is_core=True),
    _f("payroll",        "payroll", "مسير الرواتب", is_core=True),
    _f("wps_export",     "payroll", "ملف حماية الأجور", is_core=True),

    # مميزة
    _f("letter_templates",   "documents", "نماذج خطابات الموظفين"),
    _f("employee_tracking",  "attendance", "تتبع الموظفين"),
    _f("advanced_reports",   "reports", "التقارير المتقدمة"),
    _f("approval_chains",    "requests", "سلاسل الاعتماد متعددة الدرجات"),
    _f("custom_roles",       "access", "إنشاء أدوار مخصصة"),

    # مؤسسية
    _f("whatsapp_ess",         "whatsapp", "الخدمة الذاتية عبر واتساب"),
    _f("nitaqat_simulator",    "compliance", "محاكي التوطين ونطاقات"),
    _f("compliance_dashboard", "compliance", "لوحة الامتثال"),
    _f("biometric_integration","attendance", "التكامل مع أجهزة البصمة"),
    _f("api_access",           "integration", "الوصول عبر API"),

    # حدود رقمية
    _f("max_branches",  "org", "عدد الفروع", value_type="int"),
    _f("max_companies", "account", "عدد الشركات", value_type="int"),
    _f("max_employees", "account", "عدد الموظفين", value_type="int"),
]

FEATURE_KEYS = {f.key for f in FEATURES}
FEATURES_BY_KEY = {f.key: f for f in FEATURES}
CORE_FEATURE_KEYS = {f.key for f in FEATURES if f.is_core}


def validate_feature_keys(keys):
    unknown = set(keys) - FEATURE_KEYS
    if unknown:
        raise ValueError(f"مزايا غير مسجّلة: {sorted(unknown)}")
    return True
