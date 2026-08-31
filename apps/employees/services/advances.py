"""
خدمة السلف (ق-41).

الشركة تختار طريقة السداد وحدودها، ولها إطفاء النظام كليًا.
الأقساط تُخصم في المسير وتُسجَّل بعد الخصم الفعلي.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.employees.models_assets import (
    Advance, AdvanceInstallment, AdvanceStatus, RepaymentMethod,
)

ZERO = Decimal("0")
TWO = Decimal("0.01")


def r2(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


class AdvanceError(Exception):
    pass


class AdvancesDisabled(AdvanceError):
    """نظام السلف مُطفأ لهذه الشركة."""


@dataclass
class EligibilityResult:
    allowed: bool
    max_allowed: Decimal | None = None
    reasons: list = field(default_factory=list)


def _next_advance_no(company):
    year = date.today().year
    count = Advance.objects.filter(
        company=company, advance_no__startswith=f"ADV-{year}").count()
    return f"ADV-{year}-{count + 1:05d}"


def check_eligibility(*, employment, amount, settings_obj, as_of=None):
    """
    يفحص أهلية السلفة قبل الطلب.

    الحدود: مبلغ أقصى، أو عدد رواتب، ومنع سلفة ثانية قبل السداد.
    """
    if not settings_obj.advances_enabled:
        raise AdvancesDisabled(
            "نظام السلف غير مفعّل في هذه الشركة")

    reasons = []
    amount = Decimal(str(amount))
    if amount <= 0:
        reasons.append("مبلغ السلفة يجب أن يكون أكبر من صفر")

    limits = []
    if settings_obj.advance_max_amount:
        limits.append(settings_obj.advance_max_amount)

    if settings_obj.advance_max_months_of_salary:
        from apps.employees.services.hiring import current_salary_structure
        structure = current_salary_structure(employment, as_of or date.today())
        if structure:
            limits.append(structure.gross_monthly
                          * settings_obj.advance_max_months_of_salary)

    max_allowed = min(limits) if limits else None
    if max_allowed is not None and amount > max_allowed:
        reasons.append(
            f"المبلغ ({r2(amount)}) يتجاوز الحد الأقصى ({r2(max_allowed)})")

    if settings_obj.advance_block_if_outstanding:
        outstanding = Advance.objects.filter(
            employment=employment, status=AdvanceStatus.ACTIVE).first()
        if outstanding and outstanding.outstanding > 0:
            reasons.append(
                f"سلفة قائمة لم تُسدَّد: {outstanding.advance_no} "
                f"(المتبقي {r2(outstanding.outstanding)})")

    return EligibilityResult(allowed=not reasons, max_allowed=max_allowed,
                             reasons=reasons)


@transaction.atomic
def create_advance(*, employment, amount, settings_obj, start_year,
                   start_month, repayment_method=None, installments_count=1,
                   installment_amount=None, reason="", request=None,
                   skip_eligibility=False):
    """
    ينشئ سلفة بحالة «قيد الاعتماد».

    لا تُخصم حتى تُعتمد — الاعتماد يمر بسلسلة الاعتماد كبقية الطلبات.
    """
    if not settings_obj.advances_enabled:
        raise AdvancesDisabled("نظام السلف غير مفعّل في هذه الشركة")

    amount = Decimal(str(amount))
    if not skip_eligibility:
        check = check_eligibility(employment=employment, amount=amount,
                                  settings_obj=settings_obj)
        if not check.allowed:
            raise AdvanceError(" | ".join(check.reasons))

    method = repayment_method or settings_obj_default_method(settings_obj)

    if method == RepaymentMethod.EQUAL_INSTALLMENTS:
        n = max(1, int(installments_count))
        if n > settings_obj.advance_max_installments:
            raise AdvanceError(
                f"عدد الأقساط ({n}) يتجاوز الحد "
                f"({settings_obj.advance_max_installments})")
        per = r2(amount / Decimal(n))
    elif method == RepaymentMethod.LUMP_SUM:
        n, per = 1, amount
    else:
        n = max(1, int(installments_count))
        per = (Decimal(str(installment_amount))
               if installment_amount else None)

    return Advance.objects.create(
        account=employment.account, company=employment.company,
        advance_no=_next_advance_no(employment.company),
        employment=employment, request=request, amount=amount,
        reason=reason, repayment_method=method, installments_count=n,
        installment_amount=per, start_year=start_year,
        start_month=start_month, status=AdvanceStatus.PENDING)


def settings_obj_default_method(settings_obj):
    """طريقة السداد الافتراضية — الأقساط المتساوية."""
    return RepaymentMethod.EQUAL_INSTALLMENTS


@transaction.atomic
def approve_advance(*, advance, approved_by_person):
    """اعتماد السلفة — تبدأ بالخصم من الشهر المحدد."""
    if advance.status != AdvanceStatus.PENDING:
        raise AdvanceError(
            f"السلفة {advance.get_status_display()} — لا تُعتمد")
    advance.status = AdvanceStatus.ACTIVE
    advance.approved_at = timezone.now()
    advance.approved_by_person = approved_by_person
    advance.save()

    from apps.core.services.audit import log_action
    log_action(instance=advance, action="approve",
               actor=approved_by_person, label=advance.advance_no,
               summary=(f"اعتماد سلفة {advance.amount} على "
                        f"{advance.installments_count} قسط"))
    return advance


def due_installment(advance, year, month):
    """
    القسط المستحق في شهر معيّن — أو صفر.

    يُستدعى من محرك الرواتب لخصمه في القسيمة.
    """
    if advance.status != AdvanceStatus.ACTIVE:
        return ZERO
    if advance.outstanding <= 0:
        return ZERO

    # قبل شهر البدء لا خصم
    if (year, month) < (advance.start_year, advance.start_month):
        return ZERO

    already = AdvanceInstallment.objects.filter(
        advance=advance, period_year=year, period_month=month,
        is_deducted=True).first()
    if already:
        return already.amount

    if advance.repayment_method == RepaymentMethod.LUMP_SUM:
        return (advance.outstanding
                if (year, month) == (advance.start_year, advance.start_month)
                else ZERO)

    planned = advance.installment_amount or ZERO
    if planned <= 0:
        return ZERO

    # القسط الأخير يُكمّل المتبقي: 1000 ÷ 3 = 333.33 وثلاثة أقساط
    # تعطي 999.99، فيبقى قرش يمنع السداد ويحجب سلفة جديدة (ق-41).
    paid_count = advance.installments.filter(is_deducted=True).count()
    is_last = paid_count >= advance.installments_count - 1
    if is_last or advance.outstanding <= planned:
        return advance.outstanding
    return planned


@transaction.atomic
def record_deduction(*, advance, year, month, amount, payslip=None):
    """
    يسجّل خصم قسط بعد إتمامه في المسير.

    السداد يُسجَّل بعد الخصم الفعلي لا قبله — فسجل السلفة يطابق
    القسائم الصادرة.
    """
    amount = Decimal(str(amount))
    if amount <= 0:
        return None
    if amount > advance.outstanding:
        amount = advance.outstanding

    inst, _ = AdvanceInstallment.objects.update_or_create(
        advance=advance, period_year=year, period_month=month,
        defaults={"account": advance.account, "company": advance.company,
                  "amount": amount, "payslip": payslip, "is_deducted": True})

    advance.repaid_amount = r2(advance.repaid_amount + amount)
    if advance.outstanding <= 0:
        advance.status = AdvanceStatus.SETTLED
        advance.settled_at = timezone.now()
    advance.save()
    return inst


def outstanding_advances(employment):
    """سلف قائمة على الموظف — تدخل مخالصة نهاية الخدمة."""
    return Advance.objects.filter(
        employment=employment, status=AdvanceStatus.ACTIVE)


def total_outstanding(employment):
    return sum((a.outstanding for a in outstanding_advances(employment)), ZERO)


@transaction.atomic
def settle_on_termination(*, employment, note=""):
    """
    تسوية السلف عند نهاية الخدمة — المتبقي يُخصم من المخالصة.
    """
    rows = []
    for adv in outstanding_advances(employment):
        rows.append({
            "advance_no": adv.advance_no,
            "original": str(r2(adv.amount)),
            "repaid": str(r2(adv.repaid_amount)),
            "outstanding": str(r2(adv.outstanding)),
        })
    return {
        "count": len(rows),
        "total_outstanding": str(r2(total_outstanding(employment))),
        "advances": rows,
        "note": note or "يُخصم المتبقي من مستحقات نهاية الخدمة",
    }
