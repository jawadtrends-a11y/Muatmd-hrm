"""
شاشات المسير — اطلاع فقط (ق-40).

ترجع JSON للواجهة مباشرة بلا توليد ملفات. التقارير القابلة
للتصدير في طبقة منفصلة.

التبويبات: ملخص · كشف الرواتب · المستبعدون · الحسومات والإضافات ·
التأمينات · المقارنة
"""
from collections import defaultdict
from decimal import Decimal

ZERO = Decimal("0")


def _fmt(v):
    return f"{Decimal(v):.2f}"


def _pct(part, whole):
    if not whole:
        return "0.0"
    return f"{(Decimal(part) / Decimal(whole) * 100):.1f}"


# ══════════ 1. الملخص ══════════

def summary_tab(run):
    """الأرقام الكبيرة وتوزيع الحسومات والإضافات."""
    slips = run.payslips.prefetch_related("lines")

    basic_total = ZERO
    allowances_total = ZERO
    overtime_total = ZERO
    deduction_groups = defaultdict(Decimal)
    addition_groups = defaultdict(Decimal)

    for slip in slips:
        basic_total += slip.basic_salary
        for line in slip.lines.all():
            if line.line_type == "earning":
                if line.component_code == "BASIC":
                    continue
                if line.component_code == "OVERTIME":
                    overtime_total += line.amount
                    addition_groups["عمل إضافي"] += line.amount
                elif line.component_code == "GOSI_BORNE":
                    addition_groups["تحمّلته الشركة"] += line.amount
                else:
                    allowances_total += line.amount
            elif line.line_type == "deduction":
                label = {
                    "ABSENCE": "الغياب",
                    "LATE": "التأخير",
                    "UNPAID_LEAVE": "إجازة بلا أجر",
                    "GOSI_EMP": "التأمينات",
                }.get(line.component_code, "أخرى")
                deduction_groups[label] += line.amount

    total_ded = sum(deduction_groups.values(), ZERO)
    total_add = sum(addition_groups.values(), ZERO)

    return {
        "run_no": run.run_no,
        "period": f"{run.period_month:02d}-{run.period_year}",
        "run_type": run.get_run_type_display(),
        "status": run.get_status_display(),
        "accrual_date": str(run.accrual_date),
        "payment_date": str(run.payment_date) if run.payment_date else None,
        "employee_count": run.employee_count,
        "headline": {
            "net_total": _fmt(run.total_net),
            "deductions_total": _fmt(run.total_deductions),
            "overtime_total": _fmt(overtime_total),
            "basic_total": _fmt(basic_total),
            "allowances_total": _fmt(allowances_total),
        },
        "deduction_breakdown": [
            {"type": k, "amount": _fmt(v),
             "percent": _pct(v, total_ded)}
            for k, v in sorted(deduction_groups.items(),
                               key=lambda x: -x[1])
        ],
        "addition_breakdown": [
            {"type": k, "amount": _fmt(v), "percent": _pct(v, total_add)}
            for k, v in sorted(addition_groups.items(), key=lambda x: -x[1])
        ],
        "variance_count": run.variance_count,
        "error_count": len(run.error_log or []),
    }


# ══════════ 2. كشف الرواتب ══════════

def payslips_tab(run, search=None):
    """قائمة القسائم — صف لكل موظف."""
    slips = run.payslips.select_related(
        "employment__person", "employment__department").order_by(
        "employment__employee_no")
    if search:
        slips = slips.filter(
            employment__person__family_name_ar__icontains=search)

    return [
        {
            "payslip_id": s.id,
            "employee_no": s.employment.employee_no,
            "name": s.employment.person.display_name,
            "department": (s.employment.department.name_ar
                           if s.employment.department else ""),
            "basic": _fmt(s.basic_salary),
            "gross": _fmt(s.gross_earnings),
            "deductions": _fmt(s.total_deductions),
            "net": _fmt(s.net_pay),
            "gosi_employee": _fmt(s.gosi_employee_share),
            "in_wps": s.include_in_wps,
            "has_variance": s.has_variance,
            "warnings_count": len(s.warnings or []),
        }
        for s in slips
    ]


# ══════════ 3. الموظفون المستبعدون ══════════

def excluded_tab(run):
    """
    من لم يدخل المسير ولماذا.

    الاستبعاد الصامت هو ما يُنتج شكوى «لماذا لم يصلني راتبي».
    """
    from apps.employees.models import Employment, EmploymentStatus

    included = set(run.payslips.values_list("employment_id", flat=True))
    rows = []

    for e in Employment.objects.filter(
            company=run.company).select_related("person"):
        if e.id in included:
            continue
        if e.status == EmploymentStatus.TERMINATED and e.termination_date:
            if (e.termination_date.year, e.termination_date.month) != (
                    run.period_year, run.period_month):
                reason = f"انتهت خدمته في {e.termination_date}"
            else:
                reason = "منتهية خدمته — يُدرج في مسير المستحقات"
        elif e.status != EmploymentStatus.ACTIVE:
            reason = f"الحالة: {e.get_status_display()}"
        else:
            reason = "لا هيكل راتب ساري"
        rows.append({
            "employee_no": e.employee_no,
            "name": e.person.display_name,
            "status": e.get_status_display(),
            "reason": reason,
        })

    # من فشل احتسابه — بلا تكرار من القائمة أعلاه
    listed = {r["employee_no"] for r in rows}
    for err in (run.error_log or []):
        if err.get("employee_no") in listed:
            continue
        rows.append({
            "employee_no": err.get("employee_no", ""),
            "name": err.get("name", ""),
            "status": "فشل الاحتساب",
            "reason": err.get("error", ""),
        })
    return rows


