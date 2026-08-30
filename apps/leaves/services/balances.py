"""
أرصدة الإجازات: الاستحقاق والاستهلاك والترحيل.

كل سياسة خيار الشركة (ق-32): الاستحقاق شهري أو سنوي، والترحيل
كامل أو محدود أو ساقط، والعطل تُمدّد أو تُحتسب.

الرصيد الفردي يسبق افتراضي النوع (ق-33).
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from apps.leaves.models import (
    AccrualMethod, CarryForwardPolicy, HolidayTreatment, LeaveBalance,
    LeaveEntitlement, LeaveType,
)

TWO = Decimal("0.01")
MONTHS_PER_YEAR = Decimal("12")


def r2(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


class LeaveError(Exception):
    pass


# ══════════ الاستحقاق السنوي للموظف ══════════

def annual_days_for(employment, leave_type, as_of=None):
    """
    أيام الاستحقاق السنوي (ق-33).

    الترتيب: استحقاق فردي بتاريخ سريان ← افتراضي النوع ←
    الترقية بعد خمس سنوات إن كانت معرّفة.
    """
    day = as_of or date.today()

    ent = (LeaveEntitlement.objects
           .filter(employment=employment, leave_type=leave_type,
                   effective_from__lte=day)
           .order_by("-effective_from").first())
    if ent and (ent.effective_to is None or ent.effective_to >= day):
        return ent.days_per_year

    base = leave_type.days_per_year
    if base is None:
        return Decimal("0")

    if leave_type.days_after_five_years:
        start = employment.effective_service_start
        years = Decimal((day - start).days) / Decimal("360")
        if years >= 5:
            return leave_type.days_after_five_years
    return base


# ══════════ احتساب أيام الإجازة ══════════

@dataclass(frozen=True)
class LeaveDaysComputation:
    calendar_days: int
    charged_days: Decimal
    extended_days: int
    end_date: date
    excluded: list = field(default_factory=list)


def compute_leave_days(*, company, leave_type, start_date, requested_days,
                       shift=None):
    """
    يحتسب الأيام المخصومة من الرصيد وتاريخ العودة.

    ق-33: العطل تُمدّد الإجازة افتراضًا، والراحة الأسبوعية تُحتسب.
    والشركة تعدّل كليهما لكل نوع.
    """
    from apps.organization.models import Holiday

    requested = Decimal(str(requested_days))
    if requested <= 0:
        raise LeaveError("عدد الأيام يجب أن يكون أكبر من صفر")

    working_days = set(shift.working_days) if shift and shift.working_days \
        else {0, 1, 2, 3, 4}

    horizon = start_date + timedelta(days=int(requested) * 3 + 30)
    holidays = set()
    for h in Holiday.objects.filter(company=company,
                                    start_date__lte=horizon,
                                    end_date__gte=start_date):
        cur = h.start_date
        while cur <= h.end_date:
            holidays.add(cur)
            cur += timedelta(days=1)

    charged = Decimal("0")
    extended = 0
    excluded = []
    cur = start_date
    last = start_date

    while charged < requested:
        weekday = (cur.weekday() + 1) % 7      # الأحد=0
        is_weekend = weekday not in working_days
        is_holiday = cur in holidays

        skip = False
        if is_holiday and leave_type.holiday_treatment == HolidayTreatment.EXTENDS:
            skip = True
            excluded.append({"date": str(cur), "reason": "عطلة"})
        elif is_weekend and leave_type.weekend_treatment == HolidayTreatment.EXTENDS:
            skip = True
            excluded.append({"date": str(cur), "reason": "راحة أسبوعية"})

        if skip:
            extended += 1
        else:
            charged += 1
        last = cur
        cur += timedelta(days=1)

        if extended > 365:
            raise LeaveError("تعذّر احتساب الإجازة — راجع أيام العمل والعطل")

    return LeaveDaysComputation(
        calendar_days=(last - start_date).days + 1,
        charged_days=charged, extended_days=extended,
        end_date=last, excluded=excluded)


# ══════════ الأرصدة ══════════

@transaction.atomic
def ensure_balance(employment, leave_type, year):
    bal, _ = LeaveBalance.objects.get_or_create(
        employment=employment, leave_type=leave_type, year=year,
        defaults={"account": employment.account,
                  "company": employment.company})
    return bal


@transaction.atomic
def accrue(employment, leave_type, as_of=None):
    """
    يحتسب المستحق حتى تاريخ معيّن (ق-32).

    شهري: بالتناسب من بداية السنة أو المباشرة.
    سنوي: الرصيد كاملًا في بداية السنة.
    """
    day = as_of or date.today()
    bal = ensure_balance(employment, leave_type, day.year)
    annual = annual_days_for(employment, leave_type, day)

    if leave_type.accrual_method == AccrualMethod.ANNUAL:
        bal.accrued = annual
    elif leave_type.accrual_method == AccrualMethod.MONTHLY:
        start = max(employment.effective_service_start,
                    date(day.year, 1, 1))
        months = Decimal((day - start).days) / Decimal("30")
        months = min(months, MONTHS_PER_YEAR)
        bal.accrued = r2(annual / MONTHS_PER_YEAR * months)
    else:
        bal.accrued = Decimal("0")      # per_event و none

    bal.last_accrual_date = day
    bal.save()
    return bal


@transaction.atomic
def consume(employment, leave_type, days, year=None):
    """يخصم من الرصيد. يمنع تجاوز المتاح."""
    yr = year or date.today().year
    bal = ensure_balance(employment, leave_type, yr)
    amount = Decimal(str(days))

    if leave_type.accrual_method in (AccrualMethod.PER_EVENT,
                                     AccrualMethod.NONE):
        bal.consumed += amount      # بلا رصيد — للتتبع فقط
        bal.save()
        return bal

    if amount > bal.available:
        raise LeaveError(
            f"الرصيد المتاح {r2(bal.available)} يومًا "
            f"والمطلوب {r2(amount)} — لا يكفي")

    bal.consumed += amount
    bal.save()
    return bal


@transaction.atomic
def carry_forward(employment, leave_type, from_year):
    """
    يُرحّل الرصيد للسنة التالية حسب سياسة النوع (ق-32).
    """
    src = ensure_balance(employment, leave_type, from_year)
    available = src.available

    policy = leave_type.carry_forward_policy
    if policy == CarryForwardPolicy.EXPIRE:
        carried = Decimal("0")
    elif policy == CarryForwardPolicy.CAPPED:
        cap = leave_type.max_carry_forward_days or Decimal("0")
        carried = min(available, cap)
    else:
        carried = available

    carried = max(carried, Decimal("0"))
    src.carried_forward = carried
    src.save()

    dst = ensure_balance(employment, leave_type, from_year + 1)
    dst.opening_balance = carried
    dst.save()
    return {"from_year": from_year, "available": r2(available),
            "carried": r2(carried), "policy": policy,
            "expired": r2(available - carried)}


def balance_summary(employment, year=None):
    """ملخص أرصدة الموظف — لشاشة «رصيدي»."""
    yr = year or date.today().year
    return [
        {
            "leave_type": b.leave_type.name_ar,
            "code": b.leave_type.code,
            "opening": str(r2(b.opening_balance)),
            "accrued": str(r2(b.accrued)),
            "consumed": str(r2(b.consumed)),
            "adjusted": str(r2(b.adjusted)),
            "available": str(r2(b.available)),
            "is_paid": b.leave_type.is_paid,
        }
        for b in LeaveBalance.objects.filter(
            employment=employment, year=yr).select_related("leave_type")
    ]


# ══════════ التحقق من الأهلية ══════════

def check_eligibility(employment, leave_type, as_of=None):
    """
    شروط النوع: الجنس، الديانة، مدة الخدمة، مرة واحدة طوال الخدمة.
    """
    day = as_of or date.today()
    person = employment.person
    errors = []

    if leave_type.gender_restriction != "any":
        if person.gender != leave_type.gender_restriction:
            errors.append(
                f"{leave_type.name_ar} مخصصة لـ"
                f"{leave_type.get_gender_restriction_display()}")

    if leave_type.min_service_months:
        months = Decimal(
            (day - employment.effective_service_start).days) / Decimal("30")
        if months < leave_type.min_service_months:
            errors.append(
                f"تتطلب {leave_type.min_service_months} شهر خدمة "
                f"(الحالي {int(months)})")

    if leave_type.once_per_service:
        used = LeaveBalance.objects.filter(
            employment=employment, leave_type=leave_type,
            consumed__gt=0).exists()
        if used:
            errors.append(f"{leave_type.name_ar} تُمنح مرة واحدة طوال الخدمة")

    return errors


# ══════════ التسويات اليدوية ══════════

@transaction.atomic
def adjust_balance(*, employment, leave_type, days, reason,
                   adjusted_by_person, year=None):
    """
    تسوية يدوية على الرصيد — إضافة أو خصم.

    تُسجَّل في حقل adjusted المنفصل عن accrued، فلا تمحوها إعادة
    احتساب الاستحقاق. نفس مبدأ التعديل اليدوي في الحضور: قرار بشري
    لا تمحوه المعالجة الآلية.

    الاستخدامات: رصيد افتتاحي عند الترحيل من نظام آخر، منحة
    استثنائية، تصحيح خطأ إدخال.
    """
    if not reason or not reason.strip():
        raise LeaveError("سبب التسوية مطلوب — يُسجَّل في سجل التدقيق")

    amount = Decimal(str(days))
    if amount == 0:
        raise LeaveError("قيمة التسوية لا يمكن أن تكون صفرًا")

    yr = year or date.today().year
    bal = ensure_balance(employment, leave_type, yr)

    new_available = bal.available + amount
    if new_available < 0:
        raise LeaveError(
            f"التسوية تجعل الرصيد سالبًا ({r2(new_available)}). "
            f"المتاح حاليًا {r2(bal.available)} يومًا")

    bal.adjusted += amount
    bal.save()

    from apps.core.audit import record_adjustment
    record_adjustment(
        employment=employment, leave_type=leave_type, amount=amount,
        reason=reason.strip(), person=adjusted_by_person, year=yr)

    return {
        "leave_type": leave_type.name_ar,
        "amount": str(r2(amount)),
        "total_adjusted": str(r2(bal.adjusted)),
        "available_now": str(r2(bal.available)),
        "reason": reason.strip(),
    }
