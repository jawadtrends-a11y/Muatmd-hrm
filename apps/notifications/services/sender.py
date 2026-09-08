"""
من يُرسل البريد، وإلى أين يعود ردّه.

ق-99: `Reply-To` لكل شركة بريدها — فالنظام متعدّد المستأجرين،
وردّ موظف شركةٍ لا يجوز أن يصل شركة أخرى. وحين لا بريد، يسقط
الحقل ولا يُرسَل خاويًا (فالبريد الفارغ يكسر بعض العملاء).

وهي هنا في موضع واحد تستعملها الدعوة والإعلانات والتذكير — فلو
تغيّرت القاعدة تغيّرت مرّة لا ثلاثًا.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

log = logging.getLogger(__name__)


def reply_to_for(company_id=None) -> str:
    """بريد ردّ الشركة، أو فراغ إن لم يُضبط."""
    if not company_id:
        return ""
    from apps.accounts.models import Company

    email = (Company.objects.filter(id=company_id)
             .values_list("contact_email", flat=True).first() or "")
    return email.strip()


def send_email(*, to, subject, text, html=None, company_id=None,
               reply_to=None, attachments=None, fail_silently=True) -> bool:
    """
    إرسال رسالة واحدة. يرجع True إن قبِلها المزوّد.

    fail_silently افتراضيًّا True: فشل البريد لا يُسقط طلب المستخدم
    ولا يمنع إنشاء الدعوة — والرابط يُنسخ يدويًّا على كل حال.
    """
    recipients = [to] if isinstance(to, str) else list(to)
    recipients = [a for a in recipients if a and "@" in a]
    if not recipients:
        return False

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    if html:
        msg.attach_alternative(html, "text/html")

    # المرفقات: (اسم، بايتات، نوع) — تُرفق في البريد كما في النظام،
    # فمن يقرأ التعميم في بريده لا يحتاج فتح النظام ليرى ملفّه.
    for name, content, mimetype in (attachments or []):
        msg.attach(name, content, mimetype)

    rt = reply_to if reply_to is not None else reply_to_for(company_id)
    if rt:
        msg.extra_headers = {"Reply-To": rt}

    try:
        return bool(msg.send(fail_silently=False))
    except Exception as exc:                              # noqa: BLE001
        log.error("فشل بريد إلى %s: %s", recipients, exc)
        if not fail_silently:
            raise
        return False
