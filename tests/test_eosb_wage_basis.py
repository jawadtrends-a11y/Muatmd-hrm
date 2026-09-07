"""
حرّاس أساس أجر المكافأة (ق-97).

ما تمنعه:
  • احتساب بدل لم تختره الشركة — فالمكافأة مال لا يُخمَّن
  • دخول الخصومات في الأجر
  • تشغيل مسير مستحقات بلا اختيار صريح
"""
from decimal import Decimal

import pytest

from apps.payroll.models import ComponentType
from apps.payroll.services.components import eosb_wage
from apps.payroll.services.eosb import EOSBBasisNotSet


class _Comp:
    """مكوّن مبسّط — الاحتساب يقرأ الرمز والنوع والعلم وحدها."""

    def __init__(self, code, ctype=ComponentType.EARNING, eosb=False):
        self.code = code
        self.component_type = ctype
        self.is_eosb_subject = eosb


LINES = [
    (_Comp("BASIC", eosb=True), Decimal("6000")),
    (_Comp("HOUSING"), Decimal("1500")),
    (_Comp("TRANSPORT"), Decimal("500")),
    (_Comp("PHONE"), Decimal("200")),
    (_Comp("ABSENCE", ComponentType.DEDUCTION), Decimal("300")),
]


def test_basic_only():
    """الأساسي وحده — ولا بدل معه."""
    assert eosb_wage(LINES, "basic_only") == Decimal("6000")


def test_basic_plus_housing():
    """
    ⚠️ الأساسي والسكن — ولا مواصلات ولا غيرها.

    فمن اختار السكن وحده لا يُحتسب عليه ما لم يختره: المكافأة
    مال يُدفع مرة، وزيادتها بلا قرار خطأ لا يُكتشف.
    """
    assert eosb_wage(LINES, "basic_housing") == Decimal("7500")


def test_basic_housing_transport():
    """الأساسي والسكن والمواصلات — ولا بدل رابع."""
    assert eosb_wage(LINES, "basic_housing_transport") == Decimal("8000")


def test_basic_all_allowances():
    """
    ⚠️ جميع البدلات — والخصومات ليست بدلات.

    فإدخال خصم الغياب في أجر المكافأة يزيدها أو ينقصها بلا وجه.
    """
    assert eosb_wage(LINES, "basic_all") == Decimal("8200")


def test_not_set_raises():
    """
    ⚠️ الصمت ليس اختيارًا.

    فمن لم تحدّد شركته الأساس لا يُحتسب له بافتراضٍ منّا — والخطأ
    يوقف المسير حتى تقرّر.
    """
    with pytest.raises(EOSBBasisNotSet):
        eosb_wage(LINES, "not_set")


def test_deduction_never_counted():
    """⚠️ الخصم لا يدخل أي أساس مهما كان."""
    for basis in ("basic_only", "basic_housing",
                  "basic_housing_transport", "basic_all"):
        assert eosb_wage(LINES, basis) < Decimal("8500"), basis
