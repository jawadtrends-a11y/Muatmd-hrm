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
# المرجع الحكومي: قائمة «سبب إنهاء علاقة العمل» في حاسبة مكافأة
# نهاية الخدمة الرسمية بوزارة الموارد البشرية والتنمية الاجتماعية
# hrsd.gov.sa/ministry-services/services/end-service-benefit-calculator
#
# القائمة معتمدة حرفيًا (ق-26). لا حالة خارجها ولا حالة مجهولة.

FULL_ENTITLEMENT = {
    "contract_expiry":       "انتهاء مدة العقد",
    "unlawful_termination":  "إنهاء صاحب العمل للعقد لسبب غير مشروع",
    "force_majeure":         "انتهاء العقد بسبب القوة القاهرة",
    "female_childbirth":     "إنهاء العاملة للعقد خلال إجازة الوضع "
                             "البالغة ثلاثة أشهر",
    "female_marriage":       "إنهاء العاملة للعقد خلال ستة أشهر من "
                             "تاريخ عقد الزواج",
    "article_81":            "إنهاء العقد وفقًا للمادة (81)",
    "mutual_agreement":      "الاتفاق على الإنهاء",
    "worker_disability":     "عجز العامل",
    "employer_death":        "وفاة صاحب العمل",
    "worker_death":          "وفاة العامل",
    "ownership_transfer":    "نقل ملكية المنشأة الفردية إلى مالك جديد",
    "retirement":            "بلوغ سن التقاعد",
    "notice_article_75":     "إشعار إنهاء الخدمة وفقًا للمادة (75)",
}

NO_ENTITLEMENT = {
    "article_80":  "إنهاء العقد وفقًا للمادة (80)",
    "probation":   "الإنهاء خلال فترة التجربة",
}

PRORATED_ENTITLEMENT = {
    "resignation": "استقالة",
}

ALL_REASONS = {**FULL_ENTITLEMENT, **NO_ENTITLEMENT, **PRORATED_ENTITLEMENT}

# الحالة الوحيدة التي تستوجب تعويضًا إضافيًا (م/77) فوق المكافأة
UNLAWFUL_TERMINATION_CODE = "unlawful_termination"


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
    # ق-25: لا تقريب في المنتصف — الكسر يُحتفظ به كاملًا والتقريب
    # في النتيجة النهائية فقط. مطابق للحاسبة الرسمية لوزارة الموارد
    # البشرية (hrsd.gov.sa): 4س6ش15ي على 3000 = 6812.50 ريال.
    half_day_rate = eosb_wage / Decimal("2") / DAYS_PER_YEAR
    full_day_rate = eosb_wage / DAYS_PER_YEAR

    first_days = min(service_days, 5 * 360)
    second_days = max(0, service_days - (5 * 360))

    first_amount = half_day_rate * Decimal(first_days)
    second_amount = full_day_rate * Decimal(second_days)
    gross = first_amount + second_amount

    first_block = Decimal(first_days) / DAYS_PER_YEAR
    second_block = Decimal(second_days) / DAYS_PER_YEAR

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
        f"أجر اليوم للخمس الأولى (نصف شهر): {r2(half_day_rate)} ريال",
        f"أول 5 سنوات: {first_days} يومًا × {r2(half_day_rate)} = "
        f"{r2(first_amount)} ريال",
        f"أجر اليوم لما بعدها (شهر كامل): {r2(full_day_rate)} ريال",
        f"ما بعد 5 سنوات: {second_days} يومًا × {r2(full_day_rate)} = "
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


# ══════════ تعويض الإنهاء غير المشروع (المادة 77) ══════════

@dataclass(frozen=True)
class UnlawfulTerminationCompensation:
    """
    تعويض المادة 77 — بند مستقل عن المكافأة (ق-26).

    يظهر في مسير المستحقات سطرًا منفصلًا، لأن طبيعته تعويض عن ضرر
    لا مكافأة عن مدة خدمة.
    """
    contract_type: str
    months_equivalent: Decimal
    amount: Decimal
    minimum_applied: bool
    explanation: list = field(default_factory=list)


