"""
الجزاءات التأديبية (ق-119).

⚠️ **القيود النظامية مفروضة في الكود** لا في الشاشة — من النموذج
الموحّد للائحة تنظيم العمل (وزارة الموارد البشرية):

| القيد |
|---|
| الغرامة بين **أجر يوم وخمسة أيام** في الشهر — حدًّا أقصى |
| وعن **المخالفة الواحدة** لا تزيد على أجر خمسة أيام |
| **جزاء واحد** للمخالفة الواحدة |
| الإيقاف بلا أجر لا يتجاوز **٥ أيام في الشهر** |
| الحرمان من الترقية أو العلاوة **سنة** أقصاها |
| ما يتجاوز **أجر يوم واحد** يلزمه إبلاغ كتابيّ وسماع أقوال ومحضر |
| **صحيفة جزاءات** لكل عامل — فالسجلّ يُراجَع |

**واللائحة نفسها تُبذر ثم تعدّلها الشركة** (ق-9): فهي المعتمدة
لديها من الوزارة، ولا نفترض عنها.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.employees.models_penalties import (
    Penalty, PenaltyDegree, PenaltyKind, PenaltyStatus,
    ViolationCategory, ViolationType)

logger = logging.getLogger(__name__)

# سقف الحسم والإيقاف شهريًّا — نصٌّ نظاميّ لا إعداد
MAX_DEDUCTION_DAYS_PER_MONTH = Decimal("5")
MAX_SUSPENSION_DAYS_PER_MONTH = Decimal("5")
# ⚠️ وعن المخالفة الواحدة لا تزيد الغرامة على أجر خمسة أيام
MAX_DEDUCTION_DAYS_PER_VIOLATION = Decimal("5")
# وما تجاوز أجر يومٍ واحد يلزمه محضر بسماع أقوال الموظف
STATEMENT_REQUIRED_ABOVE_DAYS = Decimal("1")


class PenaltyError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


# ══════════ اللائحة الافتراضية ══════════
# تُبذر ثم تعدّلها الشركة — وهي مسؤولة عن مطابقتها للائحتها
# المعتمدة من الوزارة.
#
# (الرمز، المخالفة، التصنيف، [(تكرار، جزاء، أيام)])
DEFAULT_VIOLATIONS = [
    ("LATE-15", "التأخر عن موعد العمل حتى ١٥ دقيقة بلا إذن",
     ViolationCategory.ATTENDANCE, [
         (1, PenaltyKind.WARNING, "0"),
         (2, PenaltyKind.WAGE_DEDUCTION, "0.25"),
         (3, PenaltyKind.WAGE_DEDUCTION, "0.5"),
         (4, PenaltyKind.WAGE_DEDUCTION, "1"),
     ]),
    ("LATE-30", "التأخر أكثر من ١٥ دقيقة ودون ٣٠ بلا إذن",
     ViolationCategory.ATTENDANCE, [
         (1, PenaltyKind.WAGE_DEDUCTION, "0.25"),
         (2, PenaltyKind.WAGE_DEDUCTION, "0.5"),
         (3, PenaltyKind.WAGE_DEDUCTION, "1"),
         (4, PenaltyKind.WAGE_DEDUCTION, "2"),
     ]),
    ("EARLY-OUT", "الانصراف قبل نهاية الدوام بلا إذن",
     ViolationCategory.ATTENDANCE, [
         (1, PenaltyKind.WARNING, "0"),
         (2, PenaltyKind.WAGE_DEDUCTION, "0.5"),
         (3, PenaltyKind.WAGE_DEDUCTION, "1"),
         (4, PenaltyKind.WAGE_DEDUCTION, "2"),
     ]),
    ("ABSENT-1", "الغياب يومًا بلا عذر مقبول",
     ViolationCategory.ATTENDANCE, [
         (1, PenaltyKind.WAGE_DEDUCTION, "1"),
         (2, PenaltyKind.WAGE_DEDUCTION, "2"),
         (3, PenaltyKind.WAGE_DEDUCTION, "3"),
         (4, PenaltyKind.WAGE_DEDUCTION, "5"),
     ]),
    ("NO-PUNCH", "عدم التوقيع بالحضور أو الانصراف",
     ViolationCategory.ATTENDANCE, [
         (1, PenaltyKind.WARNING, "0"),
         (2, PenaltyKind.WARNING, "0"),
         (3, PenaltyKind.WAGE_DEDUCTION, "0.5"),
         (4, PenaltyKind.WAGE_DEDUCTION, "1"),
     ]),
    ("SLEEP", "النوم أثناء العمل",
     ViolationCategory.WORK_ORG, [
         (1, PenaltyKind.WARNING, "0"),
         (2, PenaltyKind.WAGE_DEDUCTION, "1"),
         (3, PenaltyKind.WAGE_DEDUCTION, "2"),
         (4, PenaltyKind.WAGE_DEDUCTION, "3"),
     ]),
    ("LEAVE-SITE", "ترك مكان العمل أثناء الدوام بلا إذن",
     ViolationCategory.WORK_ORG, [
         (1, PenaltyKind.WARNING, "0"),
         (2, PenaltyKind.WAGE_DEDUCTION, "0.5"),
         (3, PenaltyKind.WAGE_DEDUCTION, "1"),
         (4, PenaltyKind.WAGE_DEDUCTION, "2"),
     ]),
    ("REFUSE-ORDER", "رفض تنفيذ أمر عمل مشروع",
     ViolationCategory.WORK_ORG, [
         (1, PenaltyKind.WAGE_DEDUCTION, "1"),
         (2, PenaltyKind.WAGE_DEDUCTION, "2"),
         (3, PenaltyKind.WAGE_DEDUCTION, "3"),
         (4, PenaltyKind.WAGE_DEDUCTION, "5"),
     ]),
    ("NO-SAFETY", "عدم استعمال أدوات السلامة المقرَّرة",
     ViolationCategory.SAFETY, [
         (1, PenaltyKind.WARNING, "0"),
         (2, PenaltyKind.WAGE_DEDUCTION, "1"),
         (3, PenaltyKind.WAGE_DEDUCTION, "2"),
         (4, PenaltyKind.WAGE_DEDUCTION, "3"),
     ]),
    ("SMOKING", "التدخين في الأماكن المحظورة",
     ViolationCategory.SAFETY, [
         (1, PenaltyKind.WAGE_DEDUCTION, "1"),
         (2, PenaltyKind.WAGE_DEDUCTION, "2"),
         (3, PenaltyKind.WAGE_DEDUCTION, "3"),
         (4, PenaltyKind.WAGE_DEDUCTION, "5"),
     ]),
    ("QUARREL", "المشاجرة مع الزملاء أثناء العمل",
     ViolationCategory.CONDUCT, [
         (1, PenaltyKind.WAGE_DEDUCTION, "1"),
         (2, PenaltyKind.WAGE_DEDUCTION, "3"),
         (3, PenaltyKind.WAGE_DEDUCTION, "5"),
         (4, PenaltyKind.SUSPENSION, "3"),
     ]),
    ("MISUSE", "إساءة استعمال ممتلكات المنشأة",
     ViolationCategory.CONDUCT, [
         (1, PenaltyKind.WARNING, "0"),
         (2, PenaltyKind.WAGE_DEDUCTION, "1"),
         (3, PenaltyKind.WAGE_DEDUCTION, "3"),
         (4, PenaltyKind.WAGE_DEDUCTION, "5"),
     ]),
]


@transaction.atomic
def provision_default_violations(company):
    """
    يبذر اللائحة الافتراضية للشركة — تُعدَّل بحرّية بعدها (ق-9).

    ⚠️ وهي **استرشادية**: الشركة مسؤولة عن مطابقتها للائحتها
    المعتمدة من وزارة الموارد البشرية.
    """
    created = []
    for order, (code, name, cat, degrees) in enumerate(DEFAULT_VIOLATIONS,
                                                       start=1):
        v, is_new = ViolationType.objects.get_or_create(
            company=company, code=code,
            defaults={"account": company.account, "name_ar": name,
                      "category": cat, "sort_order": order * 10})
        if not is_new:
            continue
        created.append(code)
        PenaltyDegree.objects.bulk_create([
            PenaltyDegree(violation=v, occurrence=occ, kind=kind,
                          days=Decimal(days))
            for occ, kind, days in degrees
        ])
    return created


def occurrence_for(employment, violation, on_date=None):
    """
    رقم التكرار لهذه المخالفة — ١ للأولى.

    ⚠️ وما مضى على سابقته أكثر من **مدّة السقوط** يُعدّ أولى:
    فالموظف لا يُلاحَق بمخالفةٍ قديمة أبدًا.
    """
    on_date = on_date or timezone.localdate()
    since = on_date - timedelta(days=violation.reset_days)
    # ق-119: ما لم يُحتسب في التكرار لا يرفع الدرجة — فالتوثيق
    # حفظُ واقعة، والتصعيد قرارٌ إداريّ مستقلّ.
    prior = Penalty.objects.filter(
        employment=employment, violation=violation,
        occurred_on__gte=since, occurred_on__lte=on_date,
        count_occurrence=True,
        status__in=[PenaltyStatus.ISSUED, PenaltyStatus.OBJECTED],
    ).count()
    return prior + 1


def degree_for(violation, occurrence):
    """درجة الجزاء لهذا التكرار — وأعلاها لما تجاوزها."""
    exact = violation.degrees.filter(occurrence=occurrence).first()
    if exact:
        return exact
    return violation.degrees.order_by("-occurrence").first()


def _daily_wage(employment):
    """
    أجر اليوم — **من أساس خصم الغياب نفسه** (ق-36).

    فالنموذج يقول «الأجر» ولا يقصره على الأساسيّ. والجزاء والغياب
    خصمان من أجرٍ واحد: واختلاف أساسهما يجعل يومًا بجزاء أرخص من
    يومٍ بغياب بلا مسوّغ.

    والشركة تستثني بدلًا بإطفاء علم `is_absence_base`.
    """
    from apps.employees.models import SalaryStructure
    from apps.payroll.models import ComponentType

    st = (SalaryStructure.objects
          .filter(employment=employment, effective_to__isnull=True)
          .order_by("-effective_from").first())
    if st is None:
        return Decimal("0")

    base = Decimal("0")
    for comp, amount in st.as_lines():
        if (comp.component_type == ComponentType.EARNING
                and comp.is_absence_base):
            base += Decimal(amount)
    return (base / Decimal("30")).quantize(Decimal("0.01"))


def deducted_days_in_month(employment, on_date):
    """مجموع أيام الحسم الموقَّعة عليه في شهر التاريخ."""
    start = on_date.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    rows = Penalty.objects.filter(
        employment=employment, occurred_on__gte=start, occurred_on__lte=end,
        kind=PenaltyKind.WAGE_DEDUCTION, apply_deduction=True,
        status__in=[PenaltyStatus.ISSUED, PenaltyStatus.OBJECTED],
    ).values_list("days", flat=True)
    return sum((Decimal(d) for d in rows), Decimal("0"))


def preview(employment, violation, on_date=None):
    """
    ما سيقع لو وُقّع الجزاء — يُعرض قبل التوقيع.

    فالمسؤول يرى الدرجة والمبلغ وما بقي من سقف الشهر قبل أن
    يقرّر.
    """
    on_date = on_date or timezone.localdate()
    occ = occurrence_for(employment, violation, on_date)
    deg = degree_for(violation, occ)
    if deg is None:
        raise PenaltyError("لا درجات مضبوطة لهذه المخالفة")

    daily = _daily_wage(employment)
    used = deducted_days_in_month(employment, on_date)
    remaining = MAX_DEDUCTION_DAYS_PER_MONTH - used

    days = Decimal(deg.days)
    capped = False
    # سقف المخالفة الواحدة أوّلًا، ثم سقف الشهر
    if (deg.kind == PenaltyKind.WAGE_DEDUCTION
            and days > MAX_DEDUCTION_DAYS_PER_VIOLATION):
        days = MAX_DEDUCTION_DAYS_PER_VIOLATION
        capped = True
    if deg.kind == PenaltyKind.WAGE_DEDUCTION and days > remaining:
        days = max(remaining, Decimal("0"))
        capped = True

    # ق-119: الخصم بثلاثة مستويات — إعدادُ الشركة سقفٌ، وبندُ
    # اللائحة يقيّده، والمسؤول يقرّر عند التوقيع.
    from apps.payroll.models import PayrollSettings

    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    company_allows = bool(getattr(st, "penalties_deduct_enabled", True))
    deductible = (company_allows and violation.financial_effect
                  and deg.kind in (PenaltyKind.WAGE_DEDUCTION,
                                   PenaltyKind.SUSPENSION))
    if not deductible:
        days = Decimal("0")
        capped = False

    return {
        "occurrence": occ,
        "kind": deg.kind,
        "deductible": deductible,
        "block_reason": ("" if deductible else
                         ("خصم الجزاءات معطَّل في إعدادات الشركة"
                          if not company_allows else
                          "هذه المخالفة بلا أثر ماليّ"
                          if not violation.financial_effect else "")),
        "kind_label": deg.get_kind_display(),
        "degree_days": str(deg.days),
        "days": str(days),
        "daily_wage": str(daily),
        "amount": str((daily * days).quantize(Decimal("0.01"))),
        "deducted_this_month": str(used),
        "monthly_cap": str(MAX_DEDUCTION_DAYS_PER_MONTH),
        "capped": capped,
        "cap_note": ("بلغ سقف الحسم الشهريّ (٥ أيام) — خُفّض المحسوم"
                     if capped else ""),
    }


@transaction.atomic
def issue(*, employment, violation, occurred_on, description,
          employee_statement, issued_by_person_id=None, on_date=None,
          apply_deduction=True, count_occurrence=True):
    """
    يوقّع الجزاء.

    ⚠️ **لا جزاء بلا إفادة الموظف**: النموذج يوجب إخطاره كتابةً
    وسماع دفاعه وإثباته في محضر — فبلا إفادة لا توقيع.
    """
    if not (description or "").strip():
        raise PenaltyError("وصف الواقعة مطلوب")
    p = preview(employment, violation, occurred_on)

    # ⚠️ النموذج: ما تجاوز **أجر يوم واحد** يلزمه إبلاغ كتابيّ
    # وسماع أقوال وتحقيق دفاع بمحضر يودع في ملفّه. وما دونه لا.
    needs_statement = (
        p["kind"] != PenaltyKind.WARNING
        and Decimal(p["days"]) > STATEMENT_REQUIRED_ABOVE_DAYS)
    if needs_statement and not (employee_statement or "").strip():
        raise PenaltyError(
            "هذا الجزاء يتجاوز أجر يوم — يلزمه سماع أقوال الموظف "
            "وإثباتها في محضر قبل توقيعه")

    if p["kind"] == PenaltyKind.SUSPENSION:
        if Decimal(p["days"]) > MAX_SUSPENSION_DAYS_PER_MONTH:
            raise PenaltyError("الإيقاف لا يتجاوز خمسة أيام في الشهر")

    # المسؤول قد يوثّق بلا خصم — والمخالفة تبقى في صحيفته
    # وتُحتسب في التكرار.
    will_deduct = bool(apply_deduction) and p["deductible"]
    days = Decimal(p["days"]) if will_deduct else Decimal("0")
    amount = Decimal(p["amount"]) if will_deduct else Decimal("0")

    if (will_deduct and p["kind"] == PenaltyKind.WAGE_DEDUCTION
            and days <= 0):
        raise PenaltyError(
            "بلغ سقف الحسم الشهريّ (٥ أيام) — لا يُحسم أكثر هذا الشهر")

    pen = Penalty.objects.create(
        account=employment.account, company=employment.company,
        employment=employment, violation=violation,
        occurred_on=occurred_on, occurrence=p["occurrence"],
        kind=p["kind"], days=days, amount=amount,
        apply_deduction=will_deduct,
        count_occurrence=bool(count_occurrence),
        description=description.strip(),
        employee_statement=employee_statement.strip(),
        status=PenaltyStatus.ISSUED,
        issued_by_person_id=issued_by_person_id,
        issued_at=timezone.now())

    logger.info("جزاء %s على %s — %s", pen.id, employment.id, p["kind"])
    return pen


@transaction.atomic
def cancel(*, penalty, reason, by_person_id=None):
    """
    إلغاء الجزاء — لا حذفه.

    فالسجلّ التأديبيّ يُراجَع، ومحوُه يُخفي ما جرى. والملغى لا
    يُحتسب في التكرار ولا يُخصم.
    """
    if penalty.status == PenaltyStatus.CANCELLED:
        raise PenaltyError("ملغى أصلًا")
    if penalty.deducted_in_run_id:
        raise PenaltyError("خُصم في مسير — لا يُلغى، وتُعالج بتسوية")
    if not (reason or "").strip():
        raise PenaltyError("سبب الإلغاء مطلوب")

    penalty.status = PenaltyStatus.CANCELLED
    penalty.cancelled_reason = reason.strip()[:255]
    penalty.save(update_fields=["status", "cancelled_reason", "updated_at"])
    return penalty


# ══════════ سجلّ الجزاءات المقترحة (ق-121) ══════════
#
# **المسؤول لا يفتح شاشةً ليبحث عن مخالف** — النظام يعرض من
# تأخّر أو غاب أو لم يُتمّ حضوره، بحسم وقته محسوبًا، وزرُّ
# التطبيق بجانبه. فما لا يُعرض لا يُطبَّق.

def _daily_work_minutes(employment, day):
    """دقائق دوامه ذلك اليوم — من فترته لا رقمًا ثابتًا."""
    from datetime import datetime, timedelta as _td

    from apps.attendance.services.rules import effective_shift

    sh = effective_shift(employment, day)
    if sh is None or not sh.start_time or not sh.end_time:
        return 480
    start = datetime.combine(day, sh.start_time)
    end = datetime.combine(day, sh.end_time)
    if end <= start:
        end += _td(days=1)
    total = int((end - start).total_seconds() // 60)
    return max(total - int(sh.break_minutes or 0), 60)


def pending_board(company, start, end, employment_ids=None):
    """
    مخالفات الحضور التي لم يُوقَّع عليها جزاء — بحسم وقتها.

    ويُعرض معها **الحالة** (تأخير · غياب · حضور غير مكتمل) ومبلغ
    الحسم المحتسَب من الدقائق — فيقرّر المسؤول بضغطة.
    """
    from apps.attendance.models import AttendanceDay, DayStatus

    qs = (AttendanceDay.objects
          .filter(company=company, work_date__gte=start, work_date__lte=end)
          .exclude(status__in=[DayStatus.HOLIDAY, DayStatus.WEEKEND,
                               DayStatus.LEAVE, DayStatus.EXEMPT,
                               DayStatus.NOT_SCHEDULED])
          .select_related("employment__person"))
    if employment_ids:
        qs = qs.filter(employment_id__in=employment_ids)

    # ما وُقّع عليه جزاءٌ في يومه لا يُعرض ثانيةً
    signed = set(Penalty.objects.filter(
        company=company, occurred_on__gte=start, occurred_on__lte=end,
        status__in=[PenaltyStatus.ISSUED, PenaltyStatus.OBJECTED],
    ).values_list("employment_id", "occurred_on"))

    rows = []
    wage_cache = {}
    for d in qs.order_by("work_date", "employment__employee_no"):
        late = int(d.late_minutes or 0)
        early = int(getattr(d, "early_out_minutes", 0) or 0)
        absent = d.status == DayStatus.ABSENT
        if not (late or early or absent):
            continue
        if (d.employment_id, d.work_date) in signed:
            continue

        emp = d.employment
        if emp.id not in wage_cache:
            wage_cache[emp.id] = _monthly_wage(emp)
        monthly = wage_cache[emp.id]

        minutes = late + early
        if absent:
            amount = (Decimal(monthly) / Decimal("30")).quantize(
                Decimal("0.01"))
            state = "غياب"
        else:
            from apps.payroll.services.calculations import (
                calculate_late_deduction)
            amount = calculate_late_deduction(
                late_minutes=minutes, monthly_wage=monthly,
                daily_work_minutes=_daily_work_minutes(emp, d.work_date))
            state = "تأخير" if late and not early else (
                "انصراف مبكّر" if early and not late else "تأخير وانصراف")

        rows.append({
            "employment_id": emp.id,
            "employee_no": emp.employee_no,
            "name": emp.person.display_name,
            "date": d.work_date,
            "state": state,
            "attendance_status": d.get_status_display(),
            "late_minutes": late,
            "early_out_minutes": early,
            "minutes": minutes,
            "time_deduction": str(amount),
        })
    return rows


def _monthly_wage(employment):
    """أجره الشهريّ بأساس الغياب — مصدرٌ واحد للحسمين."""
    from apps.employees.models import SalaryStructure
    from apps.payroll.models import ComponentType

    st = (SalaryStructure.objects
          .filter(employment=employment, effective_to__isnull=True)
          .order_by("-effective_from").first())
    if st is None:
        return Decimal("0")
    total = Decimal("0")
    for comp, amount in st.as_lines():
        if (comp.component_type == ComponentType.EARNING
                and comp.is_absence_base):
            total += Decimal(amount)
    return total


# ══════════ سجلّ الجزاءات المقترحة (ق-121) ══════════
#
# **المسؤول لا يفتح شاشةً ليبحث عن مخالف** — النظام يعرض من
# تأخّر أو غاب أو لم يُتمّ حضوره، بحسم وقته محسوبًا، وزرُّ
# التطبيق بجانبه. فما لا يُعرض لا يُطبَّق.

def _monthly_wage(employment):
    """أجره الشهريّ بأساس الغياب — مصدرٌ واحد للحسمين."""
    from apps.employees.models import SalaryStructure
    from apps.payroll.models import ComponentType

    st = (SalaryStructure.objects
          .filter(employment=employment, effective_to__isnull=True)
          .order_by("-effective_from").first())
    if st is None:
        return Decimal("0")
    total = Decimal("0")
    for comp, amount in st.as_lines():
        if (comp.component_type == ComponentType.EARNING
                and comp.is_absence_base):
            total += Decimal(amount)
    return total


def pending_board(company, start, end, employment_ids=None):
    """
    مخالفات الحضور التي لم يُوقَّع عليها جزاء — بحسم وقتها.

    ويُعرض معها الحالة (تأخير · غياب · انصراف مبكّر) ومبلغ الحسم
    المحتسَب من الدقائق — فيقرّر المسؤول بضغطة.
    """
    from apps.attendance.models import AttendanceDay, DayStatus
    from apps.payroll.services.calculations import calculate_late_deduction

    qs = (AttendanceDay.objects
          .filter(company=company, work_date__gte=start, work_date__lte=end)
          .exclude(status__in=[DayStatus.HOLIDAY, DayStatus.WEEKEND,
                               DayStatus.LEAVE, DayStatus.EXEMPT,
                               DayStatus.NOT_SCHEDULED])
          .select_related("employment__person"))
    if employment_ids:
        qs = qs.filter(employment_id__in=employment_ids)

    # ما وُقّع عليه جزاءٌ في يومه لا يُعرض ثانيةً
    signed = set(Penalty.objects.filter(
        company=company, occurred_on__gte=start, occurred_on__lte=end,
        status__in=[PenaltyStatus.ISSUED, PenaltyStatus.OBJECTED],
    ).values_list("employment_id", "occurred_on"))

    rows = []
    wages = {}
    for d in qs.order_by("work_date", "employment__employee_no"):
        late = int(d.late_minutes or 0)
        early = int(getattr(d, "early_out_minutes", 0) or 0)
        absent = d.status == DayStatus.ABSENT
        if not (late or early or absent):
            continue
        if (d.employment_id, d.work_date) in signed:
            continue

        emp = d.employment
        if emp.id not in wages:
            wages[emp.id] = _monthly_wage(emp)
        monthly = wages[emp.id]

        minutes = late + early
        if absent:
            amount = (monthly / Decimal("30")).quantize(Decimal("0.01"))
            state = "غياب"
        else:
            amount = calculate_late_deduction(
                late_minutes=minutes, monthly_wage=monthly)
            state = ("تأخير" if late and not early
                     else "انصراف مبكّر" if early and not late
                     else "تأخير وانصراف مبكّر")

        rows.append({
            "employment_id": emp.id,
            "employee_no": emp.employee_no,
            "name": emp.person.display_name,
            "date": d.work_date,
            "state": state,
            "attendance_status": d.get_status_display(),
            "late_minutes": late,
            "early_out_minutes": early,
            "minutes": minutes,
            "time_deduction": str(amount),
        })
    return rows


@transaction.atomic
def issue_batch(*, company, rows, violation=None, apply_deduction=True,
                count_occurrence=True, issued_by_person_id=None,
                employee_statement=""):
    """
    توقيع جماعيّ على صفوف السجلّ (ق-121).

    فمن راجع سجلّ الشهر لا يفتح نافذةً لكل صفّ — والمرجع يتيح
    «تطبيق جميع الجزاءات في سجل البحث».

    وما تعذّر توقيعه لا يُسقط الباقي: يُجمع في `failed` برسالته،
    فيرى المسؤول ما مرّ وما لم يمرّ.
    """
    from apps.employees.models import Employment

    done, failed = [], []
    for r in rows:
        emp = Employment.objects.filter(
            id=r.get("employment_id"), company=company).first()
        if emp is None:
            failed.append({"row": r, "detail": "الموظف غير موجود"})
            continue

        v = violation or _auto_violation(company, r)
        if v is None:
            failed.append({"row": r,
                           "detail": "لا بند في اللائحة يطابق الحالة"})
            continue

        try:
            pen = issue(
                employment=emp, violation=v,
                occurred_on=r["date"],
                description=r.get("description")
                or f"{r.get('state', '')} — {r.get('minutes', 0)} دقيقة",
                employee_statement=employee_statement,
                issued_by_person_id=issued_by_person_id,
                apply_deduction=apply_deduction,
                count_occurrence=count_occurrence)
            done.append(pen.id)
        except PenaltyError as e:
            failed.append({"row": r, "detail": str(e)})

    return {"issued": len(done), "ids": done, "failed": failed}


# ربط حالة الحضور ببند اللائحة — بالرمز لا بالاسم، فالأسماء
# تُعدَّل والرموز تبقى. والشركة التي حذفت البند لا يُوقَّع لها
# تلقائيًّا، وتختاره يدويًّا.
STATE_TO_CODE = {
    "غياب": "ABSENT-1",
    "انصراف مبكّر": "EARLY-OUT",
}


def _auto_violation(company, row):
    """بند اللائحة المطابق لحالة الصفّ — أو None."""
    state = row.get("state", "")
    code = STATE_TO_CODE.get(state)
    if code is None and "تأخير" in state:
        # التأخير بحسب مدّته: حتى ١٥ دقيقة بندٌ، وما فوقها آخر
        code = "LATE-15" if int(row.get("minutes") or 0) <= 15 else "LATE-30"
    if code is None:
        return None
    return ViolationType.objects.filter(
        company=company, code=code, is_active=True).first()
