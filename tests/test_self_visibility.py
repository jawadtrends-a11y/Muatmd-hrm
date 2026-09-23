"""
حارس «ما يراه المرء عن نفسه» (ق-٢٣٩ · ق-٢٤٢).

⚠️⚠️⚠️ **نمطٌ تكرّر مرّتين**: مسارٌ يُصفّي بـ`view_team`/`view_all` **ولا يضمّ
صاحبه** — فمن له صلاحيّة فريق **يُصفَّى بفريقه وهو ليس فيه**: قسيمته تختفي عنه
(ق-٢٣٩) وملفّه يختفي عنه (ق-٢٤٢). **وكلّما كبرت صلاحيّته ضاق ما يراه لنفسه.**

فهذا الحارس يمسح المسارات كلّها — **فلا نكتشف الثالثة من عميل**.
"""
import re
from pathlib import Path

# مساراتٌ تعرض شيئًا يخصّ شخصًا بعينه: يجب أن تضمّ صاحبها
WATCHED = {
    "apps/payroll/api_outputs.py": ["payslip_detail", "employee_payslips"],
    "apps/employees/api.py": ["employee_detail"],
}
SELF_MARKS = ("| own", "|own", "person=_me", "person=person", "employment__person=person",
              "_me", "own)")


def _body(src: str, fn: str) -> str:
    i = src.index(f"def {fn}(")
    j = src.find("\n@api_view", i)
    return src[i: j if j > i else i + 3000]


def test_scoped_views_always_include_self():
    """كل فرعٍ يُصفّي بصلاحية فريق/كل يجب أن يضمّ صاحبه."""
    bad = []
    for path, fns in WATCHED.items():
        src = Path(path).read_text(encoding="utf-8")
        for fn in fns:
            body = _body(src, fn)
            uses_scope = re.search(r'Gate\.filter_queryset\([^)]*view_(team|all|)"', body)
            if not uses_scope:
                continue
            if not any(m in body for m in SELF_MARKS):
                bad.append(f"{path}:{fn} — يُصفّي بصلاحية ولا يضمّ صاحبه")
    assert not bad, (
        "⚠️ مسارٌ يحجب عن المرء ما يخصّه لأن صلاحيّته كبرت:\n" + "\n".join(bad))


def test_no_new_scoped_view_forgets_self():
    """
    ⚠️ **وأيّ مسارٍ جديد** يُصفّي بـview_team ولا يذكر صاحبه — يُكسر الاختبار
    **قبل أن يصل العميل**. (يمسح كل api*.py في apps.)
    """
    suspects = []
    for f in Path("apps").rglob("api*.py"):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"def (\w+)\(request[^)]*\):", src):
            fn = m.group(1)
            body = _body(src, fn)
            if "view_team" not in body:
                continue
            if not any(x in body for x in SELF_MARKS):
                suspects.append(f"{f}:{fn}")
    assert not suspects, (
        "مسارٌ يُصفّي بفريق المستخدم ولا يضمّه هو:\n" + "\n".join(suspects))
