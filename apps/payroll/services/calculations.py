"""
الدوال المالية الأساسية: التأمينات، أجر الساعة، العمل الإضافي.

قواعد ملزمة:
  • كل الحسابات بـDecimal لا float — الفلوس لا تحتمل تقريبًا عائمًا
  • التقريب لخانتين بـROUND_HALF_UP في النتيجة النهائية فقط
  • النسب تُقرأ بتاريخ الاستحقاق لا تاريخ اليوم
  • أجر الساعة في دالة واحدة — توحيده يمنع تناقض الأرقام بين الشاشات
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TWO = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    """تقريب لخانتين — يُستخدم في النتيجة النهائية فقط."""
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


# ══════════════════ التأمينات الاجتماعية ══════════════════

@dataclass(frozen=True)
class GosiResult:
    subject_wage: Decimal
    employee_share: Decimal
    employer_share: Decimal
    warnings: list = field(default_factory=list)
    breakdown: dict = field(default_factory=dict)


class GosiError(Exception):
    pass


def calculate_gosi(*, subject_wage: Decimal, scheme_code: str,
                   as_of: date, rate=None) -> GosiResult:
    """
    اشتراك التأمينات.

    subject_wage: الأجر الخاضع = مجموع المكوّنات المعلّمة is_gosi_subject
                  (الافتراض: الأساسي + بدل السكن — قرار المالك)
    as_of: تاريخ استحقاق المسير لا تاريخ اليوم
    """
    if rate is None:
        from apps.payroll.services.gosi_seed import get_effective_rate
        rate = get_effective_rate(scheme_code, as_of)
    if rate is None:
        raise GosiError(
            f"لا توجد نسب سارية للنظام {scheme_code} بتاريخ {as_of}")

    wage = Decimal(subject_wage)

    # قاعدة حاكمة (ق-9): نحفظ مدخلات الشركة كما هي ولا نصحّحها.
    # الحساب على الأجر المسجّل، والخروج عن الحدود تحذير لا تعديل —
    # فقسيمة الموظف تطابق أجره المسجّل، والقرار للشركة لا للنظام.
    warnings = []
    if wage < rate.min_subject_wage:
        warnings.append(
            f"الأجر الخاضع ({r2(wage)}) دون الحد الأدنى المعلن "
            f"({rate.min_subject_wage}) — راجع التسجيل لدى التأمينات"
        )
    if wage > rate.max_subject_wage:
        warnings.append(
            f"الأجر الخاضع ({r2(wage)}) يتجاوز الحد الأعلى المعلن "
            f"({rate.max_subject_wage}) — راجع التسجيل لدى التأمينات"
        )

    emp_pension = r2(wage * rate.employee_pension_rate)
    emp_saned   = r2(wage * rate.employee_saned_rate)
    er_pension  = r2(wage * rate.employer_pension_rate)
    er_saned    = r2(wage * rate.employer_saned_rate)
    er_hazards  = r2(wage * rate.employer_hazards_rate)

    return GosiResult(
        subject_wage=r2(wage),
        employee_share=emp_pension + emp_saned,
        employer_share=er_pension + er_saned + er_hazards,
        warnings=warnings,
        breakdown={
            "subject_wage": str(r2(wage)),
            "min_declared": str(rate.min_subject_wage),
            "max_declared": str(rate.max_subject_wage),
            "out_of_range": bool(warnings),
            "employee_pension": str(emp_pension),
            "employee_saned": str(emp_saned),
            "employer_pension": str(er_pension),
            "employer_saned": str(er_saned),
            "employer_hazards": str(er_hazards),
            "rate_id": rate.id,
            "rate_effective_from": str(rate.effective_from),
            "scheme": scheme_code,
        },
    )


# ══════════════════ أجر الساعة والعمل الإضافي ══════════════════

def hourly_rate(monthly_amount: Decimal, days_per_month: int = 30,
                hours_per_day: Decimal = Decimal("8")) -> Decimal:
    """
    أجر الساعة — الدالة الوحيدة في النظام.

    القاعدة المعتمدة في السوق السعودي: الشهر 30 يومًا، واليوم 8 ساعات.
    توحيدها هنا يمنع تناقض الأرقام بين الشاشات — عيب شائع في الأنظمة
    الجاهزة.
    """
    if days_per_month <= 0 or Decimal(hours_per_day) <= 0:
        raise ValueError("أيام الشهر وساعات اليوم يجب أن تكون أكبر من صفر")
    return (Decimal(monthly_amount) / Decimal(days_per_month)
            / Decimal(hours_per_day))


def daily_rate(monthly_amount: Decimal, days_per_month: int = 30) -> Decimal:
    return Decimal(monthly_amount) / Decimal(days_per_month)


@dataclass(frozen=True)
class OvertimeResult:
    hours: Decimal
    hourly_amount: Decimal
    total: Decimal
    basis: str
    explanation: str


def calculate_overtime(*, overtime_minutes: int, basic_salary: Decimal,
                       full_wage: Decimal, basis: str,
                       days_per_month: int = 30,
                       hours_per_day: Decimal = Decimal("8")) -> OvertimeResult:
    """
    أجر العمل الإضافي.

    الافتراض المعتمد (قرار المالك): أجر ساعة الأجر الكامل + 50% من
    ساعة الأساسي. المادة 107 تحتمل قراءتين، فجعلناها سياسة معلَنة
    لا افتراضًا مخفيًا.
    """
    hours = Decimal(overtime_minutes) / Decimal(60)
    basic_hr = hourly_rate(basic_salary, days_per_month, hours_per_day)
    full_hr = hourly_rate(full_wage, days_per_month, hours_per_day)

    if basis == "full_plus_half_basic":
        rate = full_hr + (basic_hr * Decimal("0.5"))
        expl = "أجر ساعة الأجر الكامل + 50% من ساعة الأساسي"
    elif basis == "basic_x1_5":
        rate = basic_hr * Decimal("1.5")
        expl = "أجر ساعة الأساسي × 1.5"
    elif basis == "full_x1_5":
        rate = full_hr * Decimal("1.5")
        expl = "أجر ساعة الأجر الكامل × 1.5"
    else:
        raise ValueError(f"أساس عمل إضافي غير معروف: {basis}")

    return OvertimeResult(
        hours=r2(hours), hourly_amount=r2(rate),
        total=r2(hours * rate), basis=basis,
        explanation=f"{expl} — {r2(hours)} ساعة × {r2(rate)} ريال",
    )


def calculate_absence_deduction(*, unpaid_days: Decimal,
                                monthly_wage: Decimal,
                                days_per_month: int = 30) -> Decimal:
    """خصم الغياب — من نفس دالة أجر اليوم لا قسمة أخرى."""
    return r2(daily_rate(monthly_wage, days_per_month) * Decimal(unpaid_days))
