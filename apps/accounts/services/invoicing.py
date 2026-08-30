"""
إصدار الفواتير الضريبية — عبر «محاسبة معتمد» حصرًا.

قرار المالك (محسوم):
  • الحساب والتحصيل في HRM (ميسر).
  • إصدار الفاتورة الضريبية في محاسبة معتمد وحده — لأن السوق
    السعودي لا يجيز إصدار فاتورة غير ضريبية، والمحاسبي هو النظام
    المتوافق مع ZATCA.
  • ممنوع توليد أي فاتورة داخل HRM. لا نموذج فاتورة هنا إطلاقًا.

التنفيذ الحالي: واجهة صورية تسجّل الطلب ولا ترسل.
التنفيذ القادم (السبرنت 17): استدعاء API محاسبة معتمد.
توقيع الدالة لن يتغيّر — لذلك لن يتأثر أي كود يناديها.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


class InvoicingError(Exception):
    pass


@dataclass(frozen=True)
class InvoiceRequest:
    """طلب إصدار فاتورة ضريبية — يُرسل للمحاسبي."""
    account_id: int
    company_id: int
    customer_name: str
    customer_vat_number: str
    period_start: str
    period_end: str
    line_description: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    payment_reference: str          # مرجع عملية ميسر


@dataclass(frozen=True)
class InvoiceResult:
    issued: bool
    invoice_number: str = ""
    invoice_url: str = ""
    zatca_uuid: str = ""
    error: str = ""


def issue_tax_invoice(req: InvoiceRequest) -> InvoiceResult:
    """
    يطلب إصدار فاتورة ضريبية من محاسبة معتمد.

    ⚠️ غير مُنفَّذ بعد. يُبنى في السبرنت 17 مع النشر.
    الضريبة (15%) يحتسبها المحاسبي لا نحن — مصدر حقيقة واحد.
    """
    logger.info(
        "طلب فاتورة ضريبية (غير مُرسَل — الربط قيد البناء): "
        "حساب=%s شركة=%s مبلغ=%s مرجع=%s",
        req.account_id, req.company_id, req.subtotal, req.payment_reference,
    )
    return InvoiceResult(
        issued=False,
        error="الربط مع محاسبة معتمد يُبنى في السبرنت 17",
    )


def is_invoicing_ready() -> bool:
    """يصير True عند بناء الربط — تستخدمه الاختبارات والواجهة."""
    return False
