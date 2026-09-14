"""
قسيمة الراتب بصيغة PDF (ق-163).

**بلاغ جواد:** زرّ «عرض القسيمة» كان يفتح **JSON خامًا** — فالمسار
يُرجع بيانات، والواجهة تفتحها كملفّ.

⚠️ **والقسيمة وثيقةٌ يحملها الموظف للبنك** — لا شاشةً يقرؤها.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from apps.core.reports.pdf import (
    FONT_BOLD, FONT_REGULAR, _ensure_fonts, _styles, ar)

INK = colors.HexColor("#1F4E5F")
LINE = colors.HexColor("#E3E8EC")
SOFT = colors.HexColor("#F5F7F8")


def _kv_table(rows, styles, widths=(55 * mm, 40 * mm)):
    """
    جدولُ قيمةٍ ومفتاح — **بلا حدودٍ ثقيلة**.

    ⚠️ **والترتيب من اليمين**: فالقسيمة عربية.
    """
    data = [[Paragraph(ar(str(v)), styles["cell"]),
             Paragraph(ar(str(k)), styles["cell"])] for k, v in rows]
    t = Table(data, colWidths=widths, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
    ]))
    return t


def _money_table(title, lines, total_label, total, styles,
                 lab=None):
    """
    جدولُ بنودٍ بمجموعه.

    ⚠️ **والبيان مع كل بند** — فمن يقرأ يعرف كيف حُسب (ق-٨٠).
    """
    # ⚠️ **والعناوين بلغة الحمولة** (بلاغ جواد): فكانت ثابتةً
    # بالعربية — **فتختلط بالإنجليزية في قسيمةٍ إنجليزية**.
    #
    # ⚠️⚠️ **ولا عمودَ لشرح الاحتساب** (قرار جواد): **فالقسيمة
    # وثيقةُ الموظف لا ورقةَ عمل المحاسب** — والتفصيل يُشوّشه.
    lab = lab or {}
    data = [[Paragraph(ar(lab.get("amount", "المبلغ")),
                       styles["head"]),
             Paragraph(ar(title), styles["head"])]]

    for ln in lines:
        data.append([
            Paragraph(str(ln.get("amount", "")), styles["cell"]),
            Paragraph(ar(ln.get("name", "")), styles["cell"]),
        ])

    if not lines:
        data.append([Paragraph("—", styles["cell"]),
                     Paragraph(ar(lab.get("no_items", "لا بنود")),
                               styles["cell"])])

    data.append([
        Paragraph(str(total), styles["total"]),
        Paragraph(ar(total_label), styles["total"]),
    ])

    t = Table(data, colWidths=(45 * mm, 100 * mm), hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), SOFT),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _center(style):
    """نسخةٌ موسَّطة من نمطٍ قائم."""
    from reportlab.lib.styles import ParagraphStyle

    return ParagraphStyle(style.name + "_c", parent=style, alignment=1)


def _logo_flowable(path, max_h=18 * mm):
    """
    شعارُ الشركة — **أو None**.

    ⚠️ **وإخفاقُه لا يكسر القسيمة**: فملفٌّ مفقودٌ أو تالف
    **يُتخطّى**، والأرقام أهمّ منه.
    """
    if not path:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image

        reader = ImageReader(path)
        iw, ih = reader.getSize()
        if not ih:
            return None
        w = max_h * (iw / ih)
        img = Image(path, width=w, height=max_h)
        img.hAlign = "CENTER"
        return img
    except Exception:          # noqa: BLE001
        return None


def build_payslip_pdf(data):
    """
    يبني القسيمة من حمولة `payslip_detail` نفسها.

    ⚠️ **ولا يحسب شيئًا**: فالأرقام من المسير، **وحسابٌ ثانٍ هنا
    قد يخالفه**.
    """
    _ensure_fonts()
    st = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=data.get("labels", {}).get("title", "payslip"))

    lab = data.get("labels", {})
    emp = data.get("employee", {})
    tot = data.get("totals", {})
    att = data.get("attendance", {})

    story = []

    # ── الترويسة: الشعار ثم الاسم ──
    #
    # ⚠️ **ووثيقةٌ بلا شعارٍ لا تبدو رسمية** (بلاغ جواد).
    # **وإخفاقُ تحميله لا يكسر القسيمة** — فالأرقام أهمّ منه.
    logo = _logo_flowable(data.get("logo_path"))
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 6))

    # ⚠️ **والعنوان موسَّط** — فالكتلة في وسط الصفحة أوضح من
    # محاذاةٍ لحافّة.
    story.append(Paragraph(ar(data.get("company_name", "")),
                           _center(st["title"])))
    story.append(Paragraph(ar(lab.get("title", "قسيمة راتب")),
                           _center(st["sub"])))
    story.append(Spacer(1, 10))

    # ── الموظف والفترة ──
    story.append(_kv_table([
        (lab.get("employee", "الموظف"), emp.get("name", "")),
        (lab.get("employee_no", "الرقم الوظيفي"),
         emp.get("employee_no", "")),
        (lab.get("id_number", "رقم الهوية"), emp.get("id_number", "")),
        (lab.get("job_title", "المسمى"), emp.get("job_title", "")),
        (lab.get("department", "القسم"), emp.get("department", "")),
        (lab.get("period", "الفترة"), data.get("period", "")),
        (lab.get("pay_date", "تاريخ الصرف"), data.get("pay_date", "")),
    ], st))
    story.append(Spacer(1, 10))

    # ── الاستحقاقات ──
    story.append(_money_table(
        lab.get("earnings", "الاستحقاقات"),
        data.get("earnings", []),
        lab.get("total_earnings", "إجمالي الاستحقاقات"),
        tot.get("earnings", "0.00"), st, lab))
    story.append(Spacer(1, 8))

    # ── الاستقطاعات ──
    story.append(_money_table(
        lab.get("deductions", "الاستقطاعات"),
        data.get("deductions", []),
        lab.get("total_deductions", "إجمالي الاستقطاعات"),
        tot.get("deductions", "0.00"), st, lab))
    story.append(Spacer(1, 10))

    # ── الصافي ── ⚠️ **بارزًا**: فهو ما يُبحث عنه أوّلًا
    net = Table(
        [[Paragraph(str(tot.get("net", "0.00")),
                    ParagraphStyle_net(st)),
          Paragraph(ar(lab.get("net_pay", "صافي المستحق")),
                    ParagraphStyle_net(st))]],
        colWidths=(60 * mm, 85 * mm), hAlign="CENTER")
    net.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(net)

    # ── الحضور ──
    if att:
        story.append(Spacer(1, 10))
        story.append(_kv_table(
            [(k, v) for k, v in att.items() if v not in (None, "")],
            st))

    # ── الملاحظة ──
    if data.get("note"):
        story.append(Spacer(1, 10))
        story.append(Paragraph(ar(data["note"]), st["note"]))

    doc.build(story)
    return buf.getvalue()


def ParagraphStyle_net(st):
    """نمطُ الصافي — أبيضُ بارز."""
    from reportlab.lib.styles import ParagraphStyle

    return ParagraphStyle(
        "net", fontName=FONT_BOLD, fontSize=13, alignment=1,
        textColor=colors.white, leading=17)


def payslip_filename(data):
    """
    اسمٌ يُعرف من نفسه — **فملفّاتٌ بأسماء متشابهة تُربك**.
    """
    import re

    emp = data.get("employee", {})
    # ⚠️ **واسمٌ لاتينيّ**: فالفترة عربية («سبتمبر ٢٠٢٦»)،
    # **واسمُ ملفٍّ مُرمَّز Base64 قد لا يُفكّه كل متصفّح**.
    period = re.sub(r"[^0-9A-Za-z_-]+", "-",
                    str(data.get("period", ""))).strip("-")
    no = re.sub(r"[^0-9A-Za-z_.-]+", "-",
                str(emp.get("employee_no", "x")))
    return f"payslip_{no}_{period or 'na'}.pdf"
