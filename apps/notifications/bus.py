"""
ناقل الأحداث — نقطة الدخول الوحيدة.

    من الموديول:  emit("leave.approved", account_id=..., context={...})

الموديول لا يعرف: من المستقبل، بأي قناة، بأي لغة. المحرك يقرر.
هذا ما يمنع تكرار مسارات الإشعار في كل موديول.

راجع الوثيقة المعمارية (2) القسم 5.
"""
import logging

from apps.notifications.catalog import validate_event_key

logger = logging.getLogger(__name__)


def emit(event_key: str, *, account_id: int, company_id: int | None = None,
         context: dict | None = None, actor_person_id: int | None = None,
         recipients: list | None = None, sync: bool = False):
    """
    يُطلق حدثًا. الإرسال غير متزامن دائمًا — فشل مزوّد البريد
    لا يوقف اعتماد الإجازة.

    recipients: قائمة person_id صريحة. إن كانت None يحلّها المحرك
                من قواعد الحدث (يُبنى في السبرنت 6 مع الطلبات).
    sync: للاختبارات فقط — ينفّذ فورًا بلا طابور.
    """
    validate_event_key(event_key)

    payload = {
        "event_key": event_key,
        "account_id": account_id,
        "company_id": company_id,
        "context": context or {},
        "actor_person_id": actor_person_id,
        "recipients": recipients or [],
    }

    if sync:
        from apps.notifications.tasks import dispatch_notification
        return dispatch_notification(**payload)

    from apps.notifications.tasks import dispatch_notification
    dispatch_notification.apply_async(kwargs=payload, queue="realtime")
    return None
