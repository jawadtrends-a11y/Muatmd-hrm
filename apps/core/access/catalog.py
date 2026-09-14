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
    #: ق-161: **الميزة التي تفتح هذه الصلاحية** — أو فراغٌ إن
    # كانت أساسية.
    #
    # ⚠️ **والصلاحية تبقى ظاهرة ويُحجب ضبطها** حين تكون ميزتها
    # خارج الباقة (قرار جواد): **فإخفاؤها يُضيّع فرصة بيع، وضبطُها
    # يمنح ما لم يُشترَ**.
    feature: str = ""


def _p(key, module, name_ar, name_en="", feature=""):
    return Permission(key=key, module=module, name_ar=name_ar,
                      name_en=name_en, feature=feature)


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
    # ق-102: الإعلانات — النطاق في اسم الصلاحية نفسها، فمدير
    # الإدارة يعلن لإدارته ولا يخاطب الشركة كلها.
    _p("announcements.view",           "announcements", "عرض الإعلانات",
       "View announcements"),
    _p("announcements.send_department", "announcements",
       "إرسال إعلان لإدارته", "Send announcement to own department"),
    _p("announcements.send_company",   "announcements",
       "إرسال إعلان لكل الشركة", "Send announcement company-wide"),
    _p("org.view",            "org", "عرض الهيكل التنظيمي", feature="org_structure"),
    _p("org.manage",          "org", "إدارة الفروع والأقسام والمسميات", feature="org_structure"),

    # الموظفون
    _p("employees.view",      "employees", "عرض موظفيه"),
    _p("employees.view_all",  "employees", "عرض كل موظفي المنشأة"),
    _p("employees.create",    "employees", "إضافة موظف"),
    _p("employees.edit",      "employees", "تعديل بيانات موظف"),
    _p("employees.terminate", "employees", "إنهاء خدمة موظف"),
    _p("employees.documents", "employees", "إدارة وثائق الموظفين"),
    # ق-94: الدعوة تفتح باب النظام — صلاحية مستقلّة عن تعديل
    # البيانات، فقد تريد الشركة من يعدّل ولا يدعو.
    _p("employees.invite",    "employees", "دعوة موظف للانضمام",
       "Invite employee to join"),
    _p("audit.view", "employees", "عرض سجل العمليات"),
    _p("persons.view_cross_company", "employees",
       "رؤية ارتباطات الشخص في شركات أخرى (بلا بيانات مالية)"),

    # الحضور
    _p("attendance.view",     "attendance", "عرض حضور موظفيه"),
    _p("attendance.view_all", "attendance", "عرض حضور كل المنشأة"),
    _p("attendance.edit",     "attendance", "تعديل سجلات الحضور", feature="manager_edit_hours"),
    _p("attendance.approve",  "attendance", "اعتماد تعديلات الحضور", feature="manager_edit_hours"),
    _p("attendance.shifts",   "attendance", "إدارة فترات العمل", feature="shifts"),
    # مواقع العمل: ثلاث صلاحيات منفصلة — فمن يُسنِد ليس بالضرورة
    # من يُنشئ، ومن يطّلع ليس بالضرورة من يُسنِد (ق-78)
    _p("sites.view",          "attendance", "عرض مواقع العمل", feature="employee_tracking"),
    _p("sites.assign",        "attendance", "إسناد موظفيه لمواقع العمل", feature="employee_tracking"),
    _p("sites.manage",        "attendance", "إضافة وتعديل مواقع العمل", feature="employee_tracking"),

    # الإجازات
    _p("leaves.view",         "leaves", "عرض إجازات موظفيه", feature="leaves"),
    _p("leaves.view_all",     "leaves", "عرض إجازات كل المنشأة", feature="leaves"),
    _p("leaves.create",       "leaves", "تقديم طلب إجازة", feature="req_leave"),
    _p("leaves.approve",      "leaves", "اعتماد إجازات موظفيه", feature="leaves"),
    _p("leaves.approve_all",  "leaves", "اعتماد إجازات كل المنشأة", feature="leaves"),
    _p("leaves.manage",       "leaves", "إدارة أنواع الإجازات والأرصدة", feature="custom_leave_types"),

    # الطلبات
    _p("requests.view",       "requests", "عرض طلبات موظفيه"),
    _p("requests.view_all",   "requests", "عرض طلبات كل المنشأة"),
    _p("requests.create",     "requests", "تقديم طلب"),
    _p("requests.approve",    "requests", "اعتماد طلبات موظفيه"),
    _p("requests.approve_all", "requests", "اعتماد طلبات كل المنشأة"),
    _p("requests.manage",     "requests", "إسناد طلب — تقديمه نيابةً عن موظف", feature="req_delegate_manager"),

    # الرواتب
    _p("payroll.view",        "payroll", "عرض المسيرات", feature="payroll"),
    _p("payroll.create",      "payroll", "إنشاء المسير واحتسابه", feature="payroll"),
    _p("payroll.submit",      "payroll", "رفع المسير للاعتماد", feature="payroll"),
    _p("payroll.approve",     "payroll", "اعتماد المسير", feature="payroll"),
    _p("payroll.export",      "payroll", "تصدير ملفات البنك وحماية الأجور", feature="wps_export"),
    _p("payroll.structures",  "payroll", "إدارة هياكل الرواتب والبدلات", feature="payroll"),

    # قسائم الرواتب
    _p("payslips.view_own",   "payroll", "عرض قسائم راتبي", feature="payroll"),
    _p("payslips.view_team",  "payroll", "عرض قسائم المرؤوسين (بعد الاعتماد)", feature="payroll"),
    _p("payslips.view_all",   "payroll", "عرض كل القسائم", feature="payroll"),

    # التوطين والامتثال
    _p("saudization.view",    "compliance", "عرض التوطين ونطاقات", feature="nitaqat_simulator"),
    _p("compliance.view",     "compliance", "عرض لوحة الامتثال", feature="compliance_dashboard"),

    # الصلاحيات وسلاسل الاعتماد
    _p("access.view",         "access", "عرض الأدوار والصلاحيات"),
    _p("access.manage",       "access", "إدارة الأدوار والصلاحيات"),
    _p("approvals.manage",    "access", "إدارة سلاسل الاعتماد", feature="approval_chains"),
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
