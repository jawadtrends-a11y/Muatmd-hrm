"""
إصدار الخطابات من قوالبها (ق-128).

⚠️ **المتغيّرات معلَنة لا حرّة**: قالبٌ يقرأ أي حقلٍ يكشف ما لا
يُكشف وينكسر كلّما تغيّر عمود — فكل متغيّر يُعلَن بمصدره.
"""
import logging
import re
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)


class LetterError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


#: (المفتاح، الوصف، أيحتاج صلاحية الرواتب؟)
VARIABLES = [
    ("employee_name", "اسم الموظف", False),
    ("employee_no", "الرقم الوظيفي", False),
    ("id_number", "رقم الهوية", False),
    ("nationality", "الجنسية", False),
    ("job_title", "المسمى الوظيفي", False),
    ("department", "الإدارة", False),
    ("branch", "الفرع", False),
    ("join_date", "تاريخ الالتحاق", False),
    ("service_years", "سنوات الخدمة", False),
    ("contract_type", "نوع العقد", False),
    ("company_name", "اسم الشركة", False),
    ("company_cr", "السجل التجاري", False),
    ("today", "تاريخ اليوم", False),
    ("today_hijri", "التاريخ الهجري", False),
    ("letter_no", "رقم الخطاب", False),
    ("addressee", "الجهة الموجَّه إليها", False),
    # ⚠️ الراتب لا يظهر إلا بطلب صاحبه — نصٌّ في نموذج الخطاب
    ("basic_salary", "الراتب الأساسي", True),
    ("total_salary", "إجمالي الراتب", True),
    ("salary_words", "الراتب كتابةً", True),
]

VARIABLE_KEYS = {v[0] for v in VARIABLES}
SALARY_KEYS = {v[0] for v in VARIABLES if v[2]}

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def validate_body(body):
    """
    يتحقّق أن كل متغيّرٍ في النصّ معلَن.

    فمتغيّرٌ مجهول يبقى ظاهرًا في الخطاب المطبوع — «{{الراتب}}»
    في يد الموظف.
    """
    unknown = set(_PLACEHOLDER.findall(body or "")) - VARIABLE_KEYS
    if unknown:
        raise LetterError(
            "متغيّرات غير معروفة: " + "، ".join(sorted(unknown)))
    return True


def _hijri(gregorian):
    """
    التاريخ الهجريّ — **بمكتبةٍ دقيقة أو فراغ**.

    ⚠️ ولا يُقرَّب: تاريخٌ خاطئ في خطابٍ رسميّ أسوأ من غيابه.
    فمن أراده يضيف `hijri-converter` وتعمل الدالّة تلقائيًّا.
    """
    try:
        from hijri_converter import Gregorian
    except ImportError:
        return ""
    try:
        h = Gregorian(gregorian.year, gregorian.month,
                      gregorian.day).to_hijri()
        return f"{h.year}/{h.month:02d}/{h.day:02d}هـ"
    except Exception:            # noqa: BLE001
        return ""


