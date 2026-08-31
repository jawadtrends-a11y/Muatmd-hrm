"""
عميل بوابة ميسر (ق-47).

⚠️ لا تُحفظ بيانات بطاقة أبدًا — الرمز فقط، وميسر تحتفظ بالباقي.
التوكنة تتطلب تفعيل الميزة للتاجر من ميسر.
"""
import logging
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger("muatmd.payments")

BASE_URL = "https://api.moyasar.com/v1"
TIMEOUT = 30


class MoyasarError(Exception):
    """خطأ من البوابة — يحمل الرد كاملًا للتشخيص."""

    def __init__(self, message, response=None, status_code=None):
        self.response = response or {}
        self.status_code = status_code
        super().__init__(message)


def _secret_key():
    key = getattr(settings, "MOYASAR_SECRET_KEY", "")
    if not key:
        raise MoyasarError("مفتاح ميسر السري غير مضبوط")
    return key


def is_test_mode():
    return getattr(settings, "MOYASAR_MODE", "test") == "test"


def to_halalas(amount):
    """ميسر تتعامل بالهللات لا الريالات — 100.50 ريال = 10050."""
    return int(Decimal(str(amount)) * 100)


def from_halalas(halalas):
    return Decimal(halalas) / Decimal("100")


def _request(method, path, **kwargs):
    """
    نداء البوابة.

    الأخطاء تُرفع لا تُبتلع — فشل الدفع يجب أن يوقف العملية،
    بخلاف سجل التدقيق.
    """
    url = f"{BASE_URL}{path}"
    try:
        r = requests.request(
            method, url, auth=(_secret_key(), ""), timeout=TIMEOUT, **kwargs)
    except requests.RequestException as e:
        logger.error("moyasar_network_error", extra={
            "path": path, "error": str(e)})
        raise MoyasarError(f"تعذّر الاتصال ببوابة الدفع: {e}")

    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:500]}

    if r.status_code >= 400:
        message = data.get("message") or data.get("type") or "خطأ غير معروف"
        logger.warning("moyasar_error", extra={
            "path": path, "status": r.status_code, "message": message})
        raise MoyasarError(f"ميسر: {message}", response=data,
                           status_code=r.status_code)

    return data


# ══════════ المدفوعات ══════════

def create_payment(*, amount, description, callback_url, source,
                   metadata=None):
    """
    ينشئ عملية دفع.

    source: {"type": "creditcard", ...} أو {"type": "token", "token": "..."}
    metadata: بيانات وصفية تُرجع في webhook — نضع فيها معرّف الفاتورة.
    """
    payload = {
        "amount": to_halalas(amount),
        "currency": "SAR",
        "description": description[:255],
        "callback_url": callback_url,
        "source": source,
    }
    if metadata:
        payload["metadata"] = {k: str(v) for k, v in metadata.items()}
    return _request("POST", "/payments", json=payload)


def charge_token(*, token, amount, description, callback_url,
                 metadata=None):
    """
    شحن بطاقة محفوظة — أساس التجديد التلقائي.

    لا يحتاج تدخّل العميل: البطاقة محفوظة كرمز لدى ميسر.
    """
    return create_payment(
        amount=amount, description=description, callback_url=callback_url,
        source={"type": "token", "token": token}, metadata=metadata)


def fetch_payment(payment_id):
    return _request("GET", f"/payments/{payment_id}")


def refund_payment(payment_id, amount=None):
    """استرداد كلي أو جزئي."""
    payload = {"amount": to_halalas(amount)} if amount else {}
    return _request("POST", f"/payments/{payment_id}/refund", json=payload)


def void_payment(payment_id):
    """إلغاء عملية مصرَّح بها ولم تُحصَّل بعد."""
    return _request("POST", f"/payments/{payment_id}/void")


# ══════════ الرموز ══════════

def fetch_token(token_id):
    """
    بيانات بطاقة محفوظة — بلا رقم البطاقة.

    يرجع: النوع، آخر أربعة، الشهر والسنة، الحالة.
    """
    return _request("GET", f"/tokens/{token_id}")


# ══════════ الأدوات ══════════

def parse_payment(data):
    """يحوّل رد ميسر لبنية موحّدة تُحفظ في نموذج الدفع."""
    source = data.get("source") or {}
    return {
        "moyasar_payment_id": data.get("id", ""),
        "moyasar_status": data.get("status", ""),
        "amount": from_halalas(data.get("amount", 0)),
        "source_type": source.get("type", ""),
        "card_brand": source.get("company", "") or source.get("type", ""),
        "card_last_four": (source.get("number", "") or "")[-4:],
        "token": source.get("token", ""),
        "failure_message": data.get("source", {}).get("message", ""),
        "transaction_url": source.get("transaction_url", ""),
    }


def is_paid(data):
    return data.get("status") == "paid"


def needs_action(data):
    """
    يحتاج تدخّل العميل — التحقق ثلاثي الأبعاد مثلًا.

    الحالة initiated تعني أن على العميل إكمال خطوة في transaction_url.
    """
    return data.get("status") == "initiated"
