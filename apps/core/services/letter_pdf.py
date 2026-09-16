"""
خطاب رسميّ بصيغة PDF (ق-196).

⚠️⚠️ **والخطاب لم يكن يُطبع** — كشفه الجرد: **فخطاب تعريفٍ بالراتب
يُحمَل للبنك ورقةً**، ونصٌّ في الشاشة لا يُغني.

⚠️ **والترويسة والتذييل صورتان** من القالب (ق-١٩٢) — **وفارغهما
يعني ورقًا مُترَوَّسًا سلفًا**.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from apps.core.reports.pdf import (
    FONT_BOLD, FONT_REGULAR, _ensure_fonts, ar)

INK = colors.HexColor("#1F4E5F")
MUTED = colors.HexColor("#6B7A85")
LINE = colors.HexColor("#E3E8EC")


def _image(path, max_h):
    """
    صورةٌ بعرضٍ متناسب — **أو None**.

    ⚠️ **وإخفاقُها لا يكسر الخطاب**: فملفٌّ مفقودٌ أو تالف
    **يُتخطّى** — والنصّ أهمّ منه.
    """
    if not path:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image

        iw, ih = ImageReader(path).getSize()
        if not ih:
            return None
        img = Image(path, width=max_h * (iw / ih), height=max_h)
        img.hAlign = "CENTER"
        return img
    except Exception:          # noqa: BLE001
        return None


def _file_path(stored):
    """مسارُ ملفٍّ مخزَّن — أو فراغ."""
    if stored is None:
        return ""
    try:
        return str(getattr(stored, "file", None).path)
    except Exception:          # noqa: BLE001
        return ""


def build_letter_pdf(letter):
    """
    يبني الخطاب من نصّه **المجمَّد** لا من القالب.

    ⚠️⚠️ **فتعديل القالب بعد الإصدار لا يغيّر خطابًا صدر** — وهو
    وثيقةُ لحظتها.
    """
    _ensure_fonts()
    buf = io.BytesIO()

    t = letter.template
    header = _image(_file_path(t.header_image), 26 * mm)
    footer = _image(_file_path(t.footer_image), 18 * mm)
    logo = _image(_file_path(getattr(letter.company, "logo", None)),
                  14 * mm)

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=letter.letter_no)

    title = ParagraphStyle(
        "t", fontName=FONT_BOLD, fontSize=14, alignment=1,
        leading=22, spaceAfter=6)
    meta = ParagraphStyle(
        "m", fontName=FONT_REGULAR, fontSize=9, alignment=2,
        textColor=MUTED, leading=15)
    body = ParagraphStyle(
        "b", fontName=FONT_REGULAR, fontSize=11.5, alignment=4,
        leading=24, firstLineIndent=0)

    story = []

    # ── الترويسة ──
    if header is not None:
        story.append(header)
        story.append(Spacer(1, 10))

    # ── رقم الخطاب وتاريخه ──
    #
    # ⚠️ **والرقم بارزٌ أعلى اليمين**: فمن يراجع **يبحث به**.
    info = [[
        Paragraph(ar(f"التاريخ: {letter.issued_on}"), meta),
        Paragraph(ar(f"الرقم: {letter.letter_no}"), meta),
    ]]
    tbl = Table(info, colWidths=(85 * mm, 85 * mm), hAlign="CENTER")
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 14))

    # ── العنوان ──
    if letter.heading_ar:
        story.append(Paragraph(ar(letter.heading_ar), title))
        story.append(Spacer(1, 8))

    # ── موجّه إلى ──
    if letter.addressee_ar:
        story.append(Paragraph(ar(letter.addressee_ar), body))
        story.append(Spacer(1, 8))

    # ── النصّ ──
    #
    # ⚠️ **وكل سطرٍ فقرةٌ**: فالنصّ المجمَّد **يحمل أسطره**،
    # وجمعُها في فقرةٍ واحدة **يُفقد شكله**.
    for line in (letter.body_ar or "").split("\n"):
        if line.strip():
            story.append(Paragraph(ar(line.strip()), body))
        else:
            story.append(Spacer(1, 8))

    # ── الصلاحية ──
    if letter.valid_until:
        story.append(Spacer(1, 16))
        story.append(Paragraph(
            ar(f"هذا الخطاب صالحٌ حتى {letter.valid_until}"), meta))

    # ── الشعار والتذييل ──
    if logo is not None:
        story.append(Spacer(1, 18))
        story.append(logo)

    if footer is not None:
        story.append(Spacer(1, 10))
        story.append(footer)

    doc.build(story)
    return buf.getvalue()


def letter_filename(letter):
    """اسمٌ يُعرف من نفسه — **ولاتينيٌّ**، فالعربيّ يُرمَّز."""
    import re

    no = re.sub(r"[^0-9A-Za-z_.-]+", "-", letter.letter_no or "letter")
    return f"letter_{no}.pdf"
