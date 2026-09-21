"""
حارس التبويبات في الواجهة (ق-231).

⚠️⚠️ **والتحديث كان يُعيد للتبويب الأول**: التبويب في الذاكرة وحدها.
وأُصلح في ثلاث صفحاتٍ **كلٌّ بطريقة** — فعاد في إحدى عشرة: **فلا شيء
كان يُلزم الصفحة الجديدة بالحلّ**. وهذا الحارس هو ذلك الإلزام.

يقرأ الملفّات نصًّا — بلا متصفّح ولا بناء.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "web" / "src"
FILES = [p for d in ("app", "components")
         for p in (SRC / d).rglob("*.tsx")]

# استثناءٌ موثَّق: شاشة الدخول تمحو الرمز من الرابط ثم تُنقل فورًا
REPLACE_NULL_OK = {"app/login/page.tsx"}


def _rel(p):
    return str(p.relative_to(SRC))


def test_frontend_is_visible():
    """⚠️ وحارسٌ لا يرى ملفّاتٍ **ينجح صامتًا** — فيُفحص أولًا أنه يراها."""
    assert (SRC / "lib" / "useUrlTab.ts").exists()
    assert len(FILES) > 50


def test_no_tab_state_in_memory():
    """
    ⚠️⚠️ الأهمّ: **لا تبويبَ بـuseState** — فكل تبويبٍ بالخُطّاف المشترك.
    """
    bad = []
    pat = re.compile(
        r"const \[\s*(tab|activeTab|currentTab)\s*,\s*set\w+\s*\]\s*=\s*useState")
    for p in FILES:
        if pat.search(p.read_text(encoding="utf-8")):
            bad.append(_rel(p))
    assert not bad, (
        "تبويبٌ في الذاكرة — يضيع بالتحديث. استعمل useUrlTab: " + ", ".join(bad))


def test_history_state_is_preserved():
    """⚠️ `replaceState(null` يمحو حالة Next.js — فيُربك زرّ الرجوع."""
    bad = [_rel(p) for p in FILES
           if "replaceState(null" in p.read_text(encoding="utf-8")
           and _rel(p) not in REPLACE_NULL_OK]
    assert not bad, "replaceState(null في: " + ", ".join(bad)
