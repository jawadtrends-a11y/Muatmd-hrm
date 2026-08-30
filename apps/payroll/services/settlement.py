"""
مسير المستحقات — تسوية نهاية الخدمة (ق-21).

يجمع ما بُني في سبرنتات سابقة:
  • مكافأة نهاية الخدمة بـ16 حالة نظامية (ق-26)
  • تعويض المادة 77 بند مستقل (ق-27)
  • بدل رصيد الإجازات على نفس أساس المكافأة (ق-42)
  • راتب أيام الشهر حتى تاريخ الانتهاء
  • خصم السلف القائمة والعهد غير المرجَعة (ق-41)

يُنشأ فور اعتماد حساب نهاية الخدمة لا بتاريخ دوري.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

ZERO = Decimal("0")
TWO = Decimal("0.01")


def r2(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


class SettlementError(Exception):
    pass


@dataclass
class SettlementLine:
    code: str
    name_ar: str
    kind: str          # earning أو deduction
    amount: Decimal
    explanation: str = ""
    order: int = 50


@dataclass
class SettlementResult:
    employment_id: int
    employee_no: str
    name: str
    termination_date: date
    reason_code: str
    reason_label: str
    service_days: int
    service_years: Decimal
    lines: list = field(default_factory=list)
    total_earnings: Decimal = ZERO
    total_deductions: Decimal = ZERO
    net_due: Decimal = ZERO
    warnings: list = field(default_factory=list)
    trace: dict = field(default_factory=dict)


def _eosb_wage_for(employment, as_of, settings_obj):
    """
    أجر المكافأة وبدل الإجازات — نفس الأساس (ق-42).

    يُقرأ من هيكل الراتب الساري بتاريخ الانتهاء لا بتاريخ اليوم.
    """
    from apps.employees.services.hiring import current_salary_structure
    from apps.payroll.models import EOSBWageBasis
    from apps.payroll.services.components import eosb_wage
    from apps.payroll.services.eosb import EOSBBasisNotSet

    if settings_obj.eosb_wage_basis == EOSBWageBasis.NOT_SET:
        raise EOSBBasisNotSet(
            "يجب تحديد ما يدخل في أجر المكافأة قبل أول مسير مستحقات "
            "— من إعدادات الرواتب")

    structure = current_salary_structure(employment, as_of)
    if structure is None:
        raise SettlementError(
            f"لا هيكل راتب ساري للموظف {employment.employee_no} "
            f"بتاريخ {as_of}")

    return eosb_wage(structure.as_lines(),
                     basis=settings_obj.eosb_wage_basis), structure


def compute_settlement(*, employment, termination_date, reason_code,
                       settings_obj, agreed_compensation=None,
                       remaining_contract_months=None,
                       include_month_salary=True,
                       leave_balance_days=None):
    """
    يحتسب تسوية نهاية الخدمة كاملة بلا حفظ.

    include_month_salary: راتب أيام الشهر — الشركة تختار إدراجه هنا
    أو تركه في المسير العام (ق-21).
    """
    from apps.payroll.services.eosb import (
        ALL_REASONS, calculate_eosb, calculate_unlawful_termination_compensation,
    )

    if reason_code not in ALL_REASONS:
        raise SettlementError(f"سبب انتهاء غير نظامي: {reason_code}")

    wage, structure = _eosb_wage_for(employment, termination_date,
                                     settings_obj)
    days_per_month = settings_obj.payroll_days_per_month

    result = SettlementResult(
        employment_id=employment.id,
        employee_no=employment.employee_no,
        name=employment.person.display_name,
        termination_date=termination_date,
        reason_code=reason_code,
        reason_label=ALL_REASONS[reason_code],
        service_days=0, service_years=ZERO,
    )

    # ── 1. مكافأة نهاية الخدمة ──
    eosb = calculate_eosb(
        join_date=employment.effective_service_start,
        end_date=termination_date, eosb_wage=wage,
        reason_code=reason_code,
        wage_basis_set=True)

    result.service_days = eosb.service_days
    result.service_years = eosb.service_years
    result.warnings.extend(eosb.warnings)
    result.trace["eosb"] = {
        "wage": str(r2(wage)),
        "service_days": eosb.service_days,
        "gross_award": str(eosb.gross_award),
        "ratio": str(eosb.entitlement_ratio),
        "explanation": eosb.explanation,
    }

    if eosb.net_award > 0:
        result.lines.append(SettlementLine(
            code="EOSB", name_ar="مكافأة نهاية الخدمة", kind="earning",
            amount=eosb.net_award,
            explanation=(f"{eosb.service_days} يومًا — نسبة الاستحقاق "
                         f"{r2(eosb.entitlement_ratio * 100)}%"),
            order=10))
    else:
        result.warnings.append(
            f"لا مكافأة مستحقة: {ALL_REASONS[reason_code]}")

    # ── 2. تعويض المادة 77 (بند مستقل — ق-27) ──
    if reason_code == "unlawful_termination":
        contract_type = ("fixed_term"
                         if employment.contract_type == "fixed_term"
                         else "indefinite")
        comp = calculate_unlawful_termination_compensation(
            monthly_wage=wage, service_days=eosb.service_days,
            contract_type=contract_type,
            remaining_contract_months=remaining_contract_months,
            agreed_amount=agreed_compensation)
        result.lines.append(SettlementLine(
            code="COMP_77", name_ar="تعويض الإنهاء غير المشروع (م/77)",
            kind="earning", amount=comp.amount,
            explanation=comp.explanation[-1] if comp.explanation else "",
            order=20))
        result.trace["compensation_77"] = {
            "amount": str(comp.amount),
            "explanation": comp.explanation,
        }

    # ── 3. بدل رصيد الإجازات (ق-42) ──
    days = leave_balance_days
    if days is None:
        days = _remaining_leave_days(employment)
    days = Decimal(str(days or 0))

    if days > 0:
        daily = wage / Decimal(days_per_month)
        amount = r2(daily * days)
        result.lines.append(SettlementLine(
            code="LEAVE_BALANCE", name_ar="بدل رصيد الإجازات",
            kind="earning", amount=amount,
            explanation=(f"{r2(days)} يوم × {r2(daily)} ريال "
                         f"(نفس أساس المكافأة)"),
            order=30))
        result.trace["leave_balance"] = {
            "days": str(r2(days)), "daily_rate": str(r2(daily)),
            "amount": str(amount)}

    # ── 4. راتب أيام الشهر ──
    if include_month_salary:
        worked = termination_date.day
        gross_monthly = structure.gross_monthly
        daily = gross_monthly / Decimal(days_per_month)
        amount = r2(daily * Decimal(worked))
        result.lines.append(SettlementLine(
            code="MONTH_SALARY", name_ar="راتب أيام الشهر",
            kind="earning", amount=amount,
            explanation=f"{worked} يوم × {r2(daily)} ريال",
            order=5))

    # ── 5. خصم السلف القائمة (ق-41) ──
    if settings_obj.advances_enabled:
        from apps.employees.services.advances import (
            outstanding_advances, total_outstanding,
        )
        for adv in outstanding_advances(employment):
            if adv.outstanding > 0:
                result.lines.append(SettlementLine(
                    code=f"ADV_{adv.id}",
                    name_ar=f"سلفة قائمة {adv.advance_no}",
                    kind="deduction", amount=adv.outstanding,
                    explanation=(f"المبلغ {r2(adv.amount)} — المسدَّد "
                                 f"{r2(adv.repaid_amount)}"),
                    order=100))
        outstanding = total_outstanding(employment)
        if outstanding > 0:
            result.trace["advances"] = {"total": str(r2(outstanding))}

    # ── 6. خصم العهد غير المرجَعة (ق-41) ──
    from apps.employees.services.assets import assets_settlement
    assets = assets_settlement(employment)
    if assets["count"]:
        for a in assets["assets"]:
            value = Decimal(a["value"])
            if value > 0:
                result.lines.append(SettlementLine(
                    code=f"AST_{a['asset_no']}",
                    name_ar=f"عهدة لم تُرجَع: {a['name_ar']}",
                    kind="deduction", amount=value,
                    explanation=f"{a['status']} — {a['category']}",
                    order=110))
        result.trace["assets"] = assets

    # ── 7. الإجماليات ──
    result.total_earnings = r2(sum(
        (l.amount for l in result.lines if l.kind == "earning"), ZERO))
    result.total_deductions = r2(sum(
        (l.amount for l in result.lines if l.kind == "deduction"), ZERO))
    net = result.total_earnings - result.total_deductions

    # ق-37: الصافي لا ينزل عن صفر
    if net < ZERO:
        excess = result.total_deductions - result.total_earnings
        result.warnings.append(
            f"الاستقطاعات ({result.total_deductions}) تتجاوز المستحقات "
            f"({result.total_earnings}) — قُصّت والصافي صفر. "
            f"المتبقي على الموظف: {r2(excess)} ريال يُطالَب به خارج المسير")
        result.lines.append(SettlementLine(
            code="DED_CAP", name_ar="تعديل حد الاستقطاع",
            kind="deduction", amount=-excess,
            explanation=f"الصافي لا ينزل عن صفر — رُدّ {r2(excess)} ريال",
            order=900))
        result.total_deductions = result.total_earnings
        net = ZERO

    result.net_due = r2(net)
    result.trace["totals"] = {
        "earnings": str(result.total_earnings),
        "deductions": str(result.total_deductions),
        "net": str(result.net_due),
    }
    return result


def _remaining_leave_days(employment):
    """رصيد الإجازات المدفوعة المتبقي."""
    from apps.leaves.models import LeaveBalance
    total = ZERO
    for b in LeaveBalance.objects.filter(
            employment=employment,
            leave_type__is_paid=True).select_related("leave_type"):
        if b.available > 0:
            total += b.available
    return total


@transaction.atomic
def create_settlement_run(*, employment, termination_date, reason_code,
                          settings_obj, **kwargs):
    """
    ينشئ مسير مستحقات لموظف واحد ويحفظ قسيمته.

    مسير المستحقات يخرج عن الدورة الشهرية — يُنشأ عند الحاجة (ق-21).
    """
    from apps.payroll.models import (
        PayrollRun, PayrollRunStatus, PayrollRunType, Payslip, PayslipLine,
        PayslipLineType,
    )

    comp = employment.company
    result = compute_settlement(
        employment=employment, termination_date=termination_date,
        reason_code=reason_code, settings_obj=settings_obj, **kwargs)

    run_no = (f"PT-{termination_date.year}{termination_date.month:02d}"
              f"-{employment.id:05d}")
    if PayrollRun.objects.filter(company=comp, run_no=run_no).exists():
        raise SettlementError(f"مسير مستحقات قائم بالفعل: {run_no}")

    run = PayrollRun.objects.create(
        account=comp.account, company=comp, run_no=run_no,
        run_type=PayrollRunType.SETTLEMENT,
        period_year=termination_date.year,
        period_month=termination_date.month,
        accrual_date=termination_date,
        status=PayrollRunStatus.CALCULATED,
        employee_count=1,
        total_gross=result.total_earnings,
        total_deductions=result.total_deductions,
        total_net=result.net_due,
        calculated_at=timezone.now(),
        note=f"تسوية نهاية خدمة — {result.reason_label}")

    slip = Payslip.objects.create(
        account=comp.account, company=comp, run=run, employment=employment,
        gross_earnings=result.total_earnings,
        total_deductions=result.total_deductions,
        net_pay=result.net_due,
        payment_method=employment.payment_method, iban=employment.iban,
        include_in_wps=False,
        calculation_trace=result.trace, warnings=result.warnings)

    PayslipLine.objects.bulk_create([
        PayslipLine(
            payslip=slip, component_code=l.code, name_ar=l.name_ar,
            line_type=(PayslipLineType.EARNING if l.kind == "earning"
                       else PayslipLineType.DEDUCTION),
            amount=r2(l.amount), explanation=l.explanation,
            display_order=l.order)
        for l in sorted(result.lines, key=lambda x: x.order)
    ])

    return run, slip, result
