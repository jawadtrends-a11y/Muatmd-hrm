"""
بناء القيد المحاسبيّ وتصديره (ق-152).

⚠️⚠️ **ولا يُصدَّر قيدٌ غير متوازن** — فمدينٌ لا يساوي دائنًا
يُرفض في أيّ نظام، **وتصديرُه يُضيّع وقت المحاسب**.
"""
import io
import logging
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)

ZERO = Decimal("0")

#: الحقول المتاحة للأعمدة — **معلَنةٌ لا حرّة**
#
# ⚠️ فعمودٌ بمرجعٍ مجهول يُفرغ الملفّ بلا خطأ.
AVAILABLE_FIELDS = {
    "entry_date": "تاريخ القيد",
    "reference": "المرجع",
    "description": "البيان",
    "account": "الحساب",
    "debit": "مدين",
    "credit": "دائن",
    "cost_center": "مركز التكلفة",
    "department": "الإدارة",
    "employee_no": "رقم الموظف",
    "employee_name": "اسم الموظف",
    "component_code": "رمز البند",
    "period": "الفترة",
    "currency": "العملة",
}


class GLError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


@dataclass
class GLLine:
    account: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    description: str = ""
    cost_center: str = ""
    department: str = ""
    employee_no: str = ""
    employee_name: str = ""
    component_code: str = ""


@dataclass
class GLEntry:
    run_no: str
    period: str
    entry_date: object
    lines: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    unmapped: list = field(default_factory=list)

    @property
    def total_debit(self):
        return sum((l.debit for l in self.lines), ZERO)

    @property
    def total_credit(self):
        return sum((l.credit for l in self.lines), ZERO)

    @property
    def is_balanced(self):
        """
        ⚠️ **التوازن شرطٌ لا تحسين**: فرقُ هللةٍ يُرفض في النظام
        المحاسبيّ.
        """
        return abs(self.total_debit - self.total_credit) < Decimal("0.01")

    @property
    def ready(self):
        return (not self.errors and not self.unmapped
                and self.is_balanced and bool(self.lines))


def _group_key(slip, grouping):
    """مفتاحُ التجميع بحسب المستوى المختار."""
    from apps.payroll.models import GLGrouping

    emp = slip.employment
    if grouping == GLGrouping.EMPLOYEE:
        return (emp.employee_no, emp.person.display_name,
                getattr(emp.department, "name_ar", "") or "",
                getattr(getattr(emp, "cost_center", None), "code", "")
                or "")
    if grouping == GLGrouping.DEPARTMENT:
        d = getattr(emp.department, "name_ar", "") or "بلا إدارة"
        return ("", "", d, "")
    if grouping == GLGrouping.COST_CENTER:
        cc = getattr(getattr(emp, "cost_center", None), "code", "") or ""
        return ("", "", "", cc or "بلا مركز")
    return ("", "", "", "")


