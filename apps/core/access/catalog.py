"""
كتالوج الصلاحيات — مصدر الحقيقة الوحيد.

الصلاحيات ثابتة في الكود (يعرفها المطوّر)، والأدوار بيانات مرنة
(يضبطها العميل). هذا ما يمنع فوضى الـ774 صلاحية في النظام القديم.

النمط: <وحدة>.<فعل>  — مثال: employees.view
"""
from dataclasses import dataclass
from enum import Enum


class Scope(str, Enum):
    """نطاق البيانات المسموح بها — مرتّبة من الأضيق للأوسع."""
    OWN        = "own"          # نفسه فقط
    TEAM       = "team"         # مرؤوسوه المباشرون
    DEPARTMENT = "department"   # قسمه
    BRANCH     = "branch"       # فرعه
    COMPANY    = "company"      # الشركة النشطة كاملة
    ACCOUNT    = "account"      # كل شركات الحساب

    @property
    def rank(self) -> int:
        return list(Scope).index(self)


@dataclass(frozen=True)
class Permission:
    key: str
    module: str
    name_ar: str
    name_en: str = ""


def _p(key, module, name_ar, name_en=""):
    return Permission(key=key, module=module, name_ar=name_ar, name_en=name_en)


# ══════════ الكتالوج ══════════
# نمط موحّد لكل ما يمر بدورة: view / create / submit / approve / manage
# مَن يعتمد فعليًا تحدده سلسلة الاعتماد لا الصلاحية وحدها.
PERMISSIONS = [
    # الحساب والشركات
    _p("account.view",        "account", "عرض بيانات الحساب"),
    _p("account.manage",      "account", "إدارة إعدادات الحساب"),
    _p("company.view",        "account", "عرض الشركات"),
    _p("company.create",      "account", "إضافة شركة"),
    _p("company.edit",        "account", "تعديل بيانات الشركة"),

    # الهيكل التنظيمي
    _p("org.view",            "org", "عرض الهيكل التنظيمي"),
    _p("org.manage",          "org", "إدارة الفروع والأقسام والمسميات"),

    # الموظفون
    _p("employees.view",      "employees", "عرض الموظفين"),
    _p("employees.create",    "employees", "إضافة موظف"),
    _p("employees.edit",      "employees", "تعديل بيانات موظف"),
    _p("employees.terminate", "employees", "إنهاء خدمة موظف"),
    _p("employees.documents", "employees", "إدارة وثائق الموظفين"),
    _p("persons.view_cross_company", "employees",
       "رؤية ارتباطات الشخص في شركات أخرى (بلا بيانات مالية)"),

    # الحضور
    _p("attendance.view",     "attendance", "عرض الحضور"),
    _p("attendance.edit",     "attendance", "تعديل سجلات الحضور"),
    _p("attendance.approve",  "attendance", "اعتماد تعديلات الحضور"),
    _p("attendance.shifts",   "attendance", "إدارة الورديات"),

    # الإجازات
    _p("leaves.view",         "leaves", "عرض الإجازات"),
    _p("leaves.create",       "leaves", "تقديم طلب إجازة"),
    _p("leaves.approve",      "leaves", "اعتماد الإجازات"),
    _p("leaves.manage",       "leaves", "إدارة أنواع الإجازات والأرصدة"),

    # الطلبات
    _p("requests.view",       "requests", "عرض الطلبات"),
    _p("requests.create",     "requests", "تقديم طلب"),
    _p("requests.approve",    "requests", "اعتماد الطلبات"),
    _p("requests.manage",     "requests", "إدارة أنواع الطلبات"),

    # الرواتب
    _p("payroll.view",        "payroll", "عرض المسيرات"),
    _p("payroll.create",      "payroll", "إنشاء المسير واحتسابه"),
    _p("payroll.submit",      "payroll", "رفع المسير للاعتماد"),
    _p("payroll.approve",     "payroll", "اعتماد المسير"),
    _p("payroll.export",      "payroll", "تصدير ملفات البنك وحماية الأجور"),
    _p("payroll.structures",  "payroll", "إدارة هياكل الرواتب والبدلات"),

    # قسائم الرواتب
    _p("payslips.view_own",   "payroll", "عرض قسائم راتبي"),
    _p("payslips.view_team",  "payroll", "عرض قسائم المرؤوسين (بعد الاعتماد)"),
    _p("payslips.view_all",   "payroll", "عرض كل القسائم"),

    # التوطين والامتثال
    _p("saudization.view",    "compliance", "عرض التوطين ونطاقات"),
    _p("compliance.view",     "compliance", "عرض لوحة الامتثال"),

    # الصلاحيات وسلاسل الاعتماد
    _p("access.view",         "access", "عرض الأدوار والصلاحيات"),
    _p("access.manage",       "access", "إدارة الأدوار والصلاحيات"),
    _p("approvals.manage",    "access", "إدارة سلاسل الاعتماد"),
]

# ══ الحد الأدنى المحمي ══
# صلاحيات لا يجوز نزعها من دور المالك، وإلا أُقفل الحساب على صاحبه.
PROTECTED_OWNER_PERMISSIONS = {
    "account.view", "account.manage", "access.view", "access.manage",
}

PERMISSION_KEYS = {p.key for p in PERMISSIONS}
PERMISSIONS_BY_KEY = {p.key: p for p in PERMISSIONS}


def validate_keys(keys):
    """يرفع خطأً عند أي مفتاح غير مسجّل — يمنع الصلاحيات اليتيمة."""
    unknown = set(keys) - PERMISSION_KEYS
    if unknown:
        raise ValueError(f"صلاحيات غير مسجّلة في الكتالوج: {sorted(unknown)}")
    return True
