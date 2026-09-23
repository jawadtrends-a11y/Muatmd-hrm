"""
حارس تغطية المكوّنات (ق-٢٤٤).

⚠️⚠️ **رمزٌ يولّده المحرّك بلا مكوّن** = **قيدٌ محاسبيٌّ عالق**: الشركة لا تجده
في قالب القيد فلا تربطه، والتصدير يرفض. وكان ثلاثة منها ناقصة
(`UNPAID_LEAVE` · `DED_CAP` · `ACTIVITY`) — فتظهر حين يغيب موظف بلا أجر أو
يتجاوز حسمُه السقف النظاميّ، **ويعلق قيد الشهر كلّه**.
"""
import re
from pathlib import Path


def test_every_engine_code_has_a_component():
    """كل رمزٍ يكتبه المحرّك في بنود القسيمة يجب أن يُبذر مكوّنًا."""
    engine = Path("apps/payroll/services/engine.py").read_text(encoding="utf-8")
    comps = Path("apps/payroll/services/components.py").read_text(encoding="utf-8")

    generated = set(re.findall(r'"code":\s*"([A-Z_]{3,})"', engine))
    seeded = set(re.findall(r'"code":\s*"([A-Z_]{3,})"', comps))
    # رموزٌ تأتي من مكوّنات الشركة نفسها (لا يولّدها المحرّك من فراغ)
    generated -= {"BASIC"}

    missing = sorted(generated - seeded)
    assert not missing, (
        "⚠️ رموزٌ يولّدها المحرّك بلا مكوّن مبذور — القيد يعلق حين تظهر:\n"
        + "\n".join(missing))
