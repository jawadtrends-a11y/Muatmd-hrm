"""
حارس رؤية القسيمة (ق-239).

⚠️⚠️ **وقسيمة المشرف كانت تختفي عنه**: بـview_team يُصفَّى بقسائم **فريقه** —
**وهو ليس في فريقه**. فالقائمة تعرضها والتفاصيل تقول «غير موجودة».
**وكلّما كبرت صلاحيّته ضاق ما يراه لنفسه** — انقلابٌ في المنطق.
"""
import re
from pathlib import Path


def test_own_payslip_is_always_visible():
    """⚠️⚠️ الأهمّ: **كل فرعٍ يضمّ قسيمته هو** (`| own`) — لا أحدهما."""
    src = Path("apps/payroll/api_outputs.py").read_text(encoding="utf-8")
    body = src[src.index("def payslip_detail"):][:1800]
    branches = re.findall(r'Gate\.filter_queryset\(request\.user, "payslips\.view_\w+", qs\)[^\n]*', body)
    assert branches, "لم يُعثر على فروع الصلاحية"
    missing = [b for b in branches if "| own" not in b]
    assert not missing, "فرعٌ لا يضمّ قسيمة صاحبها:\n" + "\n".join(missing)


def test_list_and_detail_use_same_ownership_rule():
    """
    ⚠️ **ولا تعرض القائمة ما ترفضه التفاصيل**: كلتاهما تعرّف «قسيمتي» بارتباط
    الشخص نفسه — فلا تضيق إحداهما عن الأخرى.
    """
    src = Path("apps/payroll/api_outputs.py").read_text(encoding="utf-8")
    det = src[src.index("def payslip_detail"):][:2200]
    lst = src[src.index("def my_payslips"):][:900]
    assert "employment__person=person" in det, "التفاصيل لا تعرّف «قسيمتي» بالشخص"
    assert "employment" in lst and "person" in lst, "القائمة لا تعرّفها بالشخص"
    # وحالة المسير: القائمة تُصفّي بالمعتمد والمصروف — والتفاصيل لا تضيق عنهما
    assert 'run__status__in=["approved", "paid"]' in lst
    # الصيغة قد تختلف بالفراغات — فيُفحص وجود الحالتين معًا لا نصٌّ حرفيّ
    assert "approved" in det and "paid" in det, "التفاصيل لا تذكر حالتَي المسير"


def test_employee_payslips_uses_same_gates():
    """
    ق-٢٤١: ⚠️ **ومسار قسائم موظفٍ بعينه بنفس بوّابات ق-٢٣٩** — كل فرعٍ يضمّ
    قسيمته هو (`| own`)، **والمعتمَد والمصروف وحدهما**.
    """
    src = Path("apps/payroll/api_outputs.py").read_text(encoding="utf-8")
    fn = src[src.index("def employee_payslips"):][:2000]
    branches = re.findall(r'Gate\.filter_queryset\(request\.user, "payslips\.view_\w+", qs\)[^\n]*', fn)
    assert branches, "لا فروع صلاحية"
    assert all("| own" in b for b in branches), "فرعٌ لا يضمّ قسيمة صاحبها"
    assert "approved" in fn and "paid" in fn, "يعرض قسائم مسيرٍ لم يُعتمد"
    assert "employment_id=employment_id" in fn, "لا يُصفّي بالموظف المطلوب"
