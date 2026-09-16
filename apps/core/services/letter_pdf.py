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


#: ⚠️ ملفّاتٌ مقصوصة — تُبنى مرّةً وتبقى ما دامت العملية حيّة
_TRIM_CACHE = {}


def _trim(path, threshold=240):
    """
    يقصّ الفراغ الأبيض حول التصميم — **أو None**.

    ⚠️ **وإخفاقُه يُرجع الأصل**: فصورةٌ لا تُقرأ **تُرسم كما هي**،
    والنصّ أهمّ من قصّ فراغ.
    """
    if path in _TRIM_CACHE:
        return _TRIM_CACHE[path]

    try:
        import os
        import tempfile

        from PIL import Image as _PIL, ImageChops, ImageOps

        im = _PIL.open(path)
        rgb = im.convert("RGB")
        # ⚠️ **والخلفيةُ لونُ الزاوية**: فترويسةٌ بخلفيةٍ رماديّة
        # **لا تُقصّ بالأبيض وحده**.
        bg = _PIL.new("RGB", rgb.size, rgb.getpixel((0, 0)))
        diff = ImageChops.difference(rgb, bg)
        box = ImageOps.autocontrast(diff.convert("L")).getbbox()

        if not box or (box[2] - box[0]) < 8 or (box[3] - box[1]) < 8:
            _TRIM_CACHE[path] = None
            return None

        out = os.path.join(
            tempfile.gettempdir(),
            f"trim_{abs(hash(path))}_{os.path.basename(path)}")
        im.crop(box).save(out)
        _TRIM_CACHE[path] = out
        return out
    except Exception:          # noqa: BLE001
        _TRIM_CACHE[path] = None
        return None


def _image(path, max_w, max_h=45 * mm):
    """
    صورةٌ **بعرض الصفحة** وارتفاعٍ متناسب — أو None.

    ⚠️ **وسقفُ الارتفاع يمنع ترويسةً تبتلع الصفحة**.

    ⚠️ **وإخفاقُها لا يكسر الخطاب**: فملفٌّ مفقودٌ أو تالف
    **يُتخطّى** — والنصّ أهمّ منه.
    """
    if not path:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image

        # ق-201: ⚠️⚠️ **والفراغ الأبيض يُقصّ آليًّا** (بلاغ جواد):
        # فصورةُ ترويسةٍ فيها ١٢٪ فراغًا **تُطبع بفراغها** —
        # **والعميل لا يُكلَّف تحرير صورته**.
        path = _trim(path) or path

        iw, ih = ImageReader(path).getSize()
        if not iw or not ih:
            return None
        w = max_w
        h = w * (ih / iw)
        if h > max_h:
            h = max_h
            w = h * (iw / ih)
        img = Image(path, width=w, height=h)
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


#: محاذاةُ reportlab — يمين ٢، وسط ١، يسار ٠، ضبط ٤
_ALIGN = {"right": 2, "center": 1, "left": 0, "justify": 4}

#: أحجامٌ ثلاثة — **ولا نفتح الباب لكل رقم**: فخطابٌ بعشرين حجمًا
# يفقد رسميّته.
_SIZE = {"small": 9.5, "normal": 11.5, "large": 14}