def _num_to_words_ar(amount):
    """
    المبلغ كتابةً — والخطاب الرسميّ يذكره رقمًا وكتابةً.

    تقريبٌ عمليّ: الآحاد والعشرات والمئات والآلاف، وما فوقها
    يُكتب رقمًا. فالرواتب لا تبلغ الملايين.
    """
    ones = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة",
            "سبعة", "ثمانية", "تسعة", "عشرة", "أحد عشر", "اثنا عشر",
            "ثلاثة عشر", "أربعة عشر", "خمسة عشر", "ستة عشر",
            "سبعة عشر", "ثمانية عشر", "تسعة عشر"]
    tens = ["", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون",
            "سبعون", "ثمانون", "تسعون"]
    hundreds = ["", "مئة", "مئتان", "ثلاثمئة", "أربعمئة", "خمسمئة",
                "ستمئة", "سبعمئة", "ثمانمئة", "تسعمئة"]

    def under_thousand(n):
        parts = []
        if n >= 100:
            parts.append(hundreds[n // 100])
            n %= 100
        if n >= 20:
            u, t = n % 10, n // 10
            parts.append((ones[u] + " و" + tens[t]) if u else tens[t])
        elif n:
            parts.append(ones[n])
        return " و".join(p for p in parts if p)

    try:
        n = int(Decimal(str(amount)))
    except (TypeError, ArithmeticError, ValueError):
        return ""
    if n <= 0:
        return "صفر"
    if n >= 1_000_000:
        return str(n)

    out = []
    if n >= 1000:
        th = n // 1000
        out.append("ألف" if th == 1 else
                   "ألفان" if th == 2 else
                   f"{under_thousand(th)} آلاف" if th < 11 else
                   f"{under_thousand(th)} ألفًا")
        n %= 1000
    if n:
        out.append(under_thousand(n))
    return " و".join(out)


def build_context(employment, *, letter_no="", addressee="",
                  include_salary=False):
    """
    قيم المتغيّرات لهذا الموظف.

    ⚠️ **والراتب لا يُحسب إلا بطلبه** — فبناؤه دائمًا يجعله في
    السياق، وسهوٌ واحد يطبعه في خطابٍ لم يُطلب فيه.
    """
    from apps.employees.models import SalaryStructure
    from apps.payroll.models import ComponentType

    p = employment.person
    comp = employment.company
    today = date.today()

    years = (today - employment.service_start_date).days // 365 \
        if employment.service_start_date else 0

    ctx = {
        "employee_name": p.display_name,
        "employee_no": employment.employee_no,
        "id_number": p.id_number or "",
        "nationality": p.nationality_code or "",
        "job_title": getattr(employment.job_title, "name_ar", "") or "",
        "department": getattr(employment.department, "name_ar", "") or "",
        "branch": getattr(employment.branch, "name_ar", "") or "",
        "join_date": str(employment.join_date or ""),
        "service_years": str(years),
        "contract_type": employment.get_contract_type_display()
        if employment.contract_type else "",
        "company_name": comp.legal_name_ar,
        "company_cr": getattr(comp, "cr_number", "") or "",
        "today": str(today),
        "today_hijri": _hijri(today),
        "letter_no": letter_no,
        "addressee": addressee or "من يهمّه الأمر",
    }

    if include_salary:
        st = (SalaryStructure.objects
              .filter(employment=employment, effective_to__isnull=True)
              .order_by("-effective_from").first())
        basic = total = Decimal("0")
        if st:
            for c, amount in st.as_lines():
                if c.component_type != ComponentType.EARNING:
                    continue
                total += Decimal(amount)
                if c.code == "BASIC":
                    basic = Decimal(amount)
        ctx["basic_salary"] = f"{basic:,.2f}"
        ctx["total_salary"] = f"{total:,.2f}"
        ctx["salary_words"] = _num_to_words_ar(total) + " ريالًا سعوديًّا"
    else:
        # ⚠️ الفراغ لا الحذف: متغيّرٌ مفقود يبقى ظاهرًا في النصّ
        for k in SALARY_KEYS:
            ctx[k] = "—"

    return ctx


def render(body, context):
    """يملأ المتغيّرات — والمجهول يصير فراغًا لا يبقى ظاهرًا."""
    def sub(m):
        return str(context.get(m.group(1), ""))
    return _PLACEHOLDER.sub(sub, body or "")


def _next_letter_no(company_id):
    """رقم الخطاب — أقصى مستعمل + ١ (كنمط ق-112)."""
    from apps.core.models import IssuedLetter

    year = date.today().year
    prefix = f"LTR-{year}-"
    last = (IssuedLetter.objects
            .filter(company_id=company_id, letter_no__startswith=prefix)
            .order_by("-letter_no").values_list("letter_no", flat=True)
            .first())
    n = int(last.rsplit("-", 1)[-1]) if last else 0
    return f"{prefix}{n + 1:05d}"


@transaction.atomic
def issue(*, template, employment, addressee="", include_salary=False,
          request_id=None, issued_by_person_id=None):
    """
    يُصدر خطابًا من قالبه — **بنصٍّ مجمَّد**.

    فتعديل القالب بعده لا يغيّر ما بيد الموظف، ومن راجع بعد سنة
    يرى ما صدر فعلًا.
    """
    from apps.core.models import IssuedLetter

    if not template.is_active:
        raise LetterError("القالب معطَّل")

    # ⚠️ الراتب بطلب صاحبه **وبإذن القالب** معًا
    show_salary = bool(include_salary and template.includes_salary)

    letter_no = _next_letter_no(employment.company_id)
    ctx = build_context(employment, letter_no=letter_no,
                        addressee=addressee,
                        include_salary=show_salary)

    today = date.today()
    return IssuedLetter.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        template=template, employment=employment,
        request_id=request_id, letter_no=letter_no,
        heading_ar=render(template.heading_ar, ctx),
        addressee_ar=ctx["addressee"],
        body_ar=render(template.body_ar, ctx),
        issued_on=today,
        valid_until=(today + timedelta(days=template.valid_days)
                     if template.valid_days else None),
        issued_by_person_id=issued_by_person_id)
