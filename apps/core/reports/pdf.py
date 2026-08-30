"""
تصدير التقارير إلى PDF بالعربية.

العربية في PDF تحتاج ثلاث خطوات لا واحدة:
  1. خط يدعم الحروف العربية (Amiri)
  2. إعادة تشكيل الحروف لتتصل (arabic_reshaper)
  3. عكس اتجاه النص للعرض (python-bidi)

بلا الثلاث معًا يظهر النص حروفًا منفصلة معكوسة.
"""
import io
import os
from datetime import datetime

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

FONT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "assets", "fonts")

FONT_REGULAR = "Amiri"
FONT_BOLD = "Amiri-Bold"
_fonts_ready = False

HEADER_BG = colors.HexColor("#1F4E5F")
HEADER_FG = colors.white
TOTAL_BG = colors.HexColor("#EEF3F6")
GRID = colors.HexColor("#D0D0D0")
MUTED = colors.HexColor("#666666")


def _ensure_fonts():
    """يسجّل الخطوط مرة واحدة."""
    global _fonts_ready
    if _fonts_ready:
        return
    regular = os.path.join(FONT_DIR, "Amiri-Regular.ttf")
    bold = os.path.join(FONT_DIR, "Amiri-Bold.ttf")
    if not os.path.exists(regular):
        raise FileNotFoundError(f"خط العربية غير موجود: {regular}")
    pdfmetrics.registerFont(TTFont(FONT_REGULAR, regular))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, bold))
    pdfmetrics.registerFontFamily(FONT_REGULAR, normal=FONT_REGULAR,
                                  bold=FONT_BOLD)
    _fonts_ready = True


def ar(text):
    """
    يحوّل النص العربي للعرض الصحيح في PDF.

    الأرقام والنصوص اللاتينية تمر كما هي.
    """
    if text in (None, ""):
        return ""
    s = str(text)
    if not any("\u0600" <= ch <= "\u06FF" for ch in s):
        return s
    return get_display(arabic_reshaper.reshape(s))


def _styles():
    return {
        "title": ParagraphStyle(
            "title", fontName=FONT_BOLD, fontSize=15, alignment=2,
            spaceAfter=4, leading=20),
        "sub": ParagraphStyle(
            "sub", fontName=FONT_REGULAR, fontSize=9, alignment=2,
            textColor=MUTED, leading=13),
        "cell": ParagraphStyle(
            "cell", fontName=FONT_REGULAR, fontSize=8, alignment=2,
            leading=11),
        "head": ParagraphStyle(
            "head", fontName=FONT_BOLD, fontSize=8, alignment=1,
            textColor=HEADER_FG, leading=11),
        "total": ParagraphStyle(
            "total", fontName=FONT_BOLD, fontSize=8, alignment=1,
            textColor=colors.HexColor("#1F4E5F"), leading=11),
        "note": ParagraphStyle(
            "note", fontName=FONT_REGULAR, fontSize=8, alignment=2,
            textColor=MUTED, leading=12),
    }


def export_to_pdf(result, company_name=""):
    """
    يبني PDF من نتيجة تقرير.

    الأعمدة معكوسة الترتيب لأن القراءة من اليمين.
    """
    _ensure_fonts()
    st = _styles()

    buf = io.BytesIO()
    wide = len(result.columns) > 6
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4) if wide else A4,
        rightMargin=12 * mm, leftMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=14 * mm,
        title=result.title_ar)

    story = [Paragraph(ar(result.title_ar), st["title"])]
    if company_name:
        story.append(Paragraph(ar(company_name), st["sub"]))
    if result.subtitle_ar:
        story.append(Paragraph(ar(result.subtitle_ar), st["sub"]))
    story.append(Paragraph(
        ar(f"تاريخ الإصدار: {datetime.now():%Y-%m-%d %H:%M}"), st["sub"]))
    story.append(Spacer(1, 6 * mm))

    # ── الجدول: الأعمدة معكوسة للقراءة من اليمين ──
    cols = list(reversed(result.columns))

    header = [Paragraph(ar(c.label_ar), st["head"]) for c in cols]
    data = [header]

    for row in result.rows:
        line = []
        for c in cols:
            v = row.get(c.key, "")
            if c.kind in ("money", "number") and v not in (None, ""):
                try:
                    v = f"{float(v):,.2f}"
                except (TypeError, ValueError):
                    pass
            line.append(Paragraph(ar(v), st["cell"]))
        data.append(line)

    if result.totals:
        total_line = []
        for c in cols:
            if c.key in result.totals:
                val = f"{float(result.totals[c.key]):,.2f}"
                total_line.append(Paragraph(ar(val), st["total"]))
            elif c is cols[-1]:
                total_line.append(Paragraph(ar("الإجمالي"), st["total"]))
            else:
                total_line.append("")
        data.append(total_line)

    total_width = sum(c.width for c in cols) or 1
    avail = doc.width
    widths = [max(18 * mm, avail * c.width / total_width) for c in cols]
    scale = avail / sum(widths)
    widths = [w * scale for w in widths]

    table = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2 if result.totals else -1),
         [colors.white, colors.HexColor("#FAFBFC")]),
    ]
    if result.totals:
        style.append(("BACKGROUND", (0, -1), (-1, -1), TOTAL_BG))
    table.setStyle(TableStyle(style))
    story.append(table)

    if result.notes:
        story.append(Spacer(1, 5 * mm))
        for note in result.notes:
            story.append(Paragraph(ar(f"• {note}"), st["note"]))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(FONT_REGULAR, 7)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(
            doc_.pagesize[0] / 2, 8 * mm,
            ar(f"صفحة {canvas.getPageNumber()}"))
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def pdf_filename(result):
    stamp = datetime.now().strftime("%Y%m%d")
    return f"{result.key.replace('/', '_')}_{stamp}.pdf"