# ══════════ 4. الحسومات والإضافات ══════════

def adjustments_tab(run, kind=None):
    """
    تفصيل كل حسم وإضافة بسطر — مع شرح الاحتساب.

    kind: deduction أو earning أو None للكل
    """
    rows = []
    for slip in run.payslips.select_related(
            "employment__person").prefetch_related("lines"):
        for line in slip.lines.all():
            if line.line_type not in ("deduction", "earning"):
                continue
            if line.component_code in ("BASIC", "HOUSING", "TRANSPORT"):
                continue      # الثوابت ليست حسومات ولا إضافات
            if kind and line.line_type != kind:
                continue
            rows.append({
                "employee_no": slip.employment.employee_no,
                "name": slip.employment.person.display_name,
                "type": line.get_line_type_display(),
                "reason": line.name_ar,
                "amount": _fmt(line.amount),
                "explanation": line.explanation,
            })
    return sorted(rows, key=lambda r: (r["name"], r["reason"]))


# ══════════ 5. التأمينات الاجتماعية ══════════

def gosi_tab(run):
    """
    حسومات السعوديين وغير السعوديين ومساهمة المنشأة والمستحق.

    الفصل بين الجنسيتين مقصود: الوافد لا يُخصم منه شيء، وظهور رقم
    غير صفري في خانته يكشف خطأً فورًا.
    """
    saudi_emp = non_saudi_emp = employer = ZERO
    borne_count = 0

    for slip in run.payslips.select_related("employment__person"):
        person = slip.employment.person
        if person.is_saudi:
            saudi_emp += slip.gosi_employee_share
        else:
            non_saudi_emp += slip.gosi_employee_share
        employer += slip.gosi_employer_share
        if slip.gosi_borne_by_company:
            borne_count += 1

    total_employee = saudi_emp + non_saudi_emp
    return {
        "employee_saudi": _fmt(saudi_emp),
        "employee_non_saudi": _fmt(non_saudi_emp),
        "employee_total": _fmt(total_employee),
        "employer_contribution": _fmt(employer),
        "total_due": _fmt(total_employee + employer),
        "borne_by_company_count": borne_count,
        "note": ("لا يُخصم من الوافد شيء — أي رقم غير صفري في خانته "
                 "يعني خطأً في النظام التأميني المسجّل"),
    }


# ══════════ 6. المقارنة بالشهر السابق ══════════

def comparison_tab(run):
    """ما تغيّر ولماذا — شاشة المراجعة قبل الاعتماد."""
    from apps.payroll.models import Payslip

    prev_year, prev_month = (
        (run.period_year - 1, 12) if run.period_month == 1
        else (run.period_year, run.period_month - 1))

    previous = {
        p.employment_id: p
        for p in Payslip.objects.filter(
            run__company=run.company, run__run_type=run.run_type,
            run__period_year=prev_year, run__period_month=prev_month)
    }

    rows = []
    for slip in run.payslips.select_related("employment__person"):
        prev = previous.get(slip.employment_id)
        if prev is None:
            rows.append({
                "employee_no": slip.employment.employee_no,
                "name": slip.employment.person.display_name,
                "previous_net": None, "current_net": _fmt(slip.net_pay),
                "difference": _fmt(slip.net_pay),
                "variance_percent": None,
                "status": "جديد في المسير",
            })
            continue
        diff = slip.net_pay - prev.net_pay
        if diff == 0:
            continue
        rows.append({
            "employee_no": slip.employment.employee_no,
            "name": slip.employment.person.display_name,
            "previous_net": _fmt(prev.net_pay),
            "current_net": _fmt(slip.net_pay),
            "difference": _fmt(diff),
            "variance_percent": (str(slip.variance_percent)
                                 if slip.variance_percent is not None else ""),
            "status": ("يحتاج مراجعة" if slip.has_variance else "تغيّر طفيف"),
        })

    left = {p.employment_id: p for p in previous.values()
            if p.employment_id not in
            set(run.payslips.values_list("employment_id", flat=True))}
    for p in left.values():
        rows.append({
            "employee_no": p.employment.employee_no,
            "name": p.employment.person.display_name,
            "previous_net": _fmt(p.net_pay), "current_net": None,
            "difference": _fmt(-p.net_pay), "variance_percent": None,
            "status": "خرج من المسير",
        })

    return sorted(rows, key=lambda r: r["status"] != "يحتاج مراجعة")


# ══════════ التجميع ══════════

TABS = {
    "summary": summary_tab,
    "payslips": payslips_tab,
    "excluded": excluded_tab,
    "adjustments": adjustments_tab,
    "gosi": gosi_tab,
    "comparison": comparison_tab,
}


def tab_counts(run):
    """أعداد التبويبات — تظهر بجانب العناوين."""
    return {
        "payslips": run.payslips.count(),
        "excluded": len(excluded_tab(run)),
        "adjustments": len(adjustments_tab(run)),
        "variances": run.variance_count,
    }
