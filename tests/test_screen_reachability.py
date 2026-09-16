"""
حارس وصول الشاشات (ق-210).

⚠️⚠️ **وشاشةٌ بلا رابط كالمسار اليتيم** — مبنيّةٌ ولا تُستعمل:
وكشف الجرد **«الأدوار والصلاحيات»** بلا رابط، **وهي شاشةٌ
محورية** — فمن يُعدّل دورًا لا يصلها إلا بكتابة العنوان يدويًّا.

**والجرد يدويٌّ لا يتكرّر** — فالحارس يمنع عودتها.
"""
import re
from pathlib import Path

WEB = Path("/app/web/src") if Path("/app/web/src").exists() \
    else Path(__file__).resolve().parent.parent / "web" / "src"

#: ⚠️ **شاشاتٌ تُفتح من خارج الواجهة** — رابطُ بريدٍ أو إعادةُ
#: توجيهٍ من بوابة الدفع: **فلا رابطَ لها في الكود بطبيعتها**.
EXTERNAL = {
    "/login", "/signup", "/pricing",
    "/password/forgot", "/password/reset",
    "/signup/verify", "/join",
    "/billing/callback",
}


def _screens():
    out = set()
    for f in (WEB / "app").rglob("page.tsx"):
        p = "/" + str(f.parent.relative_to(WEB / "app"))
        out.add("/" if p == "/." else p)
    return out


def _linked():
    out = set()
    for f in WEB.rglob("*.tsx"):
        t = f.read_text(encoding="utf-8")
        # ⚠️ **والرابط الديناميكيّ يُلتقط كذلك**: فشاشةٌ تُفتح
        # بـ`/x/${id}` **موصولةٌ** — والقالب يقطع عند `${`.
        for m in re.finditer(r'["`](/[a-z0-9/_-]*)(?:\$\{)?', t):
            out.add(m.group(1).rstrip("/") or "/")
    return out


def _norm(p):
    """يُسقط المتغيّرات: `/x/[id]` ← `/x`."""
    return re.sub(r'/\[[^\]]+\]', '', p).rstrip("/") or "/"


def test_every_screen_is_reachable():
    """
    ⚠️⚠️ الأهمّ: **ولكل شاشةٍ طريقٌ إليها**.

    **فشاشةٌ مبنيّةٌ لا يصلها رابط عملٌ ضائع** — والمستخدم لا
    يكتب العناوين يدويًّا.
    """
    linked = {_norm(x) for x in _linked()}
    orphans = sorted(
        s for s in _screens()
        if _norm(s) not in linked and _norm(s) not in EXTERNAL)

    assert not orphans, (
        "شاشاتٌ بلا رابطٍ يصلها:\n  " + "\n  ".join(orphans)
        + "\n\nأضف رابطًا في القائمة أو في شاشةٍ أخرى،"
          " أو أضفها لـEXTERNAL إن كانت تُفتح من بريدٍ أو بوابة.")


def test_key_screens_are_linked():
    """
    ⚠️ **والشاشات المحورية خاصّةً**: فغيابُ رابطِها **يُعطّل
    النظام** لا شاشةً وحدها.
    """
    linked = {_norm(x) for x in _linked()}
    critical = ["/settings/access", "/settings/users", "/employees",
                "/payroll", "/attendance", "/leaves"]
    missing = [c for c in critical if c not in linked]
    assert not missing, f"شاشاتٌ محورية بلا رابط: {missing}"
