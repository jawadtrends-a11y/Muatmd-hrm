"""
خدمة الدفع — تربط الفواتير بميسر (ق-47، ق-48).

المسار: إنشاء عملية ← تحويل العميل لصفحة ميسر ← العودة ←
التحقق من الحالة الفعلية لدى ميسر لا من معطيات العودة.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models_billing_v2 import (
    AccountSubscription, Invoice, InvoiceStatus, Payment, PaymentStatus,
    SavedCard,
)
from apps.accounts.services.payments import moyasar

ZERO = Decimal("0")


class PaymentError(Exception):
    pass


class PaymentThrottled(PaymentError):
    """محاولات فاشلة متتالية — مهلة حماية (ق-48)."""

    def __init__(self, minutes_left):
        self.minutes_left = minutes_left
        super().__init__(
            f"تجاوزت عدد المحاولات — أعد المحاولة بعد {minutes_left} دقيقة")


# ══════════ الحماية من الضغط المتكرر (ق-48) ══════════

def check_throttle(invoice):
    """
    ثلاث محاولات فاشلة متتالية تمنع الدفع ست ساعات.

    الهدف الحماية من الضغط المتكرر لا منع العميل — تُفتح تلقائيًا.
    """
    from apps.accounts.models_platform import get_settings
    ps = get_settings()

    window = timezone.now() - timedelta(hours=ps.manual_retry_cooldown_hours)
    recent = list(Payment.objects.filter(
        invoice=invoice, created_at__gte=window,
        is_recurring=False).order_by("-created_at")[:ps.manual_retry_limit])

    if len(recent) < ps.manual_retry_limit:
        return
    if any(p.status == PaymentStatus.PAID for p in recent):
        return
    if not all(p.status == PaymentStatus.FAILED for p in recent):
        return

    oldest = recent[-1].created_at
    unblock = oldest + timedelta(hours=ps.manual_retry_cooldown_hours)
    left = int((unblock - timezone.now()).total_seconds() / 60)
    if left > 0:
        raise PaymentThrottled(left)


# ══════════ إنشاء عملية دفع ══════════

@transaction.atomic
def start_payment(*, invoice, source, save_card=False, callback_url=None):
    """
    ينشئ عملية دفع لفاتورة.

    source من الواجهة — بيانات البطاقة لا تمر بخادمنا (ق-47):
    الواجهة تنشئ الرمز مباشرة مع ميسر ثم ترسله هنا.
    """
    from django.conf import settings

    if invoice.status == InvoiceStatus.PAID:
        raise PaymentError("الفاتورة مدفوعة بالفعل")
    if invoice.status == InvoiceStatus.CANCELLED:
        raise PaymentError("الفاتورة ملغاة")
    if invoice.total <= 0:
        raise PaymentError("مبلغ الفاتورة صفر")

    check_throttle(invoice)

    payment = Payment.objects.create(
        account_id=invoice.account_id, invoice=invoice,
        amount=invoice.total, status=PaymentStatus.INITIATED)

    try:
        data = moyasar.create_payment(
            amount=invoice.total,
            description=f"اشتراك معتمد HRM — {invoice.invoice_no}",
            callback_url=(callback_url or settings.MOYASAR_CALLBACK_URL),
            source=source,
            metadata={
                "invoice_id": invoice.id,
                "invoice_no": invoice.invoice_no,
                "account_id": invoice.account_id,
                "payment_id": payment.id,
                "save_card": "1" if save_card else "0",
            })
    except moyasar.MoyasarError as e:
        payment.status = PaymentStatus.FAILED
        payment.failure_message = str(e)[:300]
        payment.raw_response = e.response or {}
        payment.save()
        raise PaymentError(str(e))

    _apply_response(payment, data)
    return payment, data.get("source", {}).get("transaction_url", "")


def _apply_response(payment, data):
    """يحدّث عملية الدفع من رد ميسر."""
    parsed = moyasar.parse_payment(data)
    payment.moyasar_payment_id = parsed["moyasar_payment_id"]
    payment.moyasar_status = parsed["moyasar_status"]
    payment.source_type = parsed["source_type"]
    payment.card_brand = parsed["card_brand"]
    payment.card_last_four = parsed["card_last_four"]
    payment.raw_response = data

    if moyasar.is_paid(data):
        payment.status = PaymentStatus.PAID
        payment.paid_at = timezone.now()
    elif data.get("status") in ("failed", "authorized"):
        if data.get("status") == "failed":
            payment.status = PaymentStatus.FAILED
            payment.failure_message = parsed["failure_message"][:300]
    payment.save()
    return payment


# ══════════ معالجة العودة والـwebhook ══════════

@transaction.atomic
def confirm_payment(payment_id_or_moyasar_id):
    """
    يتحقق من حالة العملية لدى ميسر ويحدّث النظام.

    ⚠️ لا نثق بمعطيات العودة من المتصفح — نسأل ميسر مباشرةً،
    فمعطيات الرابط قابلة للتزوير.
    """
    payment = Payment.objects.filter(
        moyasar_payment_id=payment_id_or_moyasar_id).first()
    if payment is None:
        payment = Payment.objects.filter(
            id=payment_id_or_moyasar_id).first()
    if payment is None:
        raise PaymentError("عملية الدفع غير موجودة")

    if not payment.moyasar_payment_id:
        raise PaymentError("العملية بلا معرّف لدى ميسر")

    data = moyasar.fetch_payment(payment.moyasar_payment_id)
    _apply_response(payment, data)

    if payment.status == PaymentStatus.PAID:
        _on_paid(payment, data)

    return payment


def _on_paid(payment, data):
    """يُنفَّذ عند تأكيد الدفع: سداد الفاتورة وحفظ البطاقة."""
    from apps.accounts.services.billing_v2 import mark_paid

    mark_paid(payment.invoice, note=f"دفع إلكتروني {payment.moyasar_payment_id}")

    meta = data.get("metadata") or {}
    if meta.get("save_card") == "1":
        token = (data.get("source") or {}).get("token", "")
        if token:
            save_card_token(account_id=payment.account_id, token=token,
                            data=data)


# ══════════ البطاقات المحفوظة ══════════

@transaction.atomic
def save_card_token(*, account_id, token, data=None):
    """
    يحفظ رمز البطاقة للتجديد التلقائي.

    ⚠️ لا رقم بطاقة ولا CVC — الرمز فقط.
    """
    source = (data or {}).get("source", {})
    card, created = SavedCard.objects.get_or_create(
        moyasar_token=token,
        defaults={
            "account_id": account_id,
            "brand": source.get("company", "") or source.get("type", ""),
            "last_four": (source.get("number", "") or "")[-4:],
            "holder_name": source.get("name", ""),
        })
    if created:
        SavedCard.objects.filter(
            account_id=account_id).exclude(id=card.id).update(is_default=False)
    return card


# ══════════ التجديد التلقائي (ق-48) ══════════

@transaction.atomic
def charge_saved_card(*, invoice, card, callback_url=None):
    """
    يشحن بطاقة محفوظة — بلا تدخّل العميل.

    يُستدعى من مهمة التجديد المجدولة.
    """
    from django.conf import settings

    if not card.is_active:
        raise PaymentError("البطاقة غير نشطة")

    payment = Payment.objects.create(
        account_id=invoice.account_id, invoice=invoice,
        amount=invoice.total, status=PaymentStatus.INITIATED,
        is_recurring=True, source_type="token")

    try:
        data = moyasar.charge_token(
            token=card.moyasar_token, amount=invoice.total,
            description=f"تجديد اشتراك — {invoice.invoice_no}",
            callback_url=(callback_url or settings.MOYASAR_CALLBACK_URL),
            metadata={
                "invoice_id": invoice.id,
                "invoice_no": invoice.invoice_no,
                "account_id": invoice.account_id,
                "payment_id": payment.id,
                "recurring": "1",
            })
    except moyasar.MoyasarError as e:
        payment.status = PaymentStatus.FAILED
        payment.failure_message = str(e)[:300]
        payment.raw_response = e.response or {}
        payment.save()
        return payment

    _apply_response(payment, data)
    if payment.status == PaymentStatus.PAID:
        _on_paid(payment, data)
        card.last_used_at = timezone.now()
        card.save(update_fields=["last_used_at", "updated_at"])

    return payment


# ══════════ الاسترداد ══════════

@transaction.atomic
def refund(*, payment, amount=None, reason=""):
    """استرداد كلي أو جزئي."""
    if payment.status != PaymentStatus.PAID:
        raise PaymentError("لا يُسترد إلا المدفوع")

    try:
        data = moyasar.refund_payment(payment.moyasar_payment_id, amount)
    except moyasar.MoyasarError as e:
        raise PaymentError(f"تعذّر الاسترداد: {e}")

    payment.status = PaymentStatus.REFUNDED
    payment.raw_response = data
    payment.failure_message = reason[:300]
    payment.save()

    if amount is None or Decimal(str(amount)) >= payment.amount:
        payment.invoice.status = InvoiceStatus.REFUNDED
        payment.invoice.save(update_fields=["status", "updated_at"])

    return payment