def calculate_unlawful_termination_compensation(
    *, monthly_wage: Decimal, service_days: int,
    contract_type: str = "indefinite",
    remaining_contract_months: Decimal | None = None,
    agreed_amount: Decimal | None = None,
) -> UnlawfulTerminationCompensation:
    """
    تعويض الإنهاء لسبب غير مشروع (م/77).

    نص المادة يبدأ بـ«ما لم يكن في العقد نص على تعويض» — فالاتفاق
    يسبق الحد النظامي. لذلك (ق-27):

      • agreed_amount: المبلغ الذي تُدخله الشركة يدويًا من العقد أو
        من حكم قضائي. يُعتمد كما هو.
      • عند غيابه: يُحتسب الحد النظامي كمرجع —
        غير محدد المدة: أجر 15 يومًا عن كل سنة، بحد أدنى أجر شهرين.
        محدد المدة: أجر المدة المتبقية.

    التحذير عند نزول المُدخل عن الحد النظامي، بلا منع (ق-20).

    ⚠️ يُصرف بالإضافة إلى مكافأة نهاية الخدمة لا بدلًا عنها.
    """
    # ── المبلغ المتفق عليه يسبق الحد النظامي (م/77) ──
    if agreed_amount is not None:
        agreed = Decimal(agreed_amount)
        statutory_min = monthly_wage * Decimal("2")
        expl = [
            "تعويض الإنهاء غير المشروع (م/77) — مبلغ متفق عليه",
            f"المبلغ المُدخل: {r2(agreed)} ريال",
            f"الحد النظامي الأدنى (أجر شهرين): {r2(statutory_min)} ريال",
        ]
        if agreed < statutory_min:
            expl.append(
                "⚠️ تنبيه: المبلغ المُدخل أقل من الحد النظامي الأدنى. "
                "راجعوا نص العقد قبل الاعتماد."
            )
        return UnlawfulTerminationCompensation(
            contract_type=contract_type,
            months_equivalent=r2(agreed / monthly_wage) if monthly_wage else Decimal("0"),
            amount=r2(agreed),
            minimum_applied=False,
            explanation=expl,
        )

    if contract_type == "fixed_term":
        if remaining_contract_months is None:
            raise EOSBError(
                "العقد محدد المدة يتطلب عدد الأشهر المتبقية لاحتساب "
                "تعويض المادة 77"
            )
        months = Decimal(remaining_contract_months)
        amount = monthly_wage * months
        return UnlawfulTerminationCompensation(
            contract_type=contract_type,
            months_equivalent=r2(months),
            amount=r2(amount),
            minimum_applied=False,
            explanation=[
                "تعويض الإنهاء غير المشروع (م/77) — عقد محدد المدة",
                f"المدة المتبقية من العقد: {r2(months)} شهرًا",
                f"التعويض: {r2(months)} × {r2(monthly_wage)} = {r2(amount)} ريال",
            ],
        )

    # غير محدد المدة: 15 يومًا عن كل سنة، بحد أدنى شهران
    years = Decimal(service_days) / DAYS_PER_YEAR
    half_month_rate = monthly_wage / Decimal("2")
    computed = half_month_rate * years
    minimum = monthly_wage * Decimal("2")
    minimum_applied = computed < minimum
    amount = max(computed, minimum)

    explanation = [
        "تعويض الإنهاء غير المشروع (م/77) — عقد غير محدد المدة",
        f"مدة الخدمة: {service_days} يومًا ({r2(years)} سنة)",
        f"أجر 15 يومًا عن كل سنة: {r2(half_month_rate)} × {r2(years)} "
        f"= {r2(computed)} ريال",
        f"الحد الأدنى (أجر شهرين): {r2(minimum)} ريال",
    ]
    if minimum_applied:
        explanation.append("طُبِّق الحد الأدنى لأنه أعلى من المحتسب")
    explanation.append(f"التعويض المستحق: {r2(amount)} ريال")

    return UnlawfulTerminationCompensation(
        contract_type="indefinite",
        months_equivalent=r2(amount / monthly_wage),
        amount=r2(amount),
        minimum_applied=minimum_applied,
        explanation=explanation,
    )


# ══════════ من يبادر بالإنهاء ومدة إشعاره (ق-60) ══════════
# (المُبادِر، مدة الإشعار بالأيام — None يعني بالاتفاق)

TERMINATION_INITIATOR = {
    # ── يبادر بها الموظف ──
    "resignation":          ("employee", 30),
    "article_81":           ("employee", 0),
    "probation":            ("employee", 0),
    "female_marriage":      ("employee", 0),
    "female_childbirth":    ("employee", 0),
    "retirement":           ("employee", 0),
    "worker_disability":    ("employee", 0),

    # ── تبادر بها الشركة ──
    "notice_article_75":    ("employer", 60),
    "article_80":           ("employer", 0),
    "unlawful_termination": ("employer", 0),
    "contract_expiry":      ("employer", 0),
    "force_majeure":        ("employer", 0),
    "ownership_transfer":   ("employer", 0),
    "worker_death":         ("employer", 0),
    "employer_death":       ("employer", 0),

    # الاتفاق يقع بين الطرفين، لكن الشركة توثّقه (ق-60)
    "mutual_agreement":     ("employer", None),
}


def notice_days_for(reason_code):
    """
    مدة الإشعار النظامية للسبب — بالأيام.

    None تعني «بالاتفاق»، و0 تعني «لا إشعار».
    """
    entry = TERMINATION_INITIATOR.get(reason_code)
    return entry[1] if entry else 0


def reasons_for_initiator(initiator):
    """أسباب الإنهاء التي يبادر بها هذا الطرف (ق-60)."""
    return [code for code, (who, _days) in TERMINATION_INITIATOR.items()
            if who == initiator]
