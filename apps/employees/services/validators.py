"""
التحقق من بيانات الموظف: الآيبان، الهوية، والجوال.

المبدأ (ق-20): نحفظ مدخلات الشركة. التحقق يمنع الخطأ التقني
(آيبان غير صالح رياضيًا) لا يصحّح قرار الشركة.
"""
import re

SAUDI_IBAN_RE = re.compile(r"^SA\d{22}$")
E164_RE = re.compile(r"^\+\d{8,15}$")


def validate_saudi_iban(iban: str) -> tuple[bool, str]:
    """
    تحقق MOD-97 (ISO 13616). الآيبان السعودي 24 خانة.

    يمنع رفض ملف حماية الأجور بعد إرساله — أرخص بكثير من اكتشاف
    الخطأ من البنك.
    """
    s = (iban or "").replace(" ", "").upper()
    if not s:
        return False, "الآيبان مطلوب للصرف البنكي"
    if not SAUDI_IBAN_RE.match(s):
        return False, ("صيغة الآيبان غير صحيحة — يجب أن يبدأ بـSA "
                       "ويتكوّن من 24 خانة")

    rearranged = s[4:] + s[:4]
    numeric = "".join(
        str(ord(ch) - 55) if ch.isalpha() else ch for ch in rearranged)
    if int(numeric) % 97 != 1:
        return False, "رقم الآيبان غير صالح (فشل التحقق من رقم المراقبة)"
    return True, ""


def validate_saudi_id(id_number: str, id_type: str) -> tuple[bool, str]:
    """
    الهوية الوطنية تبدأ بـ1 والإقامة بـ2، وكلتاهما 10 خانات.
    """
    s = (id_number or "").strip()
    if not s.isdigit():
        return False, "رقم الهوية يجب أن يتكوّن من أرقام فقط"

    if id_type == "national_id":
        if len(s) != 10:
            return False, "الهوية الوطنية 10 خانات"
        if not s.startswith("1"):
            return False, "الهوية الوطنية تبدأ بالرقم 1"
    elif id_type == "iqama":
        if len(s) != 10:
            return False, "رقم الإقامة 10 خانات"
        if not s.startswith("2"):
            return False, "رقم الإقامة يبدأ بالرقم 2"
    return True, ""


def normalize_mobile(mobile: str) -> tuple[str, str]:
    """
    يوحّد صيغة الجوال إلى E.164.
    الجوال مفتاح التعريف في واتساب — التوحيد يمنع ازدواج الشخص.
    """
    s = re.sub(r"[\s\-()]", "", mobile or "")
    if not s:
        return "", ""
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("05") and len(s) == 10:
        s = "+966" + s[1:]
    elif s.startswith("5") and len(s) == 9:
        s = "+966" + s
    elif not s.startswith("+"):
        s = "+" + s

    if not E164_RE.match(s):
        return s, "صيغة رقم الجوال غير صحيحة"
    return s, ""
