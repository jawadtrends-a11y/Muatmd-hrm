"""
عرض القوالب — يختار القالب بلغة المستقبل لا لغة المُرسِل.

ترتيب البحث: قالب الحساب بلغة المستقبل ← القالب الافتراضي بلغته
← القالب الافتراضي بالعربية. الفشل الصامت ممنوع.
"""
import re

from apps.notifications.models import NotificationTemplate

VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
FALLBACK_LOCALE = "ar"


class TemplateNotFound(LookupError):
    pass


def _lookup(account_id, event_key, channel, locale):
    """قالب الحساب أولًا، ثم الافتراضي."""
    return (
        NotificationTemplate.objects.filter(
            account_id=account_id, event_key=event_key,
            channel=channel, locale=locale).first()
        or NotificationTemplate.objects.filter(
            account__isnull=True, event_key=event_key,
            channel=channel, locale=locale).first()
    )


def render(event_key: str, channel: str, locale: str,
           context: dict, account_id: int | None = None) -> dict:
    tpl = _lookup(account_id, event_key, channel, locale)
    if tpl is None and locale != FALLBACK_LOCALE:
        tpl = _lookup(account_id, event_key, channel, FALLBACK_LOCALE)
    if tpl is None:
        raise TemplateNotFound(
            f"لا قالب لـ{event_key}/{channel}/{locale} — "
            "كل حدث يجب أن يملك قوالب بالثلاث لغات"
        )

    def _sub(text):
        return VAR_RE.sub(
            lambda m: str(context.get(m.group(1), f"{{{{{m.group(1)}}}}}")),
            text or "",
        )

    return {"subject": _sub(tpl.subject), "body": _sub(tpl.body),
            "locale": tpl.locale}
