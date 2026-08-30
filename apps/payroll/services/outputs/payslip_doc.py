"""
بيانات قسيمة الراتب — مستقلة عن صيغة العرض.

الفصل مقصود: هذه الطبقة تُنتج البيانات، وطبقة أخرى تحوّلها إلى
PDF أو HTML أو رسالة واتساب. فتغيير التصميم لا يمس المنطق.

ق-39: القسيمة للراتب وحده. حصة صاحب العمل ورصيد الإجازات ومقارنة
الشهر السابق مخفية افتراضًا، وتُعرض بإعداد صريح من الشركة.
"""
from dataclasses import dataclass, field
from decimal import Decimal

ZERO = Decimal("0")

MONTHS_AR = [
    "", "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]
MONTHS_EN = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTHS_UR = [
    "", "جنوری", "فروری", "مارچ", "اپریل", "مئی", "جون",
    "جولائی", "اگست", "ستمبر", "اکتوبر", "نومبر", "دسمبر",
]

LABELS = {
    "ar": {
        "title": "قسيمة راتب", "employee": "الموظف",
        "employee_no": "الرقم الوظيفي", "id_number": "رقم الهوية",
        "job_title": "المسمى الوظيفي", "department": "القسم",
        "period": "الفترة", "pay_date": "تاريخ الصرف",
        "earnings": "الاستحقاقات", "deductions": "الاستقطاعات",
        "total_earnings": "إجمالي الاستحقاقات",
        "total_deductions": "إجمالي الاستقطاعات",
        "net_pay": "صافي المستحق", "attendance": "الحضور",
        "worked_days": "أيام العمل", "absence_days": "أيام الغياب",
        "unpaid_leave": "إجازة بلا أجر", "overtime": "ساعات إضافية",
        "iban": "الآيبان", "explanation": "الاحتساب",
        "employer_cost": "تكلفة صاحب العمل",
        "leave_balance": "رصيد الإجازات",
        "previous_month": "الشهر السابق",
        "note": "هذه قسيمة إلكترونية لا تحتاج توقيعًا",
    },
    "en": {
        "title": "Payslip", "employee": "Employee",
        "employee_no": "Employee No.", "id_number": "ID Number",
        "job_title": "Job Title", "department": "Department",
        "period": "Period", "pay_date": "Payment Date",
        "earnings": "Earnings", "deductions": "Deductions",
        "total_earnings": "Total Earnings",
        "total_deductions": "Total Deductions",
        "net_pay": "Net Pay", "attendance": "Attendance",
        "worked_days": "Worked Days", "absence_days": "Absence Days",
        "unpaid_leave": "Unpaid Leave", "overtime": "Overtime Hours",
        "iban": "IBAN", "explanation": "Calculation",
        "employer_cost": "Employer Cost",
        "leave_balance": "Leave Balance",
        "previous_month": "Previous Month",
        "note": "This is an electronic payslip and requires no signature",
    },
    "ur": {
        "title": "تنخواہ کی پرچی", "employee": "ملازم",
        "employee_no": "ملازم نمبر", "id_number": "شناختی نمبر",
        "job_title": "عہدہ", "department": "شعبہ",
        "period": "مدت", "pay_date": "ادائیگی کی تاریخ",
        "earnings": "آمدنی", "deductions": "کٹوتیاں",
        "total_earnings": "کل آمدنی", "total_deductions": "کل کٹوتیاں",
        "net_pay": "خالص تنخواہ", "attendance": "حاضری",
        "worked_days": "کام کے دن", "absence_days": "غیر حاضری کے دن",
        "unpaid_leave": "بلا معاوضہ چھٹی", "overtime": "اضافی گھنٹے",
        "iban": "آئی بین", "explanation": "حساب",
        "employer_cost": "آجر کی لاگت",
        "leave_balance": "چھٹیوں کا بیلنس",
        "previous_month": "پچھلا مہینہ",
        "note": "یہ الیکٹرانک پرچی ہے، دستخط کی ضرورت نہیں",
    },
}


@dataclass
class PayslipDocument:
    locale: str
    labels: dict
    company_name: str
    period_label: str
    employee: dict
    earnings: list = field(default_factory=list)
    deductions: list = field(default_factory=list)
    attendance: list = field(default_factory=list)
    totals: dict = field(default_factory=dict)
    optional: dict = field(default_factory=dict)
    note: str = ""


def _month_name(month, locale):
    table = {"ar": MONTHS_AR, "en": MONTHS_EN, "ur": MONTHS_UR}
    return table.get(locale, MONTHS_AR)[month]


def _fmt(value):
    return f"{Decimal(value):,.2f}"


def build_payslip_document(slip, locale=None, settings_obj=None):
    """
    يبني بيانات القسيمة بلغة الموظف المفضلة.

    كل بند يحمل شرح احتسابه — الموظف يعيد الحساب بورقة وقلم،
    وهذا ما يُنهي أغلب النزاعات.
    """
    from apps.payroll.models import PayrollSettings

    emp = slip.employment
    person = emp.person
    loc = locale or person.preferred_locale or "ar"
    if loc not in LABELS:
        loc = "ar"
    labels = LABELS[loc]

    if settings_obj is None:
        settings_obj = PayrollSettings.objects.filter(
            company=slip.company).first()

    run = slip.run
    period = f"{_month_name(run.period_month, loc)} {run.period_year}"

    doc = PayslipDocument(
        locale=loc,
        labels=labels,
        company_name=slip.company.legal_name_ar,
        period_label=period,
        employee={
            "name": (person.full_name_en
                     if loc == "en" and person.full_name_en
                     else person.display_name),
            "employee_no": emp.employee_no,
            "id_number": person.id_number,
            "job_title": emp.job_title.name_ar if emp.job_title else "",
            "department": emp.department.name_ar if emp.department else "",
            "iban": slip.iban,
            "pay_date": str(run.payment_date or run.accrual_date),
        },
        note=labels["note"],
    )

    # ── البنود ──
    for line in slip.lines.order_by("display_order"):
        # اسم البند بلغة الموظف — محفوظ في البند لا مقروء من المكوّن،
        # فالقسيمة سجل تاريخي لا يتغير بتغيّر اسم المكوّن لاحقًا
        name = line.name_ar
        if loc == "en" and line.name_en:
            name = line.name_en
        elif loc == "ur" and line.name_ur:
            name = line.name_ur
        entry = {"name": name, "amount": _fmt(line.amount),
                 "explanation": line.explanation}
        if line.line_type == "earning":
            doc.earnings.append(entry)
        elif line.line_type == "deduction":
            doc.deductions.append(entry)

    # ── الحضور ──
    if slip.worked_days:
        doc.attendance.append({"label": labels["worked_days"],
                               "value": str(slip.worked_days)})
    if slip.unpaid_absence_days:
        doc.attendance.append({"label": labels["absence_days"],
                               "value": str(slip.unpaid_absence_days)})
    if slip.unpaid_leave_days:
        doc.attendance.append({"label": labels["unpaid_leave"],
                               "value": str(slip.unpaid_leave_days)})
    if slip.overtime_minutes:
        hours = Decimal(slip.overtime_minutes) / Decimal("60")
        doc.attendance.append({"label": labels["overtime"],
                               "value": f"{hours:.2f}"})

    doc.totals = {
        "earnings": _fmt(slip.gross_earnings),
        "deductions": _fmt(slip.total_deductions),
        "net": _fmt(slip.net_pay),
    }

    # ── الاختيارية (ق-39: مخفية افتراضًا) ──
    if settings_obj and settings_obj.payslip_show_employer_gosi:
        doc.optional["employer_cost"] = {
            "label": labels["employer_cost"],
            "value": _fmt(slip.employer_cost)}

    if settings_obj and settings_obj.payslip_show_previous_month:
        if slip.previous_net is not None:
            doc.optional["previous_month"] = {
                "label": labels["previous_month"],
                "value": _fmt(slip.previous_net),
                "variance": (f"{slip.variance_percent:+.2f}%"
                             if slip.variance_percent is not None else "")}

    if settings_obj and settings_obj.payslip_show_leave_balance:
        from apps.leaves.services.balances import balance_summary
        balances = balance_summary(emp, run.period_year)
        if balances:
            doc.optional["leave_balance"] = {
                "label": labels["leave_balance"],
                "items": [{"name": b["leave_type"], "available": b["available"]}
                          for b in balances if b["is_paid"]]}

    return doc


def to_dict(doc: PayslipDocument) -> dict:
    """للـAPI وقوالب العرض."""
    return {
        "locale": doc.locale,
        "labels": doc.labels,
        "company_name": doc.company_name,
        "period": doc.period_label,
        "employee": doc.employee,
        "earnings": doc.earnings,
        "deductions": doc.deductions,
        "attendance": doc.attendance,
        "totals": doc.totals,
        "optional": doc.optional,
        "note": doc.note,
    }
