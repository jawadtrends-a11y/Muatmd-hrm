"""
بنوك السعودية ورموزها في الآيبان (ق-57).

الخانتان الخامسة والسادسة تحملان رمز البنك لدى البنك المركزي.

⚠️ القائمة تتغيّر: بنوك تندمج، ومحافظ رقمية تُستحدث — لذلك
جدول في القاعدة لا ثابت في الكود.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel

OTHER_LABEL = "بنوك أخرى"


class BankKind(models.TextChoices):
    LOCAL = "local", _("بنك محلي")
    DIGITAL = "digital", _("بنك رقمي / محفظة")
    FOREIGN = "foreign", _("فرع بنك أجنبي")
    CENTRAL = "central", _("البنك المركزي")


class Bank(TimeStampedModel):
    """بنك بجدول المنصة — مشترك بين كل الحسابات، لا يُعزل."""

    iban_code = models.CharField(
        _("رمز الآيبان"), max_length=2, unique=True, db_index=True)
    name_ar = models.CharField(_("الاسم"), max_length=120)
    name_en = models.CharField(_("بالإنجليزية"), max_length=120, blank=True)
    short_ar = models.CharField(_("المختصر"), max_length=40, blank=True)
    swift = models.CharField(_("سويفت"), max_length=11, blank=True)
    kind = models.CharField(_("النوع"), max_length=12,
                            choices=BankKind.choices,
                            default=BankKind.LOCAL)
    is_active = models.BooleanField(_("نشط"), default=True)
    supports_wps = models.BooleanField(
        _("يقبل ملفات حماية الأجور"), default=True)
    display_order = models.IntegerField(_("الترتيب"), default=100)

    class Meta:
        verbose_name = _("بنك")
        verbose_name_plural = _("البنوك")
        ordering = ["display_order", "name_ar"]

    def __str__(self):
        return f"{self.name_ar} ({self.iban_code})"


def lookup(iban_or_code):
    """يرجع كائن البنك أو None."""
    value = (iban_or_code or "").strip().upper().replace(" ", "")
    if len(value) >= 6 and value.startswith("SA"):
        code = value[4:6]
    elif len(value) == 2:
        code = value
    else:
        return None
    return Bank.objects.filter(iban_code=code).first()


def label_for(iban):
    """
    اسم البنك للعرض (ق-57).

    معروف → اسمه · غير معروف → «بنوك أخرى».
    ولا تحذير في الحالتين — مسؤولية صحة الآيبان على الشركة.
    """
    value = (iban or "").strip().upper().replace(" ", "")
    if len(value) < 6 or not value.startswith("SA"):
        return ""
    bank = lookup(value)
    return bank.name_ar if bank else OTHER_LABEL


# ══════════ البذرة الرسمية ══════════
# (الرمز، الاسم، المختصر، سويفت، النوع، الترتيب)

SAUDI_BANKS = [
    # ── المحلية ──
    ("80", "مصرف الراجحي", "الراجحي", "RJHISARI", "local", 1),
    ("10", "البنك الأهلي السعودي", "الأهلي", "NCBKSAJE", "local", 2),
    ("20", "بنك الرياض", "الرياض", "RIBLSARI", "local", 3),
    ("45", "البنك السعودي البريطاني", "ساب", "SABBSARI", "local", 4),
    ("55", "البنك السعودي الفرنسي", "الفرنسي", "BSFRSARI", "local", 5),
    ("30", "البنك العربي الوطني", "العربي الوطني", "ARNBSARI", "local", 6),
    ("05", "مصرف الإنماء", "الإنماء", "INMASARI", "local", 7),
    ("15", "بنك البلاد", "البلاد", "ALBISARI", "local", 8),
    ("60", "بنك الجزيرة", "الجزيرة", "BJAZSAJE", "local", 9),
    ("65", "البنك السعودي للاستثمار", "الاستثمار", "SIBCSARI", "local", 10),

    # ── مندمجة: تبقى لفهم الآيبانات القائمة ──
    ("40", "سامبا — اندمج في الأهلي", "سامبا", "SAMBSARI", "local", 40),
    ("50", "السعودي الهولندي — اندمج في ساب", "الهولندي", "AAALSARI",
     "local", 41),

    # ── فروع أجنبية ──
    ("71", "بنك البحرين الوطني", "البحرين", "NBOBSARI", "foreign", 60),
    ("75", "بنك الكويت الوطني", "الكويت", "NBOKSAJE", "foreign", 61),
    ("76", "بنك مسقط", "مسقط", "BMUSSARI", "foreign", 62),
    ("81", "دويتشه بنك", "دويتشه", "DEUTSARI", "foreign", 63),
    ("82", "بنك باكستان الوطني", "باكستان", "NBOPSARI", "foreign", 64),
    ("83", "بنك الهند", "الهند", "SBOISAJE", "foreign", 65),
    ("84", "زراعات بنك التركي", "زراعات", "TCZTSAJE", "foreign", 66),
    ("86", "جي بي مورغان تشيس", "جي بي مورغان", "CHASSARI", "foreign", 67),
    ("87", "الصناعي والتجاري الصيني", "آي سي بي سي", "ICBKSARI",
     "foreign", 68),
    ("90", "بنك الخليج الدولي", "الخليج الدولي", "GULFSARI", "foreign", 69),
    ("95", "بنك الإمارات دبي الوطني", "الإمارات", "EBILSARI", "foreign", 70),
    ("98", "بي إن بي باريبا", "باريبا", "BNPASARI", "foreign", 71),

    # ── المركزي ──
    ("01", "البنك المركزي السعودي", "ساما", "SAMASARI", "central", 90),
]


def sync_banks():
    """
    يزرع البنوك ويحدّثها — يُستدعى عند الإقلاع.

    لا يمسح: بنك أُضيف يدويًا من اللوحة يبقى.
    """
    created = updated = 0
    for code, name, short, swift, kind, order in SAUDI_BANKS:
        _obj, made = Bank.objects.update_or_create(
            iban_code=code,
            defaults={"name_ar": name, "short_ar": short, "swift": swift,
                      "kind": kind, "display_order": order},
        )
        created += int(made)
        updated += int(not made)
    return {"created": created, "updated": updated}
