"""
سجل المزايا (ق-123).

⚠️ **القاعدة مصدر الحقيقة لا هذا الملفّ**: ما هنا **بذرةٌ أوّلية**
تُزرع مرّةً، ثم تُدار المزايا من لوحة المنصّة — تُضاف وتُعدَّل
وتُفعَّل بلا نشر.

والفرق عن الصلاحيات: **الميزة تحدّدها الباقة** (ما اشتراه
العميل)، **والصلاحية يحدّدها الدور** (ما يخوّله منصبه).

⚠️ و`is_implemented` يمنع بيع الوهم: ميزةٌ بلا حارس في الكود لا
تُعرض في الباقات ولا تُباع.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    module: str
    name_ar: str
    value_type: str = "bool"
    is_core: bool = False
    implemented: bool = False
    guarded_at: str = ""


def _f(key, module, name_ar, value_type="bool", implemented=False,
       guarded_at=""):
    return FeatureSpec(key, module, name_ar, value_type, False,
                       implemented, guarded_at)


FEATURES = [
    # ══ الموظفون ══
    _f("employee_list", "employees", "قائمة الموظفين",
       implemented=True, guarded_at="/api/employees/"),
    _f("org_structure", "employees", "الهيكل التنظيمي",
       implemented=True, guarded_at="/api/org/"),
    _f("allowances", "employees", "المخصصات",
       implemented=True, guarded_at="/api/payroll/components/"),
    _f("employee_directory", "employees", "دليل الموظفين",
       implemented=True, guarded_at="/api/directory/"),
    _f("employee_tags", "employees", "وسوم الموظفين",
       implemented=True, guarded_at="/api/tags/"),
    _f("tasks", "employees", "المهام",
       implemented=True, guarded_at="/api/tasks/"),

    # ══ الحضور والانصراف ══
    _f("biometric_devices", "attendance", "الربط مع أجهزة البصمة"),
    _f("mobile_punch", "attendance", "التحضير عن طريق تطبيق الجوال",
       implemented=True, guarded_at="/api/me/punch/"),
    _f("web_punch", "attendance", "التحضير عن طريق تطبيق الويب",
       implemented=True, guarded_at="/api/me/punch/"),
    _f("attendance_exemption", "attendance", "الإعفاء من الحضور والانصراف",
       implemented=True, guarded_at="/api/attendance/exemptions/"),
    _f("shifts", "attendance", "فترات العمل اليومية",
       implemented=True, guarded_at="/api/attendance/shifts/"),
    _f("manager_add_punch", "attendance", "إضافة سجل بصمة من المدير",
       implemented=True, guarded_at="/api/attendance/punches/"),
    _f("manager_edit_shift", "attendance", "تعديل فترات العمل من المدير",
       implemented=True, guarded_at="/api/attendance/shifts/"),
    _f("manager_edit_hours", "attendance", "تعديل ساعات الحضور من المدير",
       implemented=True, guarded_at="/api/attendance/days/"),
    _f("employee_tracking", "attendance", "تتبع الموظفين"),
    _f("work_activities", "attendance", "أنشطة العمل"),

    # ══ الإجازات ══
    _f("leaves", "leaves", "الإجازات",
       implemented=True, guarded_at="/api/leaves/"),
    _f("custom_leave_types", "leaves", "إضافة أنواع إجازات مخصصة",
       implemented=True, guarded_at="/api/settings/leave-types/"),
    _f("leave_settlement", "leaves", "مخالصة الإجازة",
       implemented=True, guarded_at="/api/employees/<id>/leave-cashout/"),

    # ══ الخدمات الذاتية ══
    _f("req_permission", "requests", "طلب استئذان",
       implemented=True, guarded_at="RequestType.permission"),
    _f("req_attendance_fix", "requests", "طلب فقدان بصمة",
       implemented=True, guarded_at="RequestType.attendance_fix"),
    _f("req_swap_restday", "requests", "طلب تبديل يوم راحة",
       implemented=True, guarded_at="RequestType.swap_restday"),
    _f("ess_mobile", "requests", "الخدمات الذاتية عبر تطبيق الجوال",
       implemented=True, guarded_at="/api/me/"),
    _f("req_custom_payment", "requests", "طلب صرف مخصص",
       implemented=True, guarded_at="RequestType.custom_payment"),
    _f("req_grievance", "requests", "طلب تظلم",
       implemented=True, guarded_at="RequestType.grievance"),
    _f("req_leave", "requests", "طلب إجازة",
       implemented=True, guarded_at="RequestType.leave"),
    _f("req_advance", "requests", "طلب سلفة",
       implemented=True, guarded_at="RequestType.advance"),
    _f("req_delegate_manager", "requests", "إسناد الطلبات بالنيابة من المدير",
       implemented=True, guarded_at="/api/leaves/delegations/"),
    _f("req_offsite", "requests", "طلب دوام خارج المكتب",
       implemented=True, guarded_at="RequestType.offsite"),
    _f("req_overtime", "requests", "طلب دوام إضافي",
       implemented=True, guarded_at="RequestType.overtime"),
    _f("req_secondment", "requests", "طلب انتداب",
       implemented=True, guarded_at="RequestType.business_trip"),
    _f("req_purchase", "requests", "طلب مشتريات",
       implemented=True, guarded_at="RequestType.purchase"),
    _f("req_resignation", "requests", "طلب استقالة",
       implemented=True, guarded_at="RequestType.resignation"),
    _f("req_salary_letter", "requests", "طلب تعريف بالراتب",
       implemented=True, guarded_at="RequestType.certificate"),
    _f("req_profile_update", "requests", "طلب تحديث بيانات موظف",
       implemented=True, guarded_at="RequestType.profile_update"),
    _f("req_shift_change", "requests", "طلب تغيير فترة عمل",
       implemented=True, guarded_at="RequestType.shift_change"),
    _f("req_travel_ticket", "requests", "طلب تذاكر سفر",
       implemented=True, guarded_at="RequestType.ticket"),
    _f("req_salary_certificate", "requests", "طلب تثبيت الراتب",
       implemented=True, guarded_at="RequestType.salary_fix"),
    _f("req_custom", "requests", "إنشاء طلبات مخصصة",
       implemented=True, guarded_at="/api/custom-request-types/"),
    _f("req_remote_work", "requests", "طلب عمل عن بعد",
       implemented=True, guarded_at="RequestType.remote_work"),
    _f("req_asset", "requests", "طلب عهدة",
       implemented=True, guarded_at="RequestType.asset"),
    _f("approval_chains", "requests", "سلاسل الاعتماد متعددة الدرجات",
       implemented=True, guarded_at="/api/leaves/chains/"),

    # ══ مسير الرواتب ══
    _f("payroll", "payroll", "مسير الرواتب",
       implemented=True, guarded_at="/api/payroll/"),
    _f("pay_additions", "payroll", "الإضافات",
       implemented=True, guarded_at="/api/payroll/adjustments/"),
    _f("pay_deductions", "payroll", "الحسومات",
       implemented=True, guarded_at="/api/payroll/adjustments/"),
    _f("attendance_deductions", "payroll", "حساب حسومات الحضور والانصراف",
       implemented=True, guarded_at="engine.absence_deduction"),
    _f("expenses", "payroll", "المصروفات",
       implemented=True, guarded_at="/api/expenses/"),
    _f("advances", "payroll", "السلف والذمم",
       implemented=True, guarded_at="/api/advances/"),
    # ⚠️ أُعيد تعريفها (ق-141): **قوالب تصدير** تختار الشركة
    # أعمدتها — لا استيرادًا من ملفّ، فالبنود تأتي من النظام
    # نفسه (سلف ومكرّرة ومصروفات وجزاءات).
    _f("payroll_excel_templates", "payroll", "قوالب تصدير المسير"),
    _f("payslip_defer", "payroll", "تأجيل بنود القسيمة",
       implemented=True, guarded_at="/api/deferrals/"),
    _f("payroll_types", "payroll", "أنواع مسيرات الرواتب",
       implemented=True, guarded_at="PayrollRunType"),
    _f("payroll_approval_chain", "payroll", "سلسلة موافقات مسير الرواتب",
       implemented=True, guarded_at="/api/payroll/approval-steps/"),
    _f("recurring_adjustments", "payroll", "حسومات وإضافات مكررة",
       implemented=True, guarded_at="/api/recurring/"),
    _f("wps_export", "payroll", "ملف حماية الأجور",
       implemented=True, guarded_at="/api/payroll/<id>/bank-file/"),

    # ══ لوحات القيادة ══
    _f("custom_dashboards", "core", "لوحات قيادة مخصصة",
       implemented=True, guarded_at="/api/me/dashboard/"),
    _f("dashboard_widgets", "core", "تخصيص النوافذ في لوحات القيادة",
       implemented=True, guarded_at="/api/me/dashboard/"),

    # ══ المخالفات والجزاءات ══
    _f("penalties", "penalties", "المخالفات والجزاءات",
       implemented=True, guarded_at="/api/penalties/"),
    _f("auto_attendance_penalties", "penalties",
       "احتساب مخالفات الحضور والانصراف آليًّا",
       implemented=True, guarded_at="/api/penalties/board/"),
    # ق-130: التنقيح المؤرَّخ — ميزةٌ مستقلّة (قرار جواد)
    _f("penalty_policy_versions", "penalties",
       "نسخ لائحة الجزاءات بتواريخ سريانها",
       implemented=True, guarded_at="penalties.revise"),

    # ══ التقارير ══
    _f("reports_basic", "reports", "التقارير الأساسية",
       implemented=True, guarded_at="/api/reports/"),
    # ستّة تقارير مالية محروسة في run_report — والحراسة بالمفتاح
    # لا بالمسار: التقرير الماليّ ليس كتقرير الحضور.
    _f("advanced_reports", "reports", "التقارير المتقدمة",
       implemented=True, guarded_at="/api/reports/<key>/"),
    _f("custom_report_builder", "reports", "باني التقارير المخصصة",
       implemented=True, guarded_at="/api/reports/custom/"),

    # ══ الأداء والتطوير ══
    _f("performance", "performance", "الأداء والتقييم"),
    _f("training", "performance", "التدريب"),

    # ══ أخرى ══
    _f("third_party_services", "integration", "خدمات الطرف الثالث"),
    _f("policies", "documents", "السياسات",
       implemented=True, guarded_at="/api/policies/"),
    _f("letter_templates", "documents", "النماذج والقوالب",
       implemented=True, guarded_at="/api/letters/templates/"),
    _f("custom_roles", "access", "إنشاء أدوار مخصصة",
       implemented=True, guarded_at="/api/access/roles/create/"),
    _f("erp_integration", "integration", "التكامل مع الأنظمة المحاسبية وERP"),
    _f("api_access", "integration", "واجهة برمجة التطبيقات API"),
    _f("whatsapp_ess", "integration", "الخدمة الذاتية عبر واتساب"),

    # ══ الربط الحكومي ══
    # ⚠️ يُبنى كاملًا ولا يُعرض حتى الاعتماد كمورّد لدى الجهات
    # (قرار جواد) — فلا نبيع ربطًا لا نملك صلاحيته.
    _f("gov_gosi", "government", "الربط مع التأمينات الاجتماعية"),
    _f("gov_mudad", "government", "الربط مع مدد"),
    _f("gov_qiwa", "government", "الربط مع قوى"),
    _f("gov_muqeem", "government", "الربط مع مقيم"),
    _f("nitaqat_simulator", "government", "محاكي التوطين ونطاقات"),
    _f("compliance_dashboard", "government", "لوحة الامتثال"),

    # ══ الدعم ══
    # ق-133: الدعم مستوى خدمةٍ يُقاس — المهلة من الباقة، وتُختم
    # بوقت أول ردّ فيُعلَم من تجاوزناه.
    _f("support_basic", "support", "دعم أساسي — ردّ خلال ٢٤ ساعة",
       implemented=True, guarded_at="tickets.PLAN_SLA"),
    _f("support_group_courses", "support", "دورات أونلاين جماعية"),
    _f("support_pro", "support", "دعم احترافي — ردّ خلال ٨ ساعات عمل",
       implemented=True, guarded_at="tickets.PLAN_SLA"),
    _f("support_advanced", "support", "دعم متقدم — ردّ خلال ساعتَي عمل",
       implemented=True, guarded_at="tickets.PLAN_SLA"),

    # ══ الحدود العددية ══
    _f("max_companies", "account", "عدد الشركات", value_type="int"),
    _f("max_branches", "org", "عدد الفروع", value_type="int",
       implemented=True, guarded_at="structure._check_limit"),
    _f("max_employees", "account", "عدد الموظفين", value_type="int"),
]

FEATURE_KEYS = {f.key for f in FEATURES}
FEATURES_BY_KEY = {f.key: f for f in FEATURES}

# ⚠️ لم تعد ثمّة مزايا «أساسية مجّانية» (ق-118): الباقة الأساسية
# تُنال بالاشتراك، والتجربة سبعة أيام عليها.
CORE_FEATURE_KEYS = set()


def validate_feature_keys(keys):
    """
    ⚠️ يفحص **القاعدة** لا هذا الملفّ — فالمزايا تُضاف من اللوحة،
    والفحص بالكتالوج وحده يرفض ما أضافه المشغّل بحقّ.
    """
    from apps.accounts.models_billing import Feature

    known = set(Feature.objects.values_list("feature_key", flat=True))
    known |= FEATURE_KEYS
    unknown = set(keys) - known
    if unknown:
        raise ValueError(f"مزايا غير مسجّلة: {sorted(unknown)}")
    return True
