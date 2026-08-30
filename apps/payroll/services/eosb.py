"""
مكافأة نهاية الخدمة — المواد 84 و85 و87 من نظام العمل السعودي.

⚠️ أخطر دالة في النظام: تمسّ حقوقًا مالية وتُسأل عنها في النزاعات.
لا يُعتمد أي تعديل فيها قبل اجتياز مصفوفة الاختبارات كاملة.

الأساس (ق-22): السنة 360 يومًا والشهر 30.
الأجر: حسب العقد (ق-21) — الشركة تحدد ما يدخل عبر أعلام المكوّنات.

⚠️ المرجع الملزم: هيئة الخبراء بمجلس الوزراء ومنصة قوى. القيم هنا
مبنية على تعديلات فبراير 2025 (1446هـ) وتحتاج مراجعة قبل الإطلاق.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

DAYS_PER_YEAR = Decimal("360")      # ق-22
TWO = Decimal("0.01")


def r2(v) -> Decimal:
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


class EOSBError(Exception):
    pass


class EOSBBasisNotSet(EOSBError):
    """أساس أجر المكافأة لم تحدده الشركة — الصمت قرار مالي لم يُتخذ."""


# ══════════ حالات انتهاء العلاقة العمالية ══════════
# كل حالة نظامية مذكورة صراحةً — لا حالة مجهولة (طلب المالك).

FULL_ENTITLEMENT = {
    # المادة 74 — حالات الانتهاء المشروع
    "mutual_agreement":     "اتفاق الطرفين كتابةً (م/74)",
    "contract_expiry":      "انتهاء مدة العقد المحدد (م/74)",
    "employer_termination": "إنهاء من صاحب العمل (م/74 و75)",
    "retirement":           "بلوغ سن التقاعد النظامي (م/74)",
    "force_majeure":        "قوة قاهرة تجعل التنفيذ مستحيلًا (م/74)",
    "establishment_closure":"إغلاق المنشأة نهائيًا (م/74)",
    "activity_termination": "إنهاء النشاط الذي يعمل به العامل (م/74)",
    "death":                "وفاة العامل (م/74) — تُصرف للورثة",
    "bankruptcy":           "إفلاس صاحب العمل (نظام الإفلاس)",
    # المادة 81 — ترك العامل العمل لإخلال صاحب العمل
    "employer_breach":      "ترك العمل لإخلال صاحب العمل (م/81)",
    # المادة 87 — استثناءات المرأة
    "female_marriage":      "استقالة المرأة خلال 6 أشهر من الزواج (م/87)",
    "female_childbirth":    "استقالة المرأة خلال 3 أشهر من الوضع (م/87)",
}

NO_ENTITLEMENT = {
    "article_80":  "الفصل بموجب المادة 80 — بلا مكافأة ولا إشعار",
    "probation":   "الإنهاء خلال فترة التجربة (م/53)",
}

PRORATED_ENTITLEMENT = {
    "resignation": "الاستقالة (م/85) — النسبة حسب مدة الخدمة",
}

ALL_REASONS = {**FULL_ENTITLEMENT, **NO_ENTITLEMENT, **PRORATED_ENTITLEMENT}


@dataclass(frozen=True)
class EOSBResult:
    service_days: int
    service_years: Decimal
    eosb_wage: Decimal
    gross_award: Decimal          # قبل نسبة الاستحقاق
    entitlement_ratio: Decimal
    net_award: Decimal
    reason_code: str
    reason_label: str
    explanation: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def service_days_360(start: date, end: date) -> int:
    """
    مدة الخدمة بأساس 360 يومًا (ق-22).

    الطريقة المعتمدة (المثال الرسمي): تُفكَّك المدة إلى سنوات كاملة
    وشهور وأيام، ثم:
        (السنوات × 360) + (الشهور × 30) + الأيام

    لا تُحسب الأيام الفعلية بين التاريخين مقسومة على 360 — تلك تعطي
    7.10 سنة لسبع سنوات ميلادية، وهو خطأ يتراكم مع طول الخدمة.
    """
    years = end.year - start.year
    months = end.month - start.month
    days = end.day - start.day

    if days < 0:
        months -= 1
        days += 30          # الشهر 30 يومًا (ق-22)
    if months < 0:
        years -= 1
        months += 12

    return (years * 360) + (months * 30) + days


def resignation_ratio(years: Decimal) -> Decimal:
    """
    المادة 85: أقل من سنتين لا شيء، ومن سنتين لخمس الثلث،
    ومن خمس لعشر الثلثان، وعشر فأكثر كاملة.
    """
    if years < 2:
        return Decimal("0")
    if years < 5:
        return Decimal("1") / Decimal("3")
    if years < 10:
        return Decimal("2") / Decimal("3")
    return Decimal("1")


def calculate_eosb(*, join_date: date, end_date: date,
                   eosb_wage: Decimal, reason_code: str,
                   unpaid_leave_days: int = 0,
                   exclude_unpaid_leave: bool = False,
                   wage_basis_set: bool = True) -> EOSBResult:
    """
    مكافأة نهاية الخدمة.

    join_date: بداية الخدمة المحتسبة (service_start_date عند النقل
               باستمرارية الخدمة — ق-14)
    eosb_wage: الأجر المعتمد حسب العقد (ق-21)
    reason_code: حالة نظامية مذكورة صراحةً — لا مجهول
    """
    if not wage_basis_set:
        raise EOSBBasisNotSet(
            "يجب تحديد ما يدخل في أجر المكافأة قبل أول مسير مستحقات"
        )
    if reason_code not in ALL_REASONS:
        raise EOSBError(
            f"سبب انتهاء غير نظامي: {reason_code}. "
            f"الحالات المتاحة: {sorted(ALL_REASONS)}"
        )
    if end_date <= join_date:
        raise EOSBError("تاريخ انتهاء الخدمة يجب أن يلي تاريخ بداية الخدمة")

    warnings = []

    # ── مدة الخدمة (ق-22: السنة 360 يومًا) ──
    raw_days = service_days_360(join_date, end_date)
    excluded = unpaid_leave_days if exclude_unpaid_leave else 0
    if excluded:
        warnings.append(
            f"استُبعد {excluded} يومًا من الإجازات بلا أجر من مدة الخدمة "
            "(إعداد الشركة)"
        )
    service_days = raw_days - excluded
    years = Decimal(service_days) / DAYS_PER_YEAR

    # ── المكافأة الأساسية (م/84) ──
    first_block = min(years, Decimal("5"))
    second_block = max(Decimal("0"), years - Decimal("5"))
    first_amount = eosb_wage * first_block * Decimal("0.5")
    second_amount = eosb_wage * second_block
    gross = first_amount + second_amount

    # ── نسبة الاستحقاق ──
    if reason_code in NO_ENTITLEMENT:
        ratio = Decimal("0")
    elif reason_code in FULL_ENTITLEMENT:
        ratio = Decimal("1")
    else:
        ratio = resignation_ratio(years)

    explanation = [
        f"سبب انتهاء الخدمة: {ALL_REASONS[reason_code]}",
        f"مدة الخدمة: {service_days} يومًا "
        f"({r2(years)} سنة على أساس 360 يومًا للسنة)",
        f"الأجر المعتمد للمكافأة: {r2(eosb_wage)} ريال",
        f"أول 5 سنوات: {r2(first_block)} سنة × نصف شهر = "
        f"{r2(first_amount)} ريال",
        f"ما بعد 5 سنوات: {r2(second_block)} سنة × شهر كامل = "
        f"{r2(second_amount)} ريال",
        f"إجمالي المكافأة قبل النسبة: {r2(gross)} ريال",
        f"نسبة الاستحقاق: {r2(ratio * 100)}%",
        f"صافي المكافأة: {r2(gross * ratio)} ريال",
    ]

    return EOSBResult(
        service_days=service_days,
        service_years=r2(years),
        eosb_wage=r2(eosb_wage),
        gross_award=r2(gross),
        entitlement_ratio=ratio,
        net_award=r2(gross * ratio),
        reason_code=reason_code,
        reason_label=ALL_REASONS[reason_code],
        explanation=explanation,
        warnings=warnings,
    )


def warn_on_component_exclusion(component_name: str, flag_name: str) -> str:
    """
    تحذير عند استثناء بدل من أي احتساب (ق-23).

    النظام لا يمنع، لكنه ينبّه: القضاء العمالي يعتبر البدل الثابت
    المنتظم جزءًا من الأجر المحتسب ولو سُمّي مؤقتًا.
    """
    labels = {
        "is_eosb_subject": "مكافأة نهاية الخدمة",
        "is_gosi_subject": "الأجر الخاضع للتأمينات",
        "is_overtime_base": "أساس العمل الإضافي",
        "is_wps_subject": "ملف حماية الأجور",
    }
    target = labels.get(flag_name, flag_name)
    return (
        f"تنبيه: استثنيتم «{component_name}» من {target}. "
        "القضاء العمالي يعتبر البدل الثابت المنتظم جزءًا من الأجر "
        "المحتسب ولو سُمّي بدلًا مؤقتًا. راجعوا العقود قبل الاعتماد."
    )