def _paragraphs(raw, base):
    """
    يقسم النصّ فقراتٍ بأنماطها.

    ⚠️⚠️ **والنصّ الخام يعمل كما كان**: فقوالبُ كُتبت قبل المحرّر
    **لا تنكسر** — والسطر بلا وسمٍ فقرةٌ بالنمط الأساسيّ.

    ⚠️ **ولا HTML إلا ما يفهمه reportlab**: `<b>` و`<i>` و`<u>`
    و`<br/>` — **وما عداه يظهر نصًّا في الخطاب**.
    """
    import re as _re

    from reportlab.lib.styles import ParagraphStyle as _PS

    out = []
    # فقرةٌ موسومة: <p align="center" size="large">…</p>
    pattern = _re.compile(
        r'<p(?P<attrs>[^>]*)>(?P<text>.*?)</p>', _re.S)

    # ⚠️⚠️ **والنصّ يخلط الموسوم بالخام** (بلاغ جواد): فقالبٌ
    # فيه فقرةٌ موسومة وأسطرٌ عادية **كان يفقد الأسطر كلّها** —
    # فالقراءة كانت إمّا وسومًا وإمّا أسطرًا.
    #
    # **فنقسم النصّ قطعًا**: ما بين الوسوم أسطرٌ خام، وما داخلها
    # فقراتٌ بأنماطها.
    chunks = []
    pos = 0
    for m in pattern.finditer(raw):
        if m.start() > pos:
            chunks.append(("plain", raw[pos:m.start()]))
        chunks.append(("tagged", m))
        pos = m.end()
    if pos < len(raw):
        chunks.append(("plain", raw[pos:]))

    for kind, item in chunks:
        if kind == "plain":
            # ⚠️ **وأطرافُ القطعة تُقلَّم**: فالسطر الفاصل بين
            # النصّ والوسم **ليس فراغًا مقصودًا** — وإدراجه
            # يُباعد الفقرات بلا سبب.
            lines = item.split("\n")
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            for line in lines:
                if line.strip():
                    out.append((ar(line.strip()), base))
                elif out and out[-1][0] is not None:
                    out.append((None, base))
            continue

        m = item
        attrs = m.group("attrs") or ""
        text = (m.group("text") or "").strip()
        if not text:
            out.append((None, base))
            continue

        align = _re.search(r'align="([a-z]+)"', attrs)
        size = _re.search(r'size="([a-z]+)"', attrs)

        st = _PS(
            f"p{len(out)}", parent=base,
            alignment=_ALIGN.get(align.group(1) if align else "",
                                 base.alignment),
            fontSize=_SIZE.get(size.group(1) if size else "",
                               base.fontSize),
            leading=_SIZE.get(size.group(1) if size else "",
                              base.fontSize) * 2.05)

        # ⚠️ **والتشكيل يُحفظ**: فـ`ar()` تقلب الحروف، **والوسوم
        # تُعزل عنها** لئلا تُقلب معها.
        parts = _re.split(r'(</?[biu]>|<br\s*/?>)', text)
        joined = "".join(
            p if _re.fullmatch(r'</?[biu]>|<br\s*/?>', p) else ar(p)
            for p in parts)
        out.append((joined, st))

    return out


