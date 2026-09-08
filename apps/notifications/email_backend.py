"""
إرسال البريد عبر واجهة Brevo (HTTPS) لا SMTP.

السبب: SMTP من الخادم يربط سمعة الإرسال بعنوان الخادم، فينكسر
البريد عند كل نقل. والواجهة لا تعرف الخادم أصلًا.

وهي واجهة جانغو قياسية: كل send_mail و EmailMultiAlternatives
يمرّ عليها بلا تعديل، وتبديل المزوّد يمسّ هذا الملف وحده.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)

API_URL = "https://api.brevo.com/v3/smtp/email"
TIMEOUT = 15


class BrevoBackend(BaseEmailBackend):
    """fail_silently يُحترم — فلا يسقط طلب المستخدم لفشل بريد."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        key = getattr(settings, "BREVO_API_KEY", "")
        if not key:
            # لا مفتاح: نسجّل ولا نرمي — فالبيئة بلا مفتاح تعمل.
            log.warning("BREVO_API_KEY فارغ — لم يُرسل بريد")
            return 0

        sent = 0
        for msg in email_messages:
            try:
                self._send_one(msg, key)
                sent += 1
            except Exception as exc:                      # noqa: BLE001
                log.error("فشل إرسال بريد إلى %s: %s", msg.to, exc)
                if not self.fail_silently:
                    raise
        return sent

    # ── داخلي ──────────────────────────────────────────

    def _send_one(self, msg, key):
        html = self._html_of(msg)
        payload = {
            "sender": {
                "email": msg.from_email or settings.DEFAULT_FROM_EMAIL,
                "name": getattr(settings, "DEFAULT_FROM_NAME", "معتمد"),
            },
            "to": [{"email": a} for a in msg.to],
            "subject": msg.subject,
            "textContent": msg.body or " ",
        }
        if html:
            payload["htmlContent"] = html
        if msg.cc:
            payload["cc"] = [{"email": a} for a in msg.cc]
        if msg.bcc:
            payload["bcc"] = [{"email": a} for a in msg.bcc]

        # ردّ الموظف يصل الشركة لا الفراغ — تُمرَّر من المُرسِل.
        reply = (msg.extra_headers or {}).get("Reply-To")
        if reply:
            payload["replyTo"] = {"email": reply}

        req = urllib.request.Request(
            API_URL, data=json.dumps(payload).encode("utf-8"),
            headers={"api-key": key,
                     "content-type": "application/json",
                     "accept": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"Brevo {exc.code}: {detail}") from exc
        log.info("أُرسل بريد إلى %s — %s", msg.to, body[:120])
        return body

    @staticmethod
    def _html_of(msg):
        for content, mimetype in getattr(msg, "alternatives", []) or []:
            if mimetype == "text/html":
                return content
        return None
