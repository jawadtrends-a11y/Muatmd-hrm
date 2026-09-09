"""
إصدار الفاتورة الزكاتية من نظام معتمد المحاسبي (ق-111).

**HRM لا يُصدر فواتير ضريبية**: يستقبل الدفع، ثم يطلب من المحاسبي
إصدار الفاتورة — فهو نظام الفوترة المعتمد لدى الهيئة.

⚠️ **البيانات النظامية إلزامية** (قرار جواد): من لم يُكمل رقمه
الضريبيّ وعنوانه الوطنيّ لا تصدر فاتورته تلقائيًّا — تُعلَّق حتى
يُكمل. فالفاتورة الناقصة ترفضها الهيئة، وتصحيحها أسوأ من تأجيلها.

وفشل الإصدار **لا يُلغي الدفع ولا الاشتراك**: العميل دفع وحقّه
ثابت، والفاتورة تُعاد محاولتها.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)
TIMEOUT = 20


class InvoiceSkipped(Exception):
    """سببٌ معروف يمنع الإصدار — يُعرض ولا يُسجَّل خطأً."""


class InvoiceFailed(Exception):
    """فشل تقنيّ — يُسجَّل وتُعاد المحاولة."""


def readiness(company):
    """(جاهز، الناقص) — ما يمنع إصدار الفاتورة الضريبية."""
    missing = []
    checks = (
        ("vat_number", "الرقم الضريبي"),
        ("building_number", "رقم المبنى"),
        ("street", "الشارع"),
        ("district", "الحي"),
        ("city", "المدينة"),
        ("postal_code", "الرمز البريدي"),
    )
    for field, label in checks:
        if not (getattr(company, field, "") or "").strip():
            missing.append(label)
    if len((company.vat_number or "").strip()) not in (0, 15):
        missing.append("الرقم الضريبي (١٥ خانة)")
    return (not missing), missing


def issue_for_payment(payment):
    """
    يطلب من المحاسبي إصدار فاتورة لدفعةٍ ناجحة.

    يرجع dict بنتيجة الإصدار، أو يرفع InvoiceSkipped إن نقصت
    البيانات، أو InvoiceFailed إن تعذّر الاتصال.
    """
    from apps.accounts.models import Company

    # حاجزان: متغيّر البيئة **سقفٌ** لا يتجاوزه الزرّ، والزرّ قرار
    # تشغيليّ من اللوحة. فبيئة التطوير لا تُصدر فاتورة مهما ضُغط،
    # والإنتاج يُوقَف فورًا إن ظهر خلل — بلا نشرٍ ولا إعادة تشغيل.
    if not getattr(settings, "ACCOUNTING_INVOICE_ENABLED", False):
        raise InvoiceSkipped(
            "إصدار الفواتير مقفل في هذه البيئة")

    from apps.accounts.models_platform import get_settings

    ps = get_settings()
    if not getattr(ps, "accounting_enabled", False):
        raise InvoiceSkipped(
            "إصدار الفواتير معطَّل من لوحة المنصّة")

    key = getattr(settings, "ACCOUNTING_API_KEY", "")
    if not key:
        raise InvoiceSkipped("لم يُضبط مفتاح المحاسبي")

    invoice = payment.invoice
    if invoice is None:
        raise InvoiceSkipped("الدفعة بلا فاتورة داخلية")

    sub = invoice.account.subscriptions.first() if hasattr(
        invoice.account, "subscriptions") else None
    company = Company.objects.filter(
        account_id=invoice.account_id, is_active=True).order_by("id").first()
    if company is None:
        raise InvoiceSkipped("لا شركة في هذا الحساب")

    ok, missing = readiness(company)
    if not ok:
        raise InvoiceSkipped("بيانات ناقصة: " + "، ".join(missing))

    employees = invoice.headcount or 1
    unit = (invoice.subtotal - invoice.setup_fee) / employees

    payload = {
        "customer_name": company.legal_name_ar,
        "customer_vat_number": company.vat_number.strip(),
        "customer_building_number": company.building_number.strip(),
        "customer_street": company.street.strip(),
        "customer_district": company.district.strip(),
        "customer_city": company.city.strip(),
        "customer_postal_code": company.postal_code.strip(),
        "plan_name": (sub.plan.name_ar if sub and sub.plan else "اشتراك"),
        "cycle_label": invoice.get_cycle_display(),
        "employees": int(employees),
        "unit_price": str(round(unit, 2)),
        "setup_fee": str(invoice.setup_fee or 0),
        # مرجعنا يمنع التكرار: إعادة المحاولة لا تُصدر فاتورتين
        "external_reference": invoice.invoice_no,
        "payment_method": "card",
        "customer_email": company.contact_email or "",
    }

    base = (getattr(ps, "accounting_api_url", "") or "").strip() \
        or settings.ACCOUNTING_API_URL
    url = f"{base.rstrip('/')}/subscriptions/invoices"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"X-API-Key": key, "Content-Type": "application/json"},
        method="POST")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 409:
            # لها فاتورة مسبقًا — ليست فشلًا
            log.info("فاتورة قائمة لـ%s", invoice.invoice_no)
            return {"duplicate": True, "detail": body}
        raise InvoiceFailed(f"المحاسبي {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise InvoiceFailed(f"تعذّر الاتصال بالمحاسبي: {exc}") from exc

    log.info("صدرت فاتورة زكاتية %s لـ%s",
             data.get("invoice_number"), invoice.invoice_no)
    return data
