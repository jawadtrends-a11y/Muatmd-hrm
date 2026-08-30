"""
بذرة مكوّنات الأجر الافتراضية.

المبدأ الحاكم (ق-9 و ق-20): النظام يقترح ولا يفرض. المكوّنات
الثلاثة الأولى شائعة في السوق السعودي، والشركة تعدّلها وتضيف
وتحذف بحرية كاملة.

الأعلام الأربعة هي جوهر النظام — كل خلاف عمّالي تقريبًا ينشأ من
سؤال «هل هذا البدل يدخل في نهاية الخدمة؟». نجعلها إعدادًا صريحًا
يراه العميل ويوقّع عليه لا افتراضًا مخفيًا.
"""
from django.db import transaction

from apps.payroll.models import ComponentType, PayComponent

# الأعلام: (خاضع للتأمينات، نهاية الخدمة، أساس الإضافي، حماية الأجور)
#
# ⚠️ is_eosb_subject يبدأ False في كل المكوّنات عدا الأساسي —
# قرار المالك (ق-21): أجر المكافأة «حسب العقد»، والشركة تحدد.
DEFAULT_COMPONENTS = [
    {
        "code": "BASIC", "name_ar": "الراتب الأساسي",
        "name_en": "Basic Salary", "name_ur": "بنیادی تنخواہ",
        "type": ComponentType.EARNING,
        "is_gosi_subject": True,      # الأساسي خاضع دائمًا
        "is_eosb_subject": True,      # ولا خلاف على دخوله في المكافأة
        "is_overtime_base": True,
        "is_wps_subject": True,
        "is_system": True,            # لا يُحذف
        "order": 10,
    },
    {
        "code": "HOUSING", "name_ar": "بدل السكن",
        "name_en": "Housing Allowance", "name_ur": "رہائشی الاؤنس",
        "type": ComponentType.EARNING,
        "is_gosi_subject": True,      # ق: الأساسي + السكن خاضعان
        "is_eosb_subject": False,     # حسب العقد — الشركة تحدد
        "is_overtime_base": False,
        "is_wps_subject": True,
        "is_system": False,
        "order": 20,
    },
    {
        "code": "TRANSPORT", "name_ar": "بدل النقل",
        "name_en": "Transportation Allowance", "name_ur": "ٹرانسپورٹ الاؤنس",
        "type": ComponentType.EARNING,
        "is_gosi_subject": False,     # لا يخضع للتأمينات
        "is_eosb_subject": False,     # حسب العقد
        "is_overtime_base": False,
        "is_wps_subject": True,
        "is_system": False,
        "order": 30,
    },
    # ── استقطاعات نظامية ──
    {
        "code": "ABSENCE", "name_ar": "خصم غياب",
        "name_en": "Absence Deduction", "name_ur": "غیر حاضری کٹوتی",
        "type": ComponentType.DEDUCTION,
        "is_gosi_subject": False, "is_eosb_subject": False,
        "is_overtime_base": False, "is_wps_subject": False,
        "is_system": True, "order": 100,
    },
    {
        "code": "LATE", "name_ar": "خصم تأخير",
        "name_en": "Late Deduction", "name_ur": "تاخیر کٹوتی",
        "type": ComponentType.DEDUCTION,
        "is_gosi_subject": False, "is_eosb_subject": False,
        "is_overtime_base": False, "is_wps_subject": False,
        "is_system": True, "order": 110,
    },
    {
        "code": "OVERTIME", "name_ar": "العمل الإضافي",
        "name_en": "Overtime", "name_ur": "اضافی کام",
        "type": ComponentType.EARNING,
        "is_gosi_subject": False,     # الإضافي لا يخضع للتأمينات
        "is_eosb_subject": False,     # ولا يدخل نهاية الخدمة
        "is_overtime_base": False,
        "is_wps_subject": True,
        "is_system": True, "order": 40,
    },
]


class ComponentError(Exception):
    pass


@transaction.atomic
def provision_default_components(company):
    """
    ينشئ المكوّنات الافتراضية لشركة جديدة. آمن للتكرار.
    الشركة تعدّلها وتضيف وتحذف بعدها بحرية (ق-9).
    """
    created = []
    for spec in DEFAULT_COMPONENTS:
        comp, is_new = PayComponent.objects.get_or_create(
            company=company, code=spec["code"],
            defaults={
                "account": company.account,
                "name_ar": spec["name_ar"],
                "name_en": spec["name_en"],
                "name_ur": spec["name_ur"],
                "component_type": spec["type"],
                "is_gosi_subject": spec["is_gosi_subject"],
                "is_eosb_subject": spec["is_eosb_subject"],
                "is_overtime_base": spec["is_overtime_base"],
                "is_wps_subject": spec["is_wps_subject"],
                "is_system": spec["is_system"],
                "display_order": spec["order"],
            },
        )
        if is_new:
            created.append(spec["code"])
    return created


@transaction.atomic
def set_component_flags(component, *, is_gosi_subject=None,
                        is_eosb_subject=None, is_overtime_base=None,
                        is_wps_subject=None):
    """
    يعدّل أعلام مكوّن ويُرجع التحذيرات (ق-23).

    النظام لا يمنع الاستثناء، لكنه ينبّه: القضاء العمالي يعتبر
    البدل الثابت المنتظم جزءًا من الأجر المحتسب ولو سُمّي مؤقتًا.
    """
    from apps.payroll.services.eosb import warn_on_component_exclusion

    warnings = []
    changes = {
        "is_gosi_subject": is_gosi_subject,
        "is_eosb_subject": is_eosb_subject,
        "is_overtime_base": is_overtime_base,
        "is_wps_subject": is_wps_subject,
    }
    for flag, new_value in changes.items():
        if new_value is None:
            continue
        old_value = getattr(component, flag)
        if old_value and not new_value:      # إطفاء علم
            warnings.append(warn_on_component_exclusion(
                component.name_ar, flag))
        setattr(component, flag, new_value)

    component.save()
    return warnings


def gosi_subject_wage(salary_lines):
    """
    الأجر الخاضع للتأمينات = مجموع المكوّنات المعلّمة is_gosi_subject.
    salary_lines: [(component, amount), ...]
    """
    from decimal import Decimal
    return sum(
        (amount for comp, amount in salary_lines
         if comp.is_gosi_subject and comp.component_type == ComponentType.EARNING),
        Decimal("0"),
    )


def eosb_wage(salary_lines, basis="flagged"):
    """
    أجر مكافأة نهاية الخدمة (ق-21).

    basis:
      • not_set    → يرفع خطأً: الشركة لم تحدد بعد
      • basic_only → الأساسي وحده
      • flagged    → حسب أعلام المكوّنات
    """
    from decimal import Decimal
    from apps.payroll.services.eosb import EOSBBasisNotSet

    if basis == "not_set":
        raise EOSBBasisNotSet(
            "يجب تحديد ما يدخل في أجر المكافأة قبل أول مسير مستحقات"
        )
    if basis == "basic_only":
        return sum(
            (amount for comp, amount in salary_lines if comp.code == "BASIC"),
            Decimal("0"),
        )
    return sum(
        (amount for comp, amount in salary_lines
         if comp.is_eosb_subject and comp.component_type == ComponentType.EARNING),
        Decimal("0"),
    )


def overtime_base_wage(salary_lines):
    """أساس احتساب العمل الإضافي = المكوّنات المعلّمة is_overtime_base."""
    from decimal import Decimal
    return sum(
        (amount for comp, amount in salary_lines
         if comp.is_overtime_base and comp.component_type == ComponentType.EARNING),
        Decimal("0"),
    )
