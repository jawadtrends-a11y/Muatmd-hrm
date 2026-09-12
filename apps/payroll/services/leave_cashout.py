"""
مخالصة الإجازة (ق-138).

⚠️ **صرف بدل الإجازة بلا استخدامٍ فعليّ ولا انتهاء علاقة مخالفٌ
لنظام العمل** — والمسؤولية على صاحب العمل.

فلا نمنعه (شركاتٌ تعمله)، **وننبّه عليه**، ونجعله خيارًا مطفأً
افتراضًا (قرار جواد).
"""
import logging
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class CashoutError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


#: التنبيه النظاميّ — يُعرض ويُحفظ مع المخالصة
LEGAL_WARNING = (
    "⚠️ بدل الإجازة لا يُصرف نظامًا إلا عند استخدامها فعليًّا أو "
    "انتهاء العلاقة التعاقدية (المادة ١٠٩). وصرفُه أثناء الخدمة "
    "مخالفةٌ مسؤوليتها على صاحب العمل."
)


def preview(*, employment, days, as_of=None, settings_obj=None):
    """
    يحتسب بدل الإجازة بلا حفظ — **بأساس الأجر المعتمد**.

    ⚠️ **ونفس أساس المكافأة**: فبدل الإجازة يُحسب على الأجر
    الفعليّ لا الأساسيّ وحده (المادة ١٠٩) — والشركة تحدّد ما يدخل
    فيه من إعدادات المسير.
    """
    from django.utils import timezone

    from apps.payroll.models import PayrollSettings
    from apps.payroll.services.settlement import _eosb_wage_for

    as_of = as_of or timezone.localdate()
    settings_obj = settings_obj or PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    if settings_obj is None:
        raise CashoutError("لا إعدادات رواتب لهذه الشركة")

    try:
        days_dec = Decimal(str(days))
    except (TypeError, ArithmeticError, ValueError):
        raise CashoutError("عدد أيام غير صالح")
    if days_dec <= 0:
        raise CashoutError("عدد الأيام مطلوب")

    wage, structure = _eosb_wage_for(employment, as_of, settings_obj)
    daily = (wage / Decimal(settings_obj.payroll_days_per_month or 30))
    amount = (daily * days_dec).quantize(Decimal("0.01"))

    return {
        "days": str(days_dec),
        "monthly_wage": str(wage.quantize(Decimal("0.01"))),
        "daily_rate": str(daily.quantize(Decimal("0.01"))),
        "amount": str(amount),
        "basis": settings_obj.eosb_wage_basis,
        "allowed": bool(settings_obj.allow_leave_cashout),
        "warning": LEGAL_WARNING,
    }


def available_days(employment, leave_type=None, year=None):
    """رصيد الإجازة القابل للصرف."""
    from django.utils import timezone

    from apps.leaves.models import LeaveBalance, LeaveType

    year = year or timezone.localdate().year
    qs = LeaveBalance.objects.filter(employment=employment, year=year)
    if leave_type is not None:
        qs = qs.filter(leave_type=leave_type)
    else:
        annual = LeaveType.objects.filter(
            company_id=employment.company_id, code="ANNUAL").first()
        if annual:
            qs = qs.filter(leave_type=annual)

    b = qs.first()
    if b is None:
        return ZERO
    return (Decimal(b.opening_balance or 0)
            + Decimal(b.accrued or 0)
            + Decimal(b.adjusted or 0)
            + Decimal(b.carried_forward or 0)
            - Decimal(b.consumed or 0))


@transaction.atomic
def cash_out(*, employment, days, reason="", by_person_id=None,
             as_of=None):
    """
    يخصم الأيام من الرصيد ويُنشئ مستحقًّا.

    ⚠️ **ولا يُصرف أكثر من الرصيد**: فصرفُ ما لا يملكه دَينٌ عليه
    لا بدل.
    """
    from django.utils import timezone

    from apps.leaves.models import LeaveBalance, LeaveType
    from apps.payroll.models import PayrollSettings

    as_of = as_of or timezone.localdate()
    settings_obj = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    if settings_obj is None:
        raise CashoutError("لا إعدادات رواتب لهذه الشركة")

    if not settings_obj.allow_leave_cashout:
        raise CashoutError(
            "مخالصة الإجازة أثناء الخدمة غير مفعَّلة — "
            "تُفعَّل من إعدادات الرواتب بعد الاطّلاع على التنبيه النظاميّ")

    days_dec = Decimal(str(days))
    balance = available_days(employment)
    if days_dec > balance:
        raise CashoutError(
            f"الرصيد المتاح {balance} يومًا — لا يُصرف أكثر منه")

    calc = preview(employment=employment, days=days_dec, as_of=as_of,
                   settings_obj=settings_obj)

    annual = LeaveType.objects.filter(
        company_id=employment.company_id, code="ANNUAL").first()
    if annual is None:
        raise CashoutError("لا نوع إجازة سنوية معرَّف")

    b = LeaveBalance.objects.filter(
        employment=employment, leave_type=annual,
        year=as_of.year).first()
    if b is None:
        raise CashoutError("لا رصيد إجازة لهذه السنة")

    b.consumed = Decimal(b.consumed or 0) + days_dec
    b.save(update_fields=["consumed", "updated_at"])

    logger.info("مخالصة إجازة %s يومًا للموظف %s بمبلغ %s",
                days_dec, employment.employee_no, calc["amount"])
    return calc
