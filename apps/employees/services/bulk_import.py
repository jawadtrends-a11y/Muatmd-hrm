"""
الاستيراد الجماعيّ للموظفين (ق-154).

**شركةٌ بمئة موظف، أو منتقلةٌ من نظامٍ آخر** — لا يُعقل إدخالهم
واحدًا واحدًا (قرار جواد).

⚠️⚠️ **والخطأ في سطرٍ يوقف الملفّ كلّه**: فاستيرادٌ نصفُه ناقصٌ
**أسوأ من لا شيء** — والشركة لا تعرف من دخل ومن بقي.

⚠️ **والمعاينة قبل التنفيذ دائمًا**: فمن يرى ما سيقع يُصلحه قبل
أن يقع.
"""
import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction

logger = logging.getLogger(__name__)


class ImportError_(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


#: أعمدة القالب — **الإلزاميّ أوّلًا**
#
# ⚠️ والعنوان عربيٌّ لأن من يملأ الملفّ موظفُ موارد لا مبرمج.
COLUMNS = [
    ("employee_no", "الرقم الوظيفي", True,
     "1001 — ولا يتكرّر"),
    ("first_name_ar", "الاسم الأول", True, "محمد"),
    ("family_name_ar", "اسم العائلة", True, "العتيبي"),
    ("gender", "الجنس", True, "male أو female"),
    ("nationality_code", "الجنسية", True, "SA · EG · PK"),
    ("id_type", "نوع الهوية", True,
     "national_id للسعوديّ · iqama للمقيم"),
    ("id_number", "رقم الهوية", True, "1012345678"),
    ("join_date", "تاريخ المباشرة", True, "2026-01-15"),
    ("mobile", "الجوال", False, "0501234567"),
    ("email", "البريد", False, "name@company.com"),
    ("department", "الإدارة", False, "المالية — باسمها"),
    ("job_title", "المسمى الوظيفي", False, "محاسب"),
    ("basic_salary", "الراتب الأساسي", False, "8000"),
    ("housing_allowance", "بدل السكن", False, "2000"),
    ("transport_allowance", "بدل النقل", False, "800"),
    ("iban", "الآيبان", False, "SA0380000000608010167519"),
]

#: بنود الأجر التي تُستورَد — **ورمزُها في النظام**
SALARY_MAP = {
    "basic_salary": "BASIC",
    "housing_allowance": "HOUSING",
    "transport_allowance": "TRANSPORT",
}


def template_csv():
    """
    قالبٌ فارغٌ بعناوينه ومثالٍ واحد.

    ⚠️ **والمثال سطرٌ يُحذف** — فمن يملأ يرى الصيغة المطلوبة.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([c[1] for c in COLUMNS])
    w.writerow([c[3] for c in COLUMNS])
    return buf.getvalue()


def _parse_date(v):
    v = (v or "").strip()
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"تاريخ غير مفهوم: {v}")


def _parse_amount(v):
    v = (v or "").strip().replace(",", "")
    if not v:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        raise ValueError(f"مبلغ غير صالح: {v}")


def parse_file(content, company):
    """
    يقرأ الملفّ ويفحصه **سطرًا سطرًا** — بلا إنشاء.

    ⚠️ **ويُرجع كل الأخطاء لا أوّلها**: فمن يُصلح خطأً ثم يرفع
    ليكتشف ثانيًا **يكرّر الرفع عشرًا**.
    """
    from apps.employees.models import Employment, Person
    from apps.organization.models import Department, JobTitle

    if isinstance(content, bytes):
        for enc in ("utf-8-sig", "utf-8", "cp1256"):
            try:
                content = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ImportError_("تعذّر قراءة الملفّ — احفظه بترميز UTF-8")

    reader = csv.reader(io.StringIO(content))
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if len(rows) < 2:
        raise ImportError_("الملفّ فارغ — عبّئ صفًّا واحدًا على الأقلّ")

    headers = [h.strip() for h in rows[0]]
    by_label = {c[1]: c[0] for c in COLUMNS}
    mapping = {}
    for i, h in enumerate(headers):
        if h in by_label:
            mapping[by_label[h]] = i

    missing_cols = [c[1] for c in COLUMNS
                    if c[2] and c[0] not in mapping]
    if missing_cols:
        raise ImportError_(
            "أعمدة إلزامية ناقصة: " + "، ".join(missing_cols))

    # مراجع الشركة — تُقرأ مرّةً لا لكل سطر
    depts = {d.name_ar.strip(): d for d in
             Department.objects.filter(company=company)}
    titles = {t.name_ar.strip(): t for t in
              JobTitle.objects.filter(company=company)}
    existing_nos = set(Employment.objects.filter(
        company=company).values_list("employee_no", flat=True))
    existing_ids = set(Person.objects.filter(
        account=company.account).values_list("id_number", flat=True))

    parsed, errors = [], []
    seen_nos, seen_ids = set(), set()

    for n, raw in enumerate(rows[1:], start=2):
        def cell(key):
            i = mapping.get(key)
            return (raw[i].strip() if i is not None and i < len(raw)
                    else "")

        # ⚠️ سطر المثال في القالب يُتخطّى بلا خطأ
        if cell("employee_no").startswith("1001 —"):
            continue

        rec, row_errors = {"_row": n}, []

        for key, label, required, _ in COLUMNS:
            v = cell(key)
            if required and not v:
                row_errors.append(f"«{label}» مطلوب")
            rec[key] = v

        # ── تكرارٌ داخل الملفّ أو في النظام ──
        no = rec.get("employee_no")
        if no:
            if no in seen_nos:
                row_errors.append(f"الرقم الوظيفي {no} مكرّرٌ في الملفّ")
            elif no in existing_nos:
                row_errors.append(f"الرقم الوظيفي {no} مستعملٌ في النظام")
            seen_nos.add(no)

        idn = rec.get("id_number")
        if idn:
            if idn in seen_ids:
                row_errors.append("رقم الهوية مكرّرٌ في الملفّ")
            elif idn in existing_ids:
                row_errors.append("رقم الهوية مسجَّلٌ في النظام")
            seen_ids.add(idn)

        if rec.get("gender") not in ("male", "female", ""):
            row_errors.append("الجنس: male أو female")
        if rec.get("id_type") not in ("national_id", "iqama", ""):
            row_errors.append("نوع الهوية: national_id أو iqama")

        try:
            rec["join_date"] = _parse_date(rec.get("join_date"))
        except ValueError as e:
            row_errors.append(str(e))

        for k in SALARY_MAP:
            try:
                rec[k] = _parse_amount(rec.get(k))
            except ValueError as e:
                row_errors.append(str(e))

        # ── المراجع: تُطابق بالاسم، وغير الموجود خطأ ──
        #
        # ⚠️ **فإنشاؤها ضمنًا يملأ الشركة بإداراتٍ بأخطاءٍ إملائية**
        d = rec.get("department")
        if d and d not in depts:
            row_errors.append(f"الإدارة «{d}» غير معرَّفة")
        t = rec.get("job_title")
        if t and t not in titles:
            row_errors.append(f"المسمى «{t}» غير معرَّف")

        if row_errors:
            errors.append({"row": n,
                           "employee_no": no or "—",
                           "errors": row_errors})
        else:
            parsed.append(rec)

    return {
        "rows": parsed,
        "errors": errors,
        "total": len(parsed) + len(errors),
        "valid": len(parsed),
        "invalid": len(errors),
        # ⚠️ **ولا استيراد بخطأ واحد** (قرار جواد)
        "can_import": not errors and bool(parsed),
    }


@transaction.atomic
def execute(*, company, parsed_rows, by_person_id=None):
    """
    يُنشئ الموظفين — **في معاملةٍ واحدة**.

    ⚠️ **فإخفاق سطرٍ يُرجع الجميع**: وإلا بقي نصفُ الملفّ في
    النظام ولا يُعرف أين توقّف.
    """
    from apps.employees.services.hiring import (
        create_employment, create_person)
    from apps.organization.models import Department, JobTitle
    from apps.payroll.models import PayComponent

    if not parsed_rows:
        raise ImportError_("لا صفوف للاستيراد")

    comps = {c.code: c for c in PayComponent.objects.filter(
        company=company)}
    depts = {d.name_ar.strip(): d for d in
             Department.objects.filter(company=company)}
    titles = {t.name_ar.strip(): t for t in
              JobTitle.objects.filter(company=company)}

    created = []
    for rec in parsed_rows:
        try:
            person, _ = create_person(
                account=company.account,
                first_name_ar=rec["first_name_ar"],
                family_name_ar=rec["family_name_ar"],
                gender=rec["gender"],
                nationality_code=rec["nationality_code"],
                id_type=rec["id_type"], id_number=rec["id_number"],
                mobile=rec.get("mobile", ""),
                email=rec.get("email", ""),
                # ⚠️ تحذير التشابه يُتجاوز في الاستيراد الجماعيّ:
                # فمئة موظفٍ فيهم متشابهو الأسماء بالضرورة.
                force=True)

            lines = []
            for key, code in SALARY_MAP.items():
                amt = rec.get(key)
                if amt and code in comps:
                    lines.append((comps[code], amt))

            extra = {}
            if rec.get("department"):
                extra["department"] = depts[rec["department"]]
            if rec.get("job_title"):
                extra["job_title"] = titles[rec["job_title"]]

            emp, _, _ = create_employment(
                person=person, company=company,
                employee_no=rec["employee_no"],
                join_date=rec["join_date"],
                salary_lines=lines or None,
                iban=rec.get("iban", ""), **extra)
            created.append(emp.employee_no)
        except Exception as e:          # noqa: BLE001
            # ⚠️ **والمعاملة تُرجع الجميع** — فالرسالة تُسمّي السطر
            raise ImportError_(
                f"توقّف الاستيراد عند السطر {rec['_row']} "
                f"({rec.get('employee_no')}): {e}")

    logger.info("استُورد %s موظفًا للشركة %s", len(created), company.id)
    return {"created": len(created), "employee_nos": created}
