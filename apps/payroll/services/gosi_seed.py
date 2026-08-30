"""
بذرة أنظمة ونسب التأمينات.

⚠️ تحذير إلزامي: هذه النسب بذرة أولية للتصميم والاختبار. المرجع
الملزم قبل الإطلاق هو المؤسسة العامة للتأمينات الاجتماعية.
النظام مصمَّم لتُحدَّث هذه القيم كبيانات لا ككود — وهذه هي الحماية
الحقيقية من تغيّر الأنظمة (ق-19/1).

الأهم في التصميم: النظامان يعملان بالتوازي بعد إصلاح يوليو 2024،
والنظام التأميني صفة في الشخص لا الوظيفة (ق-16).
"""
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.payroll.models import GosiRate, GosiScheme

SCHEMES = {
    "traditional": {
        "name_ar": "النظام التقليدي",
        "description_ar": "لمن له مدد اشتراك قبل 3 يوليو 2024",
    },
    "new_scheme": {
        "name_ar": "النظام الجديد (المتدرّج)",
        "description_ar": "للمنضمّين بعد 3 يوليو 2024 دون سن 50 — "
                          "النسبة تتدرّج تصاعديًا",
    },
    "non_saudi": {
        "name_ar": "غير سعودي",
        "description_ar": "أخطار مهنية على صاحب العمل فقط — "
                          "لا يُخصم من الوافد شيء إطلاقًا",
    },
}

D = Decimal
MIN_WAGE = D("1500.00")
MAX_WAGE = D("45000.00")

# (النظام, سريان من, معاشات موظف, معاشات صاحب عمل,
#  ساند موظف, ساند صاحب عمل, أخطار صاحب عمل)
RATES = [
    ("traditional", date(2000, 1, 1),
     D("0.0900"), D("0.0900"), D("0.0075"), D("0.0075"), D("0.0200")),

    # النظام الجديد: تدرّج 0.5% سنويًا من 2025
    ("new_scheme", date(2024, 7, 3),
     D("0.0900"), D("0.0900"), D("0.0075"), D("0.0075"), D("0.0200")),
    ("new_scheme", date(2025, 7, 1),
     D("0.0950"), D("0.0950"), D("0.0075"), D("0.0075"), D("0.0200")),
    ("new_scheme", date(2026, 7, 1),
     D("0.1000"), D("0.1000"), D("0.0075"), D("0.0075"), D("0.0200")),
    ("new_scheme", date(2027, 7, 1),
     D("0.1050"), D("0.1050"), D("0.0075"), D("0.0075"), D("0.0200")),
    ("new_scheme", date(2028, 7, 1),
     D("0.1100"), D("0.1100"), D("0.0075"), D("0.0075"), D("0.0200")),

    # غير سعودي: صفر على الموظف — أشيع خطأ في أنظمة السوق
    ("non_saudi", date(2000, 1, 1),
     D("0"), D("0"), D("0"), D("0"), D("0.0200")),
]

SOURCE_NOTE = "بذرة أولية — تحتاج تأكيدًا من المؤسسة العامة للتأمينات"


@transaction.atomic
def sync_gosi_rates():
    """يزامن الأنظمة والنسب. آمن للتكرار."""
    for code, spec in SCHEMES.items():
        GosiScheme.objects.update_or_create(code=code, defaults=spec)

    for (code, eff, emp_p, er_p, emp_s, er_s, er_h) in RATES:
        scheme = GosiScheme.objects.get(code=code)
        GosiRate.objects.update_or_create(
            scheme=scheme, effective_from=eff,
            defaults={
                "employee_pension_rate": emp_p,
                "employer_pension_rate": er_p,
                "employee_saned_rate": emp_s,
                "employer_saned_rate": er_s,
                "employer_hazards_rate": er_h,
                "min_subject_wage": MIN_WAGE,
                "max_subject_wage": MAX_WAGE,
                "source_note": SOURCE_NOTE,
            },
        )
    return {"schemes": GosiScheme.objects.count(),
            "rates": GosiRate.objects.count()}


def get_effective_rate(scheme_code: str, as_of: date):
    """
    النسبة السارية بتاريخ الاستحقاق — لا تاريخ اليوم.

    هذا ما يجعل إعادة احتساب مسير قديم تعطي نفس الأرقام دائمًا.
    """
    return (GosiRate.objects
            .filter(scheme__code=scheme_code, effective_from__lte=as_of)
            .order_by("-effective_from").first())
