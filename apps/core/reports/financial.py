"""
التقارير المالية.

مخصصات نهاية الخدمة (ق-43) · مسيرات الرواتب · الفروقات ·
الحسومات والإضافات · السلف والذمم.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.core.reports.base import Column, Param, Report, register

ZERO = Decimal("0")


def r2(v):
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@register
class EOSBProvisionReport(Report):
    """
    مخصصات نهاية الخدمة (ق-43).

    يحتسب الالتزام المتراكم بتاريخ محدد — لا فترة. يشمل المكافأة
    الكاملة ورصيد الإجازات معًا لأنهما يُصرفان معًا في المخالصة.
    """

    key = "eosb_provision"
    title_ar = "تقرير مخصصات نهاية الخدمة"
    group = "financial"
    permission = "payroll.view"
    params = [
        Param("as_of", "التاريخ", "date", required=True,
              help_ar="يُحتسب الالتزام كما هو في هذا التاريخ"),
        Param("branch_id", "الفرع", "select"),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("department", "القسم", width=18),
            Column("join_date", "بداية الخدمة", "date", width=14),
            Column("service_years", "سنوات الخدمة", "number", width=12),
            Column("eosb_wage", "أجر المكافأة", "money", width=14),
            Column("eosb_provision", "مخصص المكافأة", "money", width=16,
                   total=True),
            Column("leave_days", "رصيد الإجازات", "number", width=12),
            Column("leave_provision", "مخصص الإجازات", "money", width=16,
                   total=True),
            Column("total_provision", "إجمالي الالتزام", "money", width=16,
                   total=True),
        ]

    def subtitle(self):
        return f"الالتزام المتراكم حتى {self.options.get('as_of')}"

    def notes(self):
        return [
            "المكافأة محتسبة كاملة — تقدير للميزانية لا استحقاق فعلي",
            "رصيد الإجازات على نفس أساس المكافأة (ق-42)",
        ]

    def rows(self):
        from apps.employees.models import Employment, EmploymentStatus
        from apps.employees.services.hiring import current_salary_structure
        from apps.leaves.models import LeaveBalance
        from apps.payroll.models import EOSBWageBasis, PayrollSettings
        from apps.payroll.services.components import eosb_wage
        from apps.payroll.services.eosb import calculate_eosb

        as_of = self.options["as_of"]
        if isinstance(as_of, str):
            as_of = date.fromisoformat(as_of)

        settings_obj = PayrollSettings.objects.filter(
            company=self.company).first()
        if settings_obj is None:
            return []
        basis = settings_obj.eosb_wage_basis
        if basis == EOSBWageBasis.NOT_SET:
            basis = "basic_only"      # تقدير تحفظي بدل التعطل
        days_per_month = settings_obj.payroll_days_per_month

        qs = Employment.objects.filter(
            company=self.company,
            status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE],
            join_date__lte=as_of,
        ).select_related("person", "department")

        branch_id = self.options.get("branch_id")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        rows = []
        for emp in qs.order_by("employee_no"):
            structure = current_salary_structure(emp, as_of)
            if structure is None:
                continue

            wage = eosb_wage(structure.as_lines(), basis=basis)
            eosb = calculate_eosb(
                join_date=emp.effective_service_start, end_date=as_of,
                eosb_wage=wage, # انتهاء مدة العقد: كامل الاستحقاق ومحايد — الأنسب للمخصص (ق-43)
                reason_code="contract_expiry",
                wage_basis_set=True)

            leave_days = ZERO
            for b in LeaveBalance.objects.filter(
                    employment=emp, year=as_of.year,
                    leave_type__is_paid=True):
                if b.available > 0:
                    leave_days += b.available

            leave_provision = r2(wage / Decimal(days_per_month) * leave_days)
            total = r2(eosb.net_award + leave_provision)

            rows.append({
                "employee_no": emp.employee_no,
                "name": emp.person.display_name,
                "department": (emp.department.name_ar
                               if emp.department else ""),
                "join_date": str(emp.effective_service_start),
                "service_years": str(eosb.service_years),
                "eosb_wage": str(r2(wage)),
                "eosb_provision": str(eosb.net_award),
                "leave_days": str(r2(leave_days)),
                "leave_provision": str(leave_provision),
                "total_provision": str(total),
            })
        return rows


@register
class PayrollRunsReport(Report):
    """مسيرات الرواتب — ملخص كل مسير في فترة."""

    key = "payroll_runs"
    title_ar = "تقرير مسيرات الرواتب"
    group = "financial"
    permission = "payroll.view"
    params = [
        Param("year", "السنة", "text", required=True),
        Param("run_type", "نوع المسير", "select",
              options=[
                  {"value": "", "label": "الكل"},
                  {"value": "regular", "label": "عام"},
                  {"value": "supplementary", "label": "إضافي"},
                  {"value": "settlement", "label": "مستحقات"},
              ]),
    ]

    def columns(self):
        return [
            Column("run_no", "رقم المسير", width=20),
            Column("period", "الفترة", width=12),
            Column("run_type", "النوع", width=12),
            Column("status", "الحالة", width=16),
            Column("employee_count", "الموظفون", "number", width=10,
                   total=True),
            Column("total_gross", "الاستحقاقات", "money", width=16,
                   total=True),
            Column("total_deductions", "الاستقطاعات", "money", width=16,
                   total=True),
            Column("total_net", "الصافي", "money", width=16, total=True),
            Column("payment_date", "تاريخ الصرف", "date", width=14),
        ]

    def subtitle(self):
        return f"سنة {self.options.get('year')}"

    def rows(self):
        from apps.payroll.models import PayrollRun

        qs = PayrollRun.objects.filter(
            company=self.company, period_year=int(self.options["year"]))
        if self.options.get("run_type"):
            qs = qs.filter(run_type=self.options["run_type"])

        return [
            {
                "run_no": r.run_no,
                "period": f"{r.period_year}-{r.period_month:02d}",
                "run_type": r.get_run_type_display(),
                "status": r.get_status_display(),
                "employee_count": r.employee_count,
                "total_gross": str(r.total_gross),
                "total_deductions": str(r.total_deductions),
                "total_net": str(r.total_net),
                "payment_date": (str(r.payment_date)
                                 if r.payment_date else ""),
            }
            for r in qs.order_by("period_month", "run_type")
        ]


@register
class PayrollVarianceReport(Report):
    """
    الفروقات بين مسيرين — يمنع كوارث الرواتب.

    يُقارن مسير شهر بالذي قبله ويُظهر من تغيّر صافيه ولماذا.
    """

    key = "payroll_variance"
    title_ar = "تقرير الفروقات بين مسيرات الرواتب"
    group = "financial"
    permission = "payroll.view"
    params = [
        Param("year", "السنة", "text", required=True),
        Param("month", "الشهر", "text", required=True),
        Param("threshold", "عتبة الفرق %", "text", default="10"),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("previous_net", "الشهر السابق", "money", width=14,
                   total=True),
            Column("current_net", "الشهر الحالي", "money", width=14,
                   total=True),
            Column("difference", "الفرق", "money", width=14, total=True),
            Column("variance_percent", "النسبة %", "number", width=10),
            Column("status", "الحالة", width=18),
        ]

    def subtitle(self):
        return (f"{self.options.get('year')}-"
                f"{int(self.options.get('month', 1)):02d}")

    def rows(self):
        from apps.payroll.models import PayrollRun
        from apps.payroll.services.outputs.run_screens import comparison_tab

        year = int(self.options["year"])
        month = int(self.options["month"])
        run = PayrollRun.objects.filter(
            company=self.company, period_year=year,
            period_month=month, run_type="regular").first()
        if run is None:
            return []

        threshold = Decimal(str(self.options.get("threshold") or "10"))
        rows = []
        for r in comparison_tab(run):
            pct = r.get("variance_percent")
            if pct and abs(Decimal(pct)) < threshold:
                continue
            rows.append(r)
        return rows


@register
class AdjustmentsReport(Report):
    """الحسومات والإضافات — تفصيل كل بند بشرح احتسابه."""

    key = "adjustments"
    title_ar = "تقرير الحسومات والإضافات"
    group = "financial"
    permission = "payroll.view"
    params = [
        Param("year", "السنة", "text", required=True),
        Param("month", "الشهر", "text", required=True),
        Param("kind", "النوع", "select",
              options=[
                  {"value": "", "label": "الكل"},
                  {"value": "deduction", "label": "حسومات"},
                  {"value": "earning", "label": "إضافات"},
              ]),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("type", "النوع", width=12),
            Column("reason", "البيان", width=24),
            Column("amount", "المبلغ", "money", width=14, total=True),
            Column("explanation", "الاحتساب", width=40),
        ]

    def subtitle(self):
        return (f"{self.options.get('year')}-"
                f"{int(self.options.get('month', 1)):02d}")

    def rows(self):
        from apps.payroll.models import PayrollRun
        from apps.payroll.services.outputs.run_screens import adjustments_tab

        run = PayrollRun.objects.filter(
            company=self.company,
            period_year=int(self.options["year"]),
            period_month=int(self.options["month"]),
            run_type="regular").first()
        if run is None:
            return []
        return adjustments_tab(run, kind=self.options.get("kind") or None)


@register
class AdvancesReport(Report):
    """السلف والذمم — القائم على الموظفين."""

    key = "advances"
    title_ar = "تقرير السلف والذمم"
    group = "financial"
    permission = "payroll.view"
    params = [
        Param("status", "الحالة", "select",
              options=[
                  {"value": "active", "label": "قيد السداد"},
                  {"value": "", "label": "الكل"},
                  {"value": "settled", "label": "مسدَّدة"},
              ], default="active"),
    ]

    def columns(self):
        return [
            Column("advance_no", "رقم السلفة", width=18),
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("amount", "المبلغ", "money", width=14, total=True),
            Column("repaid", "المسدَّد", "money", width=14, total=True),
            Column("outstanding", "المتبقي", "money", width=14, total=True),
            Column("method", "طريقة السداد", width=20),
            Column("start", "بداية السداد", width=12),
            Column("status", "الحالة", width=14),
        ]

    def notes(self):
        return ["المتبقي يُخصم من مستحقات نهاية الخدمة (ق-41)"]

    def rows(self):
        from apps.employees.models_assets import Advance
        from apps.payroll.models import PayrollSettings

        settings_obj = PayrollSettings.objects.filter(
            company=self.company).first()
        if settings_obj and not settings_obj.advances_enabled:
            return []

        qs = Advance.objects.filter(
            company=self.company).select_related("employment__person")
        if self.options.get("status"):
            qs = qs.filter(status=self.options["status"])

        return [
            {
                "advance_no": a.advance_no,
                "employee_no": a.employment.employee_no,
                "name": a.employment.person.display_name,
                "amount": str(a.amount),
                "repaid": str(a.repaid_amount),
                "outstanding": str(a.outstanding),
                "method": a.get_repayment_method_display(),
                "start": f"{a.start_year}-{a.start_month:02d}",
                "status": a.get_status_display(),
            }
            for a in qs.order_by("employment__employee_no")
        ]