def build_entry(run, template):
    """
    يبني قيد المسير — **ويُفصّل ما ينقصه**.

    ⚠️ **والمسير غير المعتمد لا قيدَ له**: فأرقامٌ غير نهائية
    تُرحَّل خطأً.
    """
    from apps.payroll.models import (
        GLAccountMap, PayrollRunStatus, PayslipLineType)

    if run.status not in (PayrollRunStatus.APPROVED,
                          PayrollRunStatus.PAID):
        raise GLError(
            f"المسير {run.get_status_display()} — "
            "لا يُرحَّل إلا بعد الاعتماد")

    entry = GLEntry(
        run_no=run.run_no,
        period=f"{run.period_year}-{run.period_month:02d}",
        entry_date=run.accrual_date)

    maps = {m.component_code: m for m in GLAccountMap.objects.filter(
        company_id=run.company_id)}

    # ⚠️ **تجميعٌ بمفتاحين**: مستوى التجميع، ثم البند — فسطرٌ لكل
    # حسابٍ في كل مجموعة.
    buckets = {}
    net_buckets = {}

    for slip in run.payslips.select_related(
            "employment__person", "employment__department"
    ).prefetch_related("lines"):
        gk = _group_key(slip, template.grouping)
        net_buckets[gk] = net_buckets.get(gk, ZERO) + slip.net_pay

        for line in slip.lines.all():
            m = maps.get(line.component_code)
            if m is None:
                if line.component_code not in entry.unmapped:
                    entry.unmapped.append(line.component_code)
                continue
            if m.is_excluded:
                continue
            if not m.is_ready:
                if line.component_code not in entry.unmapped:
                    entry.unmapped.append(line.component_code)
                continue

            key = (gk, line.component_code, line.line_type)
            buckets[key] = buckets.get(key, ZERO) + line.amount

    if entry.unmapped:
        return entry          # ⚠️ لا قيدَ ببنودٍ غير مربوطة

    # ── بناء الأسطر ──
    for (gk, code, ltype), amount in sorted(buckets.items(),
                                            key=lambda x: str(x[0])):
        if amount == ZERO:
            continue
        m = maps[code]
        emp_no, emp_name, dept, cc = gk

        # ⚠️ **والاستحقاق مدينٌ والخصم دائن**: فالأجر مصروفٌ على
        # الشركة، والخصم يقلّل الالتزام.
        if ltype == PayslipLineType.DEDUCTION:
            entry.lines.append(GLLine(
                account=m.credit_account, credit=ZERO, debit=amount,
                description=m.name_ar or code,
                department=dept, cost_center=cc,
                employee_no=emp_no, employee_name=emp_name,
                component_code=code))
        else:
            entry.lines.append(GLLine(
                account=m.debit_account, debit=amount, credit=ZERO,
                description=m.name_ar or code,
                department=dept, cost_center=cc,
                employee_no=emp_no, employee_name=emp_name,
                component_code=code))

    # ── الطرف المقابل: صافي المستحقّ للموظفين ──
    #
    # ⚠️ **وبلا هذا لا يتوازن القيد**: فالمصروف بلا التزامٍ مقابل
    # نصفُ قيد.
    payable = maps.get("NET_PAYABLE")
    if payable is None or not payable.credit_account:
        entry.errors.append(
            "اربط «NET_PAYABLE» بحساب الرواتب المستحقّة — "
            "فبلا الطرف الدائن لا يتوازن القيد")
        return entry

    for gk, net in net_buckets.items():
        if net == ZERO:
            continue
        emp_no, emp_name, dept, cc = gk
        entry.lines.append(GLLine(
            account=payable.credit_account, credit=net,
            description=payable.name_ar or "رواتب مستحقّة",
            department=dept, cost_center=cc,
            employee_no=emp_no, employee_name=emp_name,
            component_code="NET_PAYABLE"))

    if not entry.is_balanced:
        entry.errors.append(
            f"القيد غير متوازن: مدين {entry.total_debit} "
            f"دائن {entry.total_credit}")

    return entry


def to_csv(entry, template):
    """
    يحوّل القيد لنصّ CSV بقالب العميل.

    ⚠️ **ولا يُصدَّر ما ليس جاهزًا** — فالفحص قبل الكتابة.
    """
    import csv

    if not entry.ready:
        raise GLError("القيد غير جاهز للتصدير")

    cols = template.columns or [
        {"field": "entry_date", "header": "Date"},
        {"field": "account", "header": "Account"},
        {"field": "description", "header": "Description"},
        {"field": "debit", "header": "Debit"},
        {"field": "credit", "header": "Credit"},
    ]

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=template.delimiter or ",")

    if template.include_header:
        w.writerow([c.get("header") or c["field"] for c in cols])

    for line in entry.lines:
        row = []
        for c in cols:
            f = c.get("field")
            if f == "entry_date":
                v = entry.entry_date.strftime(
                    template.date_format or "%Y-%m-%d")
            elif f == "reference":
                v = entry.run_no
            elif f == "period":
                v = entry.period
            elif f == "currency":
                v = "SAR"
            elif f in ("debit", "credit"):
                amt = getattr(line, f)
                v = str(amt) if amt else ""
            else:
                v = getattr(line, f, "")
            row.append(v)
        w.writerow(row)

    return buf.getvalue()


def default_columns():
    """أعمدةٌ افتراضية — تُعدَّل بعد الإنشاء."""
    return [
        {"field": "entry_date", "header": "Date"},
        {"field": "reference", "header": "Reference"},
        {"field": "account", "header": "Account"},
        {"field": "description", "header": "Description"},
        {"field": "debit", "header": "Debit"},
        {"field": "credit", "header": "Credit"},
        {"field": "cost_center", "header": "CostCenter"},
    ]
