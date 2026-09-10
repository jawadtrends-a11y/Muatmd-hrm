"""
الحقول المتاحة لباني التقارير (ق-126).

⚠️ **معلَنة لا حرّة**: أعمدة القاعدة فيها ما لا يخصّ العميل —
مفاتيح داخلية، وحقول محذوفة، وبيانات غيره. فاختيارها حرًّا يكشف ما
لا يُكشف، ويكسر التقرير كلّما تغيّر عمود.

وكل حقل يُعلَن بـ:
  key      — المفتاح الذي يُحفظ في التقرير
  path     — مسار ORM من نموذج المصدر
  label_ar — ما يراه العميل
  kind     — text · number · date · money · bool
  perm     — صلاحيةٌ إضافية إن كان الحقل حسّاسًا (الراتب مثلًا)
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BuilderField:
    key: str
    path: str
    label_ar: str
    label_en: str = ""
    kind: str = "text"
    perm: str = ""
    total: bool = False


def _f(key, path, ar, en="", kind="text", perm="", total=False):
    return BuilderField(key, path, ar, en, kind, perm, total)


# ══════════ الموظفون ══════════
EMPLOYEE_FIELDS = [
    _f("employee_no", "employee_no", "الرقم الوظيفي", "Employee no"),
    _f("name_ar", "person__first_name_ar", "الاسم الأول", "First name"),
    _f("family_ar", "person__family_name_ar", "اسم العائلة",
       "Family name"),
    _f("name_en", "person__full_name_en", "الاسم بالإنجليزية", "Name (EN)"),
    _f("id_number", "person__id_number", "رقم الهوية", "ID number"),
    _f("nationality", "person__nationality_code", "الجنسية", "Nationality"),
    _f("gender", "person__gender", "الجنس", "Gender"),
    _f("birth_date", "person__birth_date", "تاريخ الميلاد", "Birth date",
       "date"),
    _f("mobile", "person__mobile_e164", "الجوال", "Mobile"),
    _f("email", "person__email", "البريد", "Email"),
    _f("job_title", "job_title__name_ar", "المسمى الوظيفي", "Job title"),
    _f("department", "department__name_ar", "الإدارة", "Department"),
    _f("branch", "branch__name_ar", "الفرع", "Branch"),
    _f("manager", "direct_manager__person__first_name_ar",
       "المدير المباشر", "Manager"),
    _f("grade", "job_grade__name_ar", "الدرجة", "Grade"),
    _f("join_date", "join_date", "تاريخ الالتحاق", "Join date", "date"),
    _f("service_start", "service_start_date", "بداية الخدمة",
       "Service start", "date"),
    _f("probation_end", "probation_end_date", "انتهاء التجربة",
       "Probation end", "date"),
    _f("contract_type", "contract_type", "نوع العقد", "Contract type"),
    _f("contract_end", "contract_end_date", "انتهاء العقد",
       "Contract end", "date"),
    _f("employment_type", "employment_type", "نوع التوظيف",
       "Employment type"),
    _f("status", "status", "الحالة", "Status"),
    _f("cost_center", "cost_center__name_ar", "مركز التكلفة",
       "Cost center"),
    # ⚠️ حقلٌ حسّاس في مصدرٍ عاديّ — يُصفّى بالصلاحية لا يُخفى
    # بالمصدر: فتقرير الموظفين قد يُشارَك مع من لا يرى الرواتب.
    _f("iban", "iban", "الآيبان", "IBAN", "text", "payroll.view"),
    _f("termination_date", "termination_date", "تاريخ إنهاء الخدمة",
       "Termination date", "date"),
    _f("id_expiry", "person__id_expiry_date", "انتهاء الهوية",
       "ID expiry", "date"),
]

# ══════════ الحضور ══════════
ATTENDANCE_FIELDS = [
    _f("employee_no", "employment__employee_no", "الرقم الوظيفي",
       "Employee no"),
    _f("name_ar", "employment__person__first_name_ar",
       "الاسم الأول", "First name"),
    _f("family_ar", "employment__person__family_name_ar",
       "اسم العائلة", "Family name"),
    _f("department", "employment__department__name_ar", "الإدارة",
       "Department"),
    _f("work_date", "work_date", "التاريخ", "Date", "date"),
    _f("status", "status", "الحالة", "Status"),
    _f("first_in", "first_in", "أول حضور", "First in"),
    _f("last_out", "last_out", "آخر انصراف", "Last out"),
    _f("worked_minutes", "worked_minutes", "دقائق العمل", "Worked minutes",
       "number", total=True),
    _f("late_minutes", "late_minutes", "دقائق التأخير", "Late minutes",
       "number", total=True),
    _f("early_out_minutes", "early_out_minutes", "دقائق الانصراف المبكّر",
       "Early out", "number", total=True),
    _f("overtime_minutes", "overtime_minutes", "دقائق الإضافي",
       "Overtime", "number", total=True),
    _f("note", "adjustment_note", "ملاحظة", "Note"),
]

# ══════════ الطلبات ══════════
#
# ⚠️ الإجازة **طلبٌ بنوع** لا نموذجٌ مستقلّ — فمصدر «الطلبات»
# يشمل العشرين نوعًا، وهو أنفع من الإجازات وحدها.
REQUEST_FIELDS = [
    _f("request_no", "request_no", "رقم الطلب", "Request no"),
    _f("employee_no", "employment__employee_no", "الرقم الوظيفي",
       "Employee no"),
    _f("name_ar", "employment__person__first_name_ar", "الاسم الأول",
       "First name"),
    _f("family_ar", "employment__person__family_name_ar", "اسم العائلة",
       "Family name"),
    _f("department", "employment__department__name_ar", "الإدارة",
       "Department"),
    _f("branch", "employment__branch__name_ar", "الفرع", "Branch"),
    _f("request_type", "request_type", "نوع الطلب", "Type"),
    _f("status", "status", "الحالة", "Status"),
    _f("channel", "channel", "القناة", "Channel"),
    _f("submitted_at", "submitted_at", "تاريخ التقديم", "Submitted",
       "date"),
    _f("closed_at", "closed_at", "تاريخ الإغلاق", "Closed", "date"),
    _f("note", "note", "الملاحظة", "Note"),
]

# ══════════ الرواتب ══════════
# ⚠️ كلّها تحتاج صلاحية الرواتب — فالراتب لا يُبنى عنه تقريرٌ
# بصلاحية عرض الموظفين.
PAYROLL_FIELDS = [
    _f("employee_no", "employment__employee_no", "الرقم الوظيفي",
       "Employee no", perm="payroll.view"),
    _f("name_ar", "employment__person__first_name_ar", "الاسم الأول",
       "First name", perm="payroll.view"),
    _f("family_ar", "employment__person__family_name_ar",
       "اسم العائلة", "Family name", perm="payroll.view"),
    _f("department", "employment__department__name_ar", "الإدارة",
       "Department", perm="payroll.view"),
    _f("year", "run__period_year", "السنة", "Year", "number",
       perm="payroll.view"),
    _f("month", "run__period_month", "الشهر", "Month", "number",
       perm="payroll.view"),
    _f("gross", "gross_earnings", "إجمالي الاستحقاق", "Gross", "money",
       "payroll.view", True),
    _f("deductions", "total_deductions", "إجمالي الخصومات", "Deductions",
       "money", "payroll.view", True),
    _f("net", "net_pay", "صافي الراتب", "Net", "money",
       "payroll.view", True),
    _f("basic", "basic_salary", "الراتب الأساسي", "Basic",
       "money", "payroll.view", True),
    _f("worked_days", "worked_days", "أيام العمل",
       "Worked days", "number", "payroll.view", True),
    _f("gosi_employee", "gosi_employee_share", "حصة الموظف — تأمينات",
       "GOSI (employee)", "money", "payroll.view", True),
    _f("gosi_employer", "gosi_employer_share", "حصة الشركة — تأمينات",
       "GOSI (employer)", "money", "payroll.view", True),
]

FIELDS_BY_SOURCE = {
    "employees": EMPLOYEE_FIELDS,
    "attendance": ATTENDANCE_FIELDS,
    "requests": REQUEST_FIELDS,
    "payroll": PAYROLL_FIELDS,
}


def fields_for(source):
    return FIELDS_BY_SOURCE.get(source, [])


def field_map(source):
    return {f.key: f for f in fields_for(source)}
