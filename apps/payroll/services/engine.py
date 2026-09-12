"""
محرك احتساب الرواتب — قلب النظام.

يجمع كل ما بُني: هيكل الراتب التاريخي، الأعلام الأربعة، نسب
التأمينات بتاريخ السريان، ملخص الحضور، والإجازات بلا أجر.

قواعد ملزمة:
  • كل المدخلات تُقرأ بـaccrual_date لا بتاريخ اليوم — فإعادة
    الاحتساب تعطي نفس الأرقام دائمًا (شرط التدقيق)
  • كل بند يشرح نفسه في calculation_trace
  • الاحتساب لا يمس أي جدول خارج المسير
  • الغياب والإجازة بلا أجر منفصلان (ق-32)
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.payroll.models import (
    ComponentType, Payslip, PayslipLine, PayslipLineType, PayrollRun,
    PayrollRunStatus, PayrollRunType, PayrollSettings,
)
from apps.payroll.services.calculations import (
    allocate_gosi, calculate_absence_deduction, calculate_gosi,
    calculate_overtime, daily_rate, r2,
)

ZERO = Decimal("0")


class PayrollError(Exception):
    pass


@dataclass
class SlipResult:
    payslip: Payslip
    warnings: list = field(default_factory=list)


def _next_run_no(company, run_type, year, month):
    prefix = {"regular": "PR", "supplementary": "PS",
              "settlement": "PT"}.get(run_type, "PR")
    return f"{prefix}-{year}{month:02d}-{company.id:04d}"


@transaction.atomic
def create_run(*, company, run_type, year, month, accrual_date=None,
               note=""):
    """ينشئ مسيرًا. تاريخ الاستحقاق افتراضه آخر يوم في الشهر."""
    from calendar import monthrange
    acc_date = accrual_date or date(year, month, monthrange(year, month)[1])

    existing = PayrollRun.objects.filter(
        company=company, run_type=run_type, period_year=year,
        period_month=month,
        status__in=["draft", "calculating", "calculated", "submitted",
                    "approved", "paid"]).first()
    if existing:
        raise PayrollError(
            f"يوجد مسير نشط لهذه الفترة: {existing.run_no} "
            f"({existing.get_status_display()})")

    return PayrollRun.objects.create(
        account=company.account, company=company,
        run_no=_next_run_no(company, run_type, year, month),
        run_type=run_type, period_year=year, period_month=month,
        accrual_date=acc_date, note=note)


def _eligible_employments(run):
    """
    الموظفون المشمولون في المسير.

    المسير العام: النشطون. والمنتهية خدمتهم في الشهر يدخلون حسب
    إعداد الشركة (ق-21).
    """
    from apps.employees.models import Employment, EmploymentStatus
    from calendar import monthrange

    start = date(run.period_year, run.period_month, 1)
    end = date(run.period_year, run.period_month,
               monthrange(run.period_year, run.period_month)[1])

    qs = Employment.objects.filter(company=run.company).select_related(
        "person", "company")

    if run.run_type == PayrollRunType.SETTLEMENT:
        return qs.filter(status=EmploymentStatus.TERMINATED,
                         termination_date__gte=start,
                         termination_date__lte=end)

    settings_obj = PayrollSettings.objects.filter(company=run.company).first()
    include_terminated = (settings_obj.terminated_pay_in_regular_run
                          if settings_obj else True)

    active = qs.filter(status__in=[EmploymentStatus.ACTIVE,
                                   EmploymentStatus.ON_LEAVE],
                       join_date__lte=end)
    if include_terminated:
        from django.db.models import Q
        return qs.filter(
            Q(status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE],
              join_date__lte=end)
            | Q(status=EmploymentStatus.TERMINATED,
                termination_date__gte=start, termination_date__lte=end)
        )
    return active


@transaction.atomic
def calculate_slip(*, run, employment, settings_obj):
    """
    يحتسب قسيمة موظف واحد.

    الترتيب: هيكل الراتب ← الحضور ← الاستحقاقات ← التأمينات ←
    الاستقطاعات ← الصافي.
    """
    warnings = []
    trace = {"accrual_date": str(run.accrual_date),
             "employee_no": employment.employee_no}

    # ── 1. هيكل الراتب الساري بتاريخ الاستحقاق ──
    from apps.employees.services.hiring import current_salary_structure
    structure = current_salary_structure(employment, run.accrual_date)
    if structure is None:
        raise PayrollError(
            f"لا هيكل راتب ساري للموظف {employment.employee_no} "
            f"بتاريخ {run.accrual_date}")

    lines_src = structure.as_lines()
    trace["salary_structure"] = {
        "id": structure.id, "effective_from": str(structure.effective_from),
        "gross": str(structure.gross_monthly)}

    # ── 2. الحضور والإجازات ──
    from apps.attendance.models import AttendanceMonthlySummary
    from apps.leaves.services.leave_requests import unpaid_leave_days_in_period

    summary = AttendanceMonthlySummary.objects.filter(
        employment=employment, period_year=run.period_year,
        period_month=run.period_month).first()

    absence_days = summary.unpaid_absent_days if summary else ZERO
    overtime_minutes = summary.approved_overtime_minutes if summary else 0
    worked_days = summary.worked_days if summary else ZERO
    unpaid_leave = unpaid_leave_days_in_period(
        employment, run.period_year, run.period_month)

    trace["attendance"] = {
        "worked_days": str(worked_days),
        "unpaid_absence_days": str(absence_days),
        "unpaid_leave_days": str(unpaid_leave),
        "approved_overtime_minutes": overtime_minutes,
        "source": "monthly_summary" if summary else "no_summary",
    }
    if summary is None:
        warnings.append("لا ملخص حضور لهذه الفترة — احتُسب الشهر كاملًا")

    # ── 3. الاستحقاقات ──
    days_per_month = settings_obj.payroll_days_per_month
    hours_per_day = settings_obj.working_hours_per_day

    earnings = []
    gross = ZERO
    basic = ZERO
    gosi_subject = ZERO
    overtime_base = ZERO
    absence_base = ZERO      # ق-36

    for comp, amount in lines_src:
        if comp.component_type != ComponentType.EARNING:
            continue
        earnings.append({
            "code": comp.code, "name_ar": comp.name_ar,
            "name_en": comp.name_en, "name_ur": comp.name_ur,
            "amount": amount,
            "explanation": "مبلغ ثابت شهري", "order": comp.display_order,
        })
        gross += amount
        if comp.code == "BASIC":
            basic = amount
        if comp.is_gosi_subject:
            gosi_subject += amount
        if comp.is_overtime_base:
            overtime_base += amount
        if comp.is_absence_base:
            absence_base += amount

    trace["earnings"] = {
        "gross_monthly": str(gross), "basic": str(basic),
        "gosi_subject_wage": str(gosi_subject),
        "overtime_base": str(overtime_base),
        "absence_base": str(absence_base)}

    # ── 4. العمل الإضافي ──
    if overtime_minutes > 0:
        ot = calculate_overtime(
            overtime_minutes=overtime_minutes, basic_salary=basic,
            full_wage=gross, basis=settings_obj.overtime_basis,
            days_per_month=days_per_month, hours_per_day=hours_per_day)
        earnings.append({
            "code": "OVERTIME", "name_ar": "العمل الإضافي",
            "amount": ot.total, "explanation": ot.explanation, "order": 40})
        gross += ot.total
        trace["overtime"] = {"minutes": overtime_minutes,
                             "amount": str(ot.total),
                             "basis": ot.basis,
                             "explanation": ot.explanation}

    # ── 5. التأمينات (بتاريخ الاستحقاق) ──
    from apps.employees.services.hiring import gosi_borne_by_company

    deductions = []
    employer_costs = []
    gosi_emp_share = ZERO
    gosi_er_share = ZERO
    borne = False

    # ق-38: الإجازة بلا أجر شهرًا كاملًا توقف الاشتراك — لا خصم
    # تأمينات على أجر لم يُصرف
    from calendar import monthrange
    days_in_month = monthrange(run.period_year, run.period_month)[1]
    full_month_unpaid = unpaid_leave >= days_in_month
    if full_month_unpaid:
        warnings.append(
            f"إجازة بلا أجر الشهر كاملًا ({days_in_month} يومًا) — "
            "أُوقف اشتراك التأمينات لهذه الفترة")

    scheme = employment.person.gosi_scheme_code
    if employment.is_gosi_registered and scheme and not full_month_unpaid:
        declared = employment.gosi_declared_wage or gosi_subject
        g = calculate_gosi(subject_wage=declared, scheme_code=scheme,
                           as_of=run.accrual_date)
        warnings.extend(g.warnings)

        borne = gosi_borne_by_company(employment, settings_obj)
        alloc = allocate_gosi(gosi_result=g,
                              company_bears_employee_share=borne)
        gosi_emp_share = g.employee_share
        gosi_er_share = g.employer_share

        for line in alloc.payslip_lines:
            entry = {"code": line["code"], "name_ar": line["name_ar"],
                     "amount": line["amount"],
                     "explanation": f"{scheme} — أجر خاضع {r2(declared)}",
                     "order": 100}
            if line["type"] == "deduction":
                deductions.append(entry)
            elif line["type"] == "earning":
                earnings.append(entry)
                gross += line["amount"]
            else:
                employer_costs.append(entry)

        trace["gosi"] = {**g.breakdown, "borne_by_company": borne,
                         "employee_deduction": str(alloc.employee_deduction)}
    elif scheme is None and employment.is_gosi_registered:
        warnings.append("مسجّل في التأمينات بلا نظام تأميني محدد")

    # ── 6. خصم الغياب والإجازة بلا أجر (ق-32: منفصلان) ──
    if absence_days > 0:
        amt = calculate_absence_deduction(
            unpaid_days=absence_days, monthly_wage=absence_base,
            days_per_month=days_per_month)
        deductions.append({
            "code": "ABSENCE", "name_ar": "خصم غياب", "amount": amt,
            "explanation": (f"{r2(absence_days)} يوم × "
                            f"{r2(daily_rate(absence_base, days_per_month))} ريال"),
            "order": 110})

    if unpaid_leave > 0:
        amt = calculate_absence_deduction(
            unpaid_days=unpaid_leave, monthly_wage=absence_base,
            days_per_month=days_per_month)
        deductions.append({
            "code": "UNPAID_LEAVE", "name_ar": "خصم إجازة بلا أجر",
            "amount": amt,
            "explanation": (f"{r2(unpaid_leave)} يوم × "
                            f"{r2(daily_rate(absence_base, days_per_month))} ريال "
                            "— إجازة مأذونة لا غياب"),
            "order": 120})

    # ── 7. أقساط السلف (ق-41) ──
    advance_deductions = []
    if settings_obj.advances_enabled:
        from apps.employees.services.advances import (
            due_installment, outstanding_advances,
        )
        for adv in outstanding_advances(employment):
            due = due_installment(adv, run.period_year, run.period_month)
            if due > 0:
                deductions.append({
                    "code": f"ADVANCE_{adv.id}",
                    "name_ar": f"قسط سلفة {adv.advance_no}",
                    "name_en": f"Advance {adv.advance_no}",
                    "name_ur": f"ایڈوانس {adv.advance_no}",
                    "amount": due,
                    "explanation": (
                        f"المبلغ {r2(adv.amount)} — المسدَّد "
                        f"{r2(adv.repaid_amount)} — المتبقي بعد هذا القسط "
                        f"{r2(adv.outstanding - due)}"),
                    "order": 130})
                advance_deductions.append((adv, due))
        if advance_deductions:
            trace["advances"] = [
                {"advance_no": a.advance_no, "installment": str(r2(d)),
                 "outstanding_after": str(r2(a.outstanding - d))}
                for a, d in advance_deductions
            ]

    # ── البنود المكرّرة (ق-135) ──
    #
    # **بندٌ يتكرّر شهريًّا بلا إدخال** — بدل سكنٍ إضافيّ أو حسم
    # قرض. والموارد تُدخله مرّةً ويتكرّر في مداه.
    #
    # ⚠️ **والعدّاد يُرفع عند الاعتماد لا هنا**: مسيرٌ يُحسب ثم
    # يُلغى لا يستهلك قسطًا — وإلا نقص قسطٌ بلا صرف.
    from apps.payroll.models import RecurringAdjustment, RecurringKind

    recurring_applied = []
    for rec in (RecurringAdjustment.objects
                .filter(employment=employment, is_active=True)
                .select_related("component")):
        if not rec.applies_to(run.period_year, run.period_month):
            continue

        left = rec.remaining
        entry = {
            "code": rec.component.code,
            "name_ar": rec.component.name_ar,
            "name_en": getattr(rec.component, "name_en", "") or "",
            "amount": rec.amount,
            "explanation": (
                (rec.reason or "بند مكرّر")
                + (f" — يتبقّى {left - 1} قسطًا" if left else "")),
            "order": 140,
        }
        if rec.kind == RecurringKind.DEDUCTION:
            deductions.append(entry)
        else:
            earnings.append(entry)
            gross += rec.amount
        recurring_applied.append((rec, rec.amount))

    if recurring_applied:
        trace["recurring"] = [
            {"id": r.id, "component": r.component.code,
             "kind": r.kind, "amount": str(r2(a)),
             "applied_count": r.applied_count}
            for r, a in recurring_applied
        ]

    # ── البنود المؤجَّلة (ق-136) ──
    #
    # ⚠️ **الراتب لا يُؤجَّل** — وإنما بندٌ منه: قسط سلفة لظرفٍ
    # طارئ أو حسمٌ بقرار. والمؤجَّل يُنزع من شهره ويُدرج في شهر
    # وجهته.
    from apps.payroll.models import DeferralStatus, PayslipDeferral

    # ما أُجِّل **من هذا الشهر** يُنزع
    deferred_codes = set(
        PayslipDeferral.objects.filter(
            employment=employment,
            from_year=run.period_year, from_month=run.period_month,
            status=DeferralStatus.PENDING
        ).values_list("component_code", flat=True))

    if deferred_codes:
        def _keep(group):
            out = []
            for e in group:
                if e["code"] in deferred_codes:
                    continue
                out.append(e)
            return out

        removed_gross = sum(
            (e["amount"] for e in earnings if e["code"] in deferred_codes),
            ZERO)
        earnings = _keep(earnings)
        deductions = _keep(deductions)
        gross -= removed_gross
        trace["deferred_out"] = sorted(deferred_codes)

    # وما أُجِّل **إلى هذا الشهر** يُدرج
    incoming = list(PayslipDeferral.objects.filter(
        employment=employment,
        to_year=run.period_year, to_month=run.period_month,
        status=DeferralStatus.PENDING))

    for d in incoming:
        entry = {
            "code": d.component_code,
            "name_ar": f"{d.name_ar} (مؤجَّل من "
                       f"{d.from_year}-{d.from_month:02d})",
            "name_en": "", "amount": d.amount,
            "explanation": d.reason or "بند مؤجَّل",
            "order": 150,
        }
        if d.line_type == PayslipLineType.DEDUCTION:
            deductions.append(entry)
        else:
            earnings.append(entry)
            gross += d.amount

    if incoming:
        trace["deferred_in"] = [
            {"id": d.id, "code": d.component_code,
             "amount": str(r2(d.amount)),
             "from": f"{d.from_year}-{d.from_month:02d}"}
            for d in incoming
        ]

    # ── 8. استقطاعات الهيكل ──
    for comp, amount in lines_src:
        if comp.component_type == ComponentType.DEDUCTION and amount > 0:
            deductions.append({
                "code": comp.code, "name_ar": comp.name_ar,
                "name_en": comp.name_en, "name_ur": comp.name_ur,
                "amount": amount, "explanation": "استقطاع ثابت",
                "order": comp.display_order})

    # ── 7ب. التسويات الرجعية (ق-69) ──
    #
    # تدخل المجاميع قبل الصافي: بند بلا أثر في الصافي يظهر في
    # القسيمة ولا يُدفع — والموظف يقرأ استحقاقًا لم يصله.
    retro_rows = _pending_retro(run, employment)
    for adj in retro_rows:
        row = {
            "code": f"RETRO_{adj.source.upper()}",
            "name_ar": (f"تسوية {adj.period_year}/{adj.period_month:02d}"
                        f" — {adj.get_source_display()}"),
            "name_en": f"Retro {adj.period_year}/{adj.period_month:02d}",
            "name_ur": f"سابقہ تصفیہ {adj.period_year}/"
                       f"{adj.period_month:02d}",
            "amount": abs(adj.amount),
            "explanation": (adj.reason_ar
                            or f"فرق عن {adj.period_year}/"
                               f"{adj.period_month:02d}"),
            "order": 90,
        }
        if adj.amount >= ZERO:
            earnings.append(row)
            gross += adj.amount
        else:
            deductions.append(row)

    # ── 8. الصافي ──
    total_ded = sum((d["amount"] for d in deductions), ZERO)
    total_er = sum((e["amount"] for e in employer_costs), ZERO)
    raw_net = gross - total_ded

    # ق-37: الصافي السالب مستحيل نظاميًا. الخصم يُقصّ عند حد الاستحقاق،
    # فأقصى ما يُخصم هو كامل الأجر. الحالة القصوى (إجازة شهر كامل بلا
    # راتب) تعطي صفرًا لا سالبًا.
    if raw_net < ZERO:
        capped = total_ded + raw_net          # = gross
        excess = total_ded - capped
        warnings.append(
            f"الاستقطاعات ({r2(total_ded)}) تتجاوز الاستحقاق "
            f"({r2(gross)}) — قُصّت عند {r2(capped)} والصافي صفر. "
            f"الفارق غير المخصوم: {r2(excess)} ريال")
        deductions.append({
            "code": "DED_CAP", "name_ar": "تعديل حد الاستقطاع",
            "amount": -excess,
            "explanation": (f"الصافي لا ينزل عن صفر — رُدّ "
                            f"{r2(excess)} ريال من الاستقطاعات"),
            "order": 900})
        total_ded = capped
        net = ZERO
    else:
        net = raw_net

    trace["totals"] = {"gross": str(r2(gross)),
                       "deductions": str(r2(total_ded)),
                       "net": str(r2(net)),
                       "employer_cost": str(r2(total_er))}

    # ── 9. حفظ القسيمة ──
    slip = Payslip.objects.create(
        account=run.account, company=run.company, run=run,
        employment=employment,
        basic_salary=r2(basic), gross_earnings=r2(gross),
        total_deductions=r2(total_ded), net_pay=r2(net),
        employer_cost=r2(total_er),
        gosi_subject_wage=r2(gosi_subject),
        gosi_employee_share=r2(gosi_emp_share),
        gosi_employer_share=r2(gosi_er_share),
        gosi_borne_by_company=borne,
        worked_days=worked_days, unpaid_absence_days=absence_days,
        unpaid_leave_days=unpaid_leave, overtime_minutes=overtime_minutes,
        payment_method=employment.payment_method, iban=employment.iban,
        include_in_wps=(employment.include_in_wps and
                        not (net == ZERO
                             and settings_obj.exclude_zero_net_from_wps)),
        calculation_trace=trace, warnings=warnings)

    bulk = []
    for group, ltype in ((earnings, PayslipLineType.EARNING),
                         (deductions, PayslipLineType.DEDUCTION),
                         (employer_costs, PayslipLineType.EMPLOYER_COST)):
        for e in group:
            bulk.append(PayslipLine(
                payslip=slip, component_code=e["code"],
                name_ar=e["name_ar"],
                name_en=e.get("name_en", ""),
                name_ur=e.get("name_ur", ""),
                line_type=ltype,
                amount=r2(e["amount"]), explanation=e["explanation"],
                display_order=e.get("order", 50)))
    PayslipLine.objects.bulk_create(bulk)

    # تُعلَّم مدموجة بمسيرها بعد أن صارت بنودًا — فلا تُصرف مرتين
    _mark_retro_merged(run, retro_rows)

    # تسجيل أقساط السلف بعد الخصم الفعلي — السجل يطابق القسائم
    if advance_deductions:
        from apps.employees.services.advances import record_deduction
        for adv, due in advance_deductions:
            record_deduction(advance=adv, year=run.period_year,
                             month=run.period_month, amount=due,
                             payslip=slip)

    return SlipResult(payslip=slip, warnings=warnings)


# ══════════ معالجة المسير الكامل ══════════

@dataclass
class RunResult:
    run: PayrollRun
    calculated: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)
    variances: int = 0


@transaction.atomic
def calculate_run(run):
    """
    يحتسب المسير كاملًا.

    فشل موظف لا يوقف الباقين — يُسجَّل في error_log ويُكمل المحرك.
    مدير الموارد يرى القائمة ويعالجها بدل أن يتعطل المسير كله.
    """
    if run.is_locked:
        raise PayrollError(
            f"المسير {run.get_status_display()} — لا يُعاد احتسابه")

    settings_obj = PayrollSettings.objects.filter(company=run.company).first()
    if settings_obj is None:
        raise PayrollError("لا إعدادات رواتب لهذه الشركة")

    run.status = PayrollRunStatus.CALCULATING
    run.save(update_fields=["status", "updated_at"])

    run.payslips.all().delete()      # إعادة الاحتساب تبني من جديد

    result = RunResult(run=run)
    for emp in _eligible_employments(run):
        try:
            calculate_slip(run=run, employment=emp,
                           settings_obj=settings_obj)
            result.calculated += 1
        except PayrollError as e:
            result.failed += 1
            result.errors.append({
                "employee_no": emp.employee_no,
                "name": emp.person.display_name,
                "error": str(e)})
        except Exception as e:  # noqa: BLE001
            result.failed += 1
            result.errors.append({
                "employee_no": emp.employee_no,
                "name": emp.person.display_name,
                "error": f"خطأ غير متوقع: {e}"})

    _detect_variances(run, settings_obj)
    _update_totals(run)

    run.status = (PayrollRunStatus.CALCULATED if result.calculated
                  else PayrollRunStatus.FAILED)
    run.calculated_at = timezone.now()
    run.error_log = result.errors
    run.save()

    result.variances = run.variance_count
    return result


def _detect_variances(run, settings_obj):
    """
    يكشف الفروقات عن الشهر السابق.

    شاشة المراجعة قبل الاعتماد تمنع أغلب كوارث الرواتب — موظف تغيّر
    صافيه 40% يُعرض قبل الصرف لا بعده.
    """
    threshold = settings_obj.variance_threshold_percent
    prev_year, prev_month = (
        (run.period_year - 1, 12) if run.period_month == 1
        else (run.period_year, run.period_month - 1))

    previous = {
        p.employment_id: p.net_pay
        for p in Payslip.objects.filter(
            run__company=run.company, run__run_type=run.run_type,
            run__period_year=prev_year, run__period_month=prev_month)
    }

    count = 0
    for slip in run.payslips.all():
        prev = previous.get(slip.employment_id)
        if prev is None or prev == 0:
            continue
        diff = ((slip.net_pay - prev) / prev) * Decimal("100")
        slip.previous_net = prev
        slip.variance_percent = r2(diff)
        slip.has_variance = abs(diff) >= threshold
        slip.save(update_fields=["previous_net", "variance_percent",
                                 "has_variance", "updated_at"])
        if slip.has_variance:
            count += 1

    run.variance_count = count


def _update_totals(run):
    from django.db.models import Count, Sum
    agg = run.payslips.aggregate(
        n=Count("id"), gross=Sum("gross_earnings"),
        ded=Sum("total_deductions"), net=Sum("net_pay"),
        er=Sum("employer_cost"))
    run.employee_count = agg["n"] or 0
    run.total_gross = agg["gross"] or ZERO
    run.total_deductions = agg["ded"] or ZERO
    run.total_net = agg["net"] or ZERO
    run.total_employer_cost = agg["er"] or ZERO


@transaction.atomic
def submit_run(run, submitted_by_person=None):
    """يرفع المسير للاعتماد — يمر بسلسلة الاعتماد (ق-10)."""
    if run.status != PayrollRunStatus.CALCULATED:
        raise PayrollError(
            f"المسير {run.get_status_display()} — لا يُرفع إلا بعد الاحتساب")
    if run.employee_count == 0:
        raise PayrollError("المسير فارغ")

    run.status = PayrollRunStatus.SUBMITTED
    run.submitted_at = timezone.now()
    run.save(update_fields=["status", "submitted_at", "updated_at"])

    from apps.notifications.bus import emit
    emit("payroll.submitted", account_id=run.account_id,
         company_id=run.company_id,
         context={"period": f"{run.period_year}-{run.period_month:02d}",
                  "total_net": str(run.total_net),
                  "employee_count": run.employee_count,
                  # الإشعار يوصل لا يخبر فقط
                  "link_url": "/payroll"},
         recipients=[])
    return run


@transaction.atomic
def approve_run(run, approved_by_person):
    """
    اعتماد المسير — يقفله نهائيًا (ق-10).

    بعده لا يُعاد الاحتساب: سجل مالي نهائي يُصرف عليه ويُرحَّل للمحاسبة.
    """
    if run.status != PayrollRunStatus.SUBMITTED:
        raise PayrollError(
            f"المسير {run.get_status_display()} — لا يُعتمد إلا بعد الرفع")

    run.status = PayrollRunStatus.APPROVED
    run.approved_at = timezone.now()
    run.approved_by_person = approved_by_person
    run.save(update_fields=["status", "approved_at", "approved_by_person",
                            "updated_at"])

    from apps.attendance.models import AttendanceMonthlySummary
    AttendanceMonthlySummary.objects.filter(
        company=run.company, period_year=run.period_year,
        period_month=run.period_month).update(is_final=True)

    # ق-135: **العدّاد يُرفع عند الاعتماد لا عند الحساب**.
    #
    # ⚠️ فمسيرٌ يُحسب ثم يُلغى لا يستهلك قسطًا — وإلا نقص قسطٌ بلا
    # صرف، وانتهى القرض قبل سداده.
    #
    # والرفع **بما طُبّق فعلًا** في القسائم لا بكل بندٍ سارٍ: من
    # لم يُحسب له مسير (التحق بعده مثلًا) لا يُستهلك قسطه.
    from apps.payroll.models import RecurringAdjustment

    applied_ids = []
    for slip in run.payslips.all():
        for row in (slip.calculation_trace or {}).get("recurring", []):
            applied_ids.append(row["id"])

    if applied_ids:
        from django.db.models import F

        RecurringAdjustment.objects.filter(id__in=applied_ids).update(
            applied_count=F("applied_count") + 1)
        # وما استُهلك بالكامل يُطفأ — فلا يظهر في قوائم السارية
        for rec in RecurringAdjustment.objects.filter(
                id__in=applied_ids, max_occurrences__isnull=False):
            if rec.applied_count >= rec.max_occurrences:
                RecurringAdjustment.objects.filter(id=rec.id).update(
                    is_active=False)

    # ق-136: المؤجَّلات تُعلَّم مطبَّقةً — **عند الاعتماد لا الحساب**
    #
    # ⚠️ وقسط السلفة المؤجَّل **يمتدّ جدولها شهرًا** لا يُضاعَف
    # القادم: فالتأجيل تخفيفٌ لظرفٍ طارئ، ومضاعفتُه تنقضه.
    from apps.payroll.models import DeferralStatus, PayslipDeferral

    applied_defers = []
    for slip in run.payslips.all():
        for row in (slip.calculation_trace or {}).get("deferred_in", []):
            applied_defers.append(row["id"])

    # وما أُجِّل **من** هذا المسير يبقى معلَّقًا حتى شهر وجهته
    if applied_defers:
        PayslipDeferral.objects.filter(id__in=applied_defers).update(
            status=DeferralStatus.APPLIED, applied_run_id=run.id)

    # وامتداد جدول السلف المؤجَّلة أقساطها
    from apps.employees.models import Advance

    for d in PayslipDeferral.objects.filter(
            from_year=run.period_year, from_month=run.period_month,
            company=run.company, advance_id__isnull=False,
            status=DeferralStatus.PENDING):
        adv = Advance.objects.filter(id=d.advance_id).first()
        if adv and adv.installments_count:
            Advance.objects.filter(id=adv.id).update(
                installments_count=adv.installments_count + 1)

    from apps.core.services.audit import log_action
    log_action(instance=run, action="approve",
               actor=approved_by_person, label=run.run_no,
               summary=(f"اعتماد مسير {run.period_year}-"
                        f"{run.period_month:02d} بصافي {run.total_net} "
                        f"لـ{run.employee_count} موظفًا"))

    from apps.notifications.bus import emit
    emit("payroll.approved", account_id=run.account_id,
         company_id=run.company_id,
         context={"period": f"{run.period_year}-{run.period_month:02d}",
                  "total_net": str(run.total_net),
                  "approver_name": getattr(approved_by_person,
                                           "display_name", ""),
                  "link_url": "/payroll"},
         recipients=[])
    return run


def variance_report(run):
    """تقرير الفروقات — شاشة المراجعة قبل الاعتماد."""
    return [
        {
            "employee_no": s.employment.employee_no,
            "name": s.employment.person.display_name,
            "previous_net": str(s.previous_net),
            "current_net": str(s.net_pay),
            "variance_percent": str(s.variance_percent),
            "warnings": s.warnings,
        }
        for s in run.payslips.filter(has_variance=True).select_related(
            "employment__person")
    ]


def _pending_retro(run, employment):
    """
    تسويات هذا الموظف المختارة للإدراج في هذا المسير (ق-69).

    ولا تُدرج تلقائيًا: القرار صريح بيد موظف الموارد — فما يمرّ
    بالإهمال يُصرف بلا مراجعة. وهو يختارها قبل الاحتساب.

    ولا تُدرج تسوية شهر في مسير الشهر نفسه — فالاحتساب يأخذها.
    """
    from apps.payroll.models import RetroAdjustment, RetroStatus

    return list(RetroAdjustment.objects.filter(
        employment=employment, status=RetroStatus.SELECTED,
        merged_run=run,
    ).exclude(period_year=run.period_year,
              period_month=run.period_month))


def _mark_retro_merged(run, rows):
    """تُعلَّم مدموجة بمسيرها — فلا تُصرف مرتين."""
    if not rows:
        return
    from django.utils import timezone

    from apps.payroll.models import RetroAdjustment, RetroStatus

    RetroAdjustment.objects.filter(id__in=[a.id for a in rows]).update(
        status=RetroStatus.MERGED, merged_run=run,
        decided_at=timezone.now())
