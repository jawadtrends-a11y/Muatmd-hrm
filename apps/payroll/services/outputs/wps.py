"""
ملف حماية الأجور (مُدد).

قواعد ملزمة:
  • الموظف بصافٍ صفري يُستبعد تلقائيًا (ق-37)
  • غير المُدرج في حماية الأجور يُستبعد (ق-15)
  • الآيبان يُتحقق منه قبل التصدير — رفض البنك أغلى من الفحص
  • الاستبعاد الصامت ممنوع: كل مستبعَد يُسجَّل بسببه
"""
from dataclasses import dataclass, field
from decimal import Decimal

from apps.employees.services.validators import validate_saudi_iban

ZERO = Decimal("0")


class WPSError(Exception):
    pass


@dataclass
class WPSRow:
    employee_no: str
    id_number: str
    name_ar: str
    name_en: str
    iban: str
    bank_code: str
    basic_salary: Decimal
    housing_allowance: Decimal
    other_earnings: Decimal
    deductions: Decimal
    net_pay: Decimal


@dataclass
class WPSFile:
    run_no: str
    period: str
    company_name: str
    mol_establishment_no: str
    rows: list = field(default_factory=list)
    excluded: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def total_net(self):
        return sum((r.net_pay for r in self.rows), ZERO)

    @property
    def record_count(self):
        return len(self.rows)


def build_wps_file(run, branch=None):
    """يبني ملف حماية الأجور من مسير معتمد."""
    from apps.payroll.models import PayrollRunStatus

    if run.status not in (PayrollRunStatus.APPROVED, PayrollRunStatus.PAID):
        raise WPSError(
            f"المسير {run.get_status_display()} — لا يُصدَّر إلا بعد الاعتماد")

    establishment = branch.mol_establishment_no if branch else ""

    wps = WPSFile(
        run_no=run.run_no,
        period=f"{run.period_year}-{run.period_month:02d}",
        company_name=run.company.legal_name_ar,
        mol_establishment_no=establishment,
    )

    slips = run.payslips.select_related(
        "employment__person", "employment__branch").prefetch_related("lines")
    if branch is not None:
        slips = slips.filter(employment__branch=branch)

    for slip in slips.order_by("employment__employee_no"):
        emp = slip.employment
        person = emp.person

        if not slip.include_in_wps:
            reason = ("صافي صفري" if slip.net_pay == 0
                      else "غير مُدرج في حماية الأجور")
            wps.excluded.append({
                "employee_no": emp.employee_no,
                "name": person.display_name, "reason": reason})
            continue

        ok, err = validate_saudi_iban(slip.iban)
        if not ok:
            wps.errors.append({
                "employee_no": emp.employee_no,
                "name": person.display_name, "error": err})
            continue

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

        wps.rows.append(WPSRow(
            employee_no=emp.employee_no,
            id_number=person.id_number,
            name_ar=person.display_name,
            name_en=person.full_name_en or person.display_name,
            iban=(slip.iban or "").replace(" ", "").upper(),
            bank_code=emp.bank_code,
            basic_salary=basic,
            housing_allowance=housing,
            other_earnings=other,
            deductions=slip.total_deductions,
            net_pay=slip.net_pay,
        ))

    return wps


def to_csv(wps: WPSFile) -> str:
    """الصيغة القياسية لمُدد."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow([
        "Employee ID", "Employee Name", "IBAN", "Bank Code",
        "Basic Salary", "Housing Allowance", "Other Earnings",
        "Deductions", "Net Salary",
    ])
    for r in wps.rows:
        w.writerow([
            r.id_number, r.name_en, r.iban, r.bank_code,
            f"{r.basic_salary:.2f}", f"{r.housing_allowance:.2f}",
            f"{r.other_earnings:.2f}", f"{r.deductions:.2f}",
            f"{r.net_pay:.2f}",
        ])
    return buf.getvalue()


def validation_report(wps: WPSFile) -> dict:
    """تقرير ما قبل الإرسال — يُعرض لمدير الموارد."""
    return {
        "run_no": wps.run_no,
        "period": wps.period,
        "establishment_no": wps.mol_establishment_no,
        "record_count": wps.record_count,
        "total_net": str(wps.total_net),
        "excluded_count": len(wps.excluded),
        "excluded": wps.excluded,
        "error_count": len(wps.errors),
        "errors": wps.errors,
        "ready": len(wps.errors) == 0 and wps.record_count > 0,
    }
