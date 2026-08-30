"""
مولّد ملفات البنوك.

القالب بيانات لا كود: الشركة تضبط الأعمدة وترتيبها ومصادرها،
فبنك جديد لا يحتاج نشر إصدار.

⚠️ لا يُبنى قالب من تخمين — البنك يسلّم مواصفاته عند اتفاقية
الرواتب. القالب الخاطئ يعني رفض الملف وتأخر رواتب.
"""
import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal

from apps.employees.services.validators import validate_saudi_iban

ZERO = Decimal("0")

# خريطة رمز الآيبان إلى رمز سويفت — مؤكدة من ملف بنك فعلي لا تخمين
IBAN_BANK_MAP = {
    "10": "NCBK",   # الأهلي
    "15": "ALBI",   # البلاد
    "20": "RIBL",   # الرياض
    "45": "SABB",   # الأول
    "60": "BJAZ",   # الجزيرة
    "80": "RJHI",   # الراجحي
}


class BankFileError(Exception):
    pass


@dataclass
class BankFileResult:
    content: str
    filename: str
    row_count: int
    total_amount: Decimal
    excluded: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def ready(self):
        return not self.errors and self.row_count > 0


def swift_from_iban(iban):
    """رمز البنك من الآيبان السعودي — الخانتان 5 و6."""
    if len(iban) >= 6 and iban.startswith("SA"):
        return IBAN_BANK_MAP.get(iban[4:6], "")
    return ""


def _slip_values(slip):
    """يفكّك القسيمة لقيم الأعمدة المتاحة."""
    emp = slip.employment
    person = emp.person

    basic = housing = other = ZERO
    for line in slip.lines.all():
        if line.line_type != "earning":
            continue
        if line.component_code == "BASIC":
            basic += line.amount
        elif line.component_code == "HOUSING":
            housing += line.amount
        else:
            other += line.amount

    iban = (slip.iban or "").replace(" ", "").upper()
    swift = emp.bank_code or swift_from_iban(iban)

    dept = ""
    if emp.department:
        dept = emp.department.name_en or emp.department.name_ar

    return {
        "employee_bank_swift": swift,
        "iban": iban,
        "account_number": iban,
        "net_pay": slip.net_pay,
        "gross": slip.gross_earnings,
        "basic": basic,
        "housing": housing,
        "other_earnings": other,
        "deductions": slip.total_deductions,
        "employee_no": emp.employee_no,
        "name_ar": person.display_name,
        "name_en": person.full_name_en or person.display_name,
        "id_number": person.id_number,
        "department": dept,
        "branch": emp.branch.name_ar if emp.branch else "",
        "job_title": emp.job_title.name_ar if emp.job_title else "",
    }


def _format_value(raw, column, seq):
    """يطبّق تنسيق العمود على القيمة."""
    if column.source == "constant":
        value = column.constant_value
    elif column.source == "sequence":
        value = str(seq)
    else:
        value = raw

    if isinstance(value, Decimal):
        fmt = column.number_format or "0.00"
        decimals = len(fmt.split(".")[1]) if "." in fmt else 0
        value = f"{value:.{decimals}f}"
    else:
        value = str(value if value is not None else "")

    if column.text_transform == "upper":
        value = value.upper()
    elif column.text_transform == "lower":
        value = value.lower()
    elif column.text_transform == "strip":
        value = value.strip()

    if column.max_length:
        value = value[: column.max_length]
    return value


def build_bank_file(run, template, branch=None):
    """يبني ملف البنك من مسير معتمد."""
    from apps.payroll.models import PayrollRunStatus

    if run.status not in (PayrollRunStatus.APPROVED, PayrollRunStatus.PAID):
        raise BankFileError(
            f"المسير {run.get_status_display()} — لا يُصدَّر إلا بعد الاعتماد")

    columns = list(template.columns.order_by("position"))
    if not columns:
        raise BankFileError(f"القالب {template.name_ar} بلا أعمدة")

    slips = run.payslips.select_related(
        "employment__person", "employment__department", "employment__branch",
        "employment__job_title").prefetch_related("lines")
    if branch is not None:
        slips = slips.filter(employment__branch=branch)

    rows, excluded, errors = [], [], []
    total = ZERO
    seq = 0

    for slip in slips.order_by("employment__employee_no"):
        emp = slip.employment

        if slip.net_pay <= 0:
            excluded.append({
                "employee_no": emp.employee_no,
                "name": emp.person.display_name,
                "reason": "صافي صفري — لا يُحوَّل"})
            continue

        if emp.payment_method != "bank":
            excluded.append({
                "employee_no": emp.employee_no,
                "name": emp.person.display_name,
                "reason": f"طريقة الصرف: {emp.get_payment_method_display()}"})
            continue

        ok, err = validate_saudi_iban(slip.iban)
        if not ok:
            errors.append({
                "employee_no": emp.employee_no,
                "name": emp.person.display_name, "error": err})
            continue

        seq += 1
        values = _slip_values(slip)
        rows.append([_format_value(values.get(c.source), c, seq)
                     for c in columns])
        total += slip.net_pay

    newline = "\r\n" if template.line_ending == "crlf" else "\n"
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=template.delimiter,
                        lineterminator=newline)
    if template.include_header:
        writer.writerow([c.header for c in columns])
    writer.writerows(rows)

    pay_date = run.payment_date or run.accrual_date
    filename = template.filename_pattern.format(
        bank=template.swift_prefix or template.code,
        date=pay_date.strftime('%d-%m-%Y'),
        date_iso=pay_date.isoformat(),
        period=f"{run.period_year}{run.period_month:02d}",
        company=getattr(run.company, "code", ""))

    return BankFileResult(
        content=buf.getvalue(), filename=filename, row_count=len(rows),
        total_amount=total, excluded=excluded, errors=errors)