def build_letter_pdf(letter):
    """
    يبني الخطاب من نصّه **المجمَّد** لا من القالب.

    ⚠️⚠️ **فتعديل القالب بعد الإصدار لا يغيّر خطابًا صدر** — وهو
    وثيقةُ لحظتها.
    """
    _ensure_fonts()
    buf = io.BytesIO()

    t = letter.template
    # ⚠️ **وبعرض الصفحة لا بارتفاعٍ صغير** (بلاغ جواد): فترويسةٌ
    # بارتفاع ٢٦ مم **تظهر شريطًا باهتًا** — والمطبوعة تملأ العرض.
    # ⚠️ **وبقياسٍ معقول** (بلاغ جواد): فـ١٧٠ مم عرضًا **تدفع
    # التذييل لصفحةٍ ثانية** — والترويسة شريطٌ لا لوحة.
    # ⚠️ **وقياسٌ متوسّط**: ترويسةٌ ظاهرةٌ **بلا أن تدفع صفحةً
    # ثانية** — والحدّ في الارتفاع لا العرض.
    # ⚠️⚠️ **والصورة بعرض الصفحة وارتفاعُها بنسبتها** (قرار
    # جواد): **فالتحجيم يتبع الصورة لا رقمًا نفرضه** — وسقفُ
    # الارتفاع حمايةٌ من صورةٍ طويلة تبتلع الصفحة.
    #
    # وعرضُ الكتابة = A4 (210) ناقص الهامشين (20+20) = **170 مم**.
    # ⚠️⚠️ **وسقفُ الارتفاع كان يقصّ العرض** (بلاغ جواد): فصورةٌ
    # نسبتها ٣:١ **تحتاج ٥٧ مم ارتفاعًا لتبلغ ١٧٠ عرضًا** — وسقفُ
    # ٣٢ يردّها إلى ٩٦ مم.
    #
    # **فالسقف يتّسع**: والصورة تبلغ عرض الصفحة، **وحمايةُ
    # الارتفاع تبقى لصورةٍ شاذّة**.
    # ⚠️⚠️ **وسقفٌ يترك الصفحة للنصّ** (بلاغ جواد): فترويسةُ
    # ٥٧ مم وتذييلُ ٤٥ **يبتلعان ثلث الصفحة** — فلا يتّسع النصّ
    # وتنقسم.
    #
    # **والسقف بالارتفاع لا العرض**: فالصورة تُصغَّر بنسبتها،
    # **وتبقى بعرضها الكامل ما أمكن**.
    # ⚠️ **وقياسٌ وسط**: فـ٢٨ مم **صغيرةٌ مبالغٌ فيها**، و٥٧
    # **تبتلع ثلث الصفحة** — والنصّ اتّسع بفراغٍ أسفله.
    header = _image(_file_path(t.header_image), 170 * mm,
                    max_h=40 * mm)
    footer = _image(_file_path(t.footer_image), 170 * mm,
                    max_h=30 * mm)

    # ق-200: ⚠️⚠️ **والترويسة والتذييل يُرسمان على كل صفحة**
    # (بلاغ جواد): فجعلُهما جزءًا من النصّ **يدفعه لصفحةٍ ثانية**،
    # **ويترك فراغًا كبيرًا أسفلها** — والصحيح أن **ينساب النصّ
    # بينهما**.
    hh = header.drawHeight if header is not None else 0
    fh = footer.drawHeight if footer is not None else 0

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=20 * mm, leftMargin=20 * mm,
        topMargin=hh + 10 * mm,
        bottomMargin=fh + 18 * mm,
        title=letter.letter_no)

    def _decorate(canvas, _doc):
        """
        يرسم الترويسة والتذييل — **خارج تدفّق النصّ**.

        ⚠️ **و`drawOn` ينطلق من الزاوية السفلى للصورة**: فالترويسة
        تُرسم من أعلى الصفحة ناقصَ ارتفاعها، **والتذييل من
        أسفلها**.
        """
        canvas.saveState()
        pw, ph = A4
        if header is not None:
            header.drawOn(canvas, (pw - header.drawWidth) / 2,
                          ph - hh - 6 * mm)
        if footer is not None:
            # ⚠️ **ولا يُلاصق الحافّة** (بلاغ جواد): فالطابعة
            # **تقصّ ما قارب الطرف**.
            footer.drawOn(canvas, (pw - footer.drawWidth) / 2,
                          14 * mm)
        canvas.restoreState()

    title = ParagraphStyle(
        "t", fontName=FONT_BOLD, fontSize=14, alignment=1,
        leading=22, spaceAfter=6)
    meta = ParagraphStyle(
        "m", fontName=FONT_REGULAR, fontSize=9, alignment=2,
        textColor=MUTED, leading=15)
    # ⚠️⚠️ **والأساس يمينٌ لا ضبط** (بلاغ جواد): فـ`ar()` تقلب
    # النصّ بـbidi، **والضبط يوزّعه من اليسار** — فيظهر معكوسًا.
    body = ParagraphStyle(
        "b", fontName=FONT_REGULAR, fontSize=11.5, alignment=2,
        leading=24, firstLineIndent=0)

    story = []

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
        # ⚠️ **ولا خطَّ تحتهما** (بلاغ جواد) — والترويسة تفصل
        # كفايةً.
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 10))

    # ── العنوان ──
    if letter.heading_ar:
        story.append(Paragraph(ar(letter.heading_ar), title))
        story.append(Spacer(1, 8))

    # ── موجّه إلى ──
    # ق-199: ⚠️⚠️ **ولا يُطبع المرسَل إليه سطرًا مستقلًّا** (قرار
    # جواد): **فيظهر عاريًا بلا مقدّمة تعريفٍ ولا تقديم احترام**.
    #
    # **وموضعه نصُّ القالب**: «إلى السادة / {{addressee}}
    # المحترمين» — بصياغته كاملةً.

    # ── النصّ ──
    #
    # ⚠️⚠️ **والتنسيق لكل فقرة** (قرار جواد): محاذاةٌ وحجمٌ —
    # **يُخزَّنان HTML مبسَّطًا يفهمه reportlab**.
    for para, style in _paragraphs(letter.body_ar or "", body):
        if para is None:
            story.append(Spacer(1, 8))
        else:
            story.append(Paragraph(para, style))

    # ── الصلاحية ──
    if letter.valid_until:
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            ar(f"هذا الخطاب صالحٌ حتى {letter.valid_until}"), meta))

    # ── التذييل ──
    #
    # ⚠️ **ولا شعارَ مستقلّ** (قرار جواد): **فالتذييل هو موضع
    # الهوية** — وشعارٌ فوقه تكرار.

    doc.build(story, onFirstPage=_decorate,
               onLaterPages=_decorate)
    return buf.getvalue()


def letter_filename(letter):
    """اسمٌ يُعرف من نفسه — **ولاتينيٌّ**، فالعربيّ يُرمَّز."""
    import re

    no = re.sub(r"[^0-9A-Za-z_.-]+", "-", letter.letter_no or "letter")
    return f"letter_{no}.pdf"
