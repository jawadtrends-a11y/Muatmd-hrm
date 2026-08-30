"""
مهام الإشعارات — تعمل على طابور realtime المعزول.

عزل الطوابير مقصود: تعليق مسير رواتب لا يوقف رسائل الإشعارات.
"""
import logging

from celery import shared_task
from django.utils import timezone

from apps.core.tasks import AccountTask
from apps.notifications.catalog import EVENTS_BY_KEY, MANDATORY_KEYS
from apps.notifications.models import (
    Channel, DeliveryStatus, Notification, NotificationDelivery,
    NotificationPreference,
)
from apps.notifications.renderer import TemplateNotFound, render

logger = logging.getLogger(__name__)


def _channel_allowed(account_id, person_id, event_key, channel) -> bool:
    """الأحداث الإلزامية لا تخضع لتفضيلات المستخدم."""
    if event_key in MANDATORY_KEYS:
        return True
    pref = NotificationPreference.objects.filter(
        person_id=person_id, event_key=event_key, channel=channel).first()
    return True if pref is None else pref.is_enabled


@shared_task(base=AccountTask, bind=True, max_retries=3)
def dispatch_notification(self, *, account_id, event_key, company_id=None,
                          context=None, actor_person_id=None, recipients=None,
                          **kwargs):
    """يوزّع الحدث على المستقبلين والقنوات."""
    spec = EVENTS_BY_KEY.get(event_key)
    if spec is None:
        logger.error("حدث غير مسجّل: %s", event_key)
        return {"error": "unknown_event"}

    context = context or {}
    recipients = recipients or []
    created = []

    for person_id in recipients:
        locale = context.get("recipient_locale", "ar")
        try:
            rendered = render(event_key, Channel.IN_APP, locale,
                              context, account_id)
        except TemplateNotFound as e:
            logger.error("قالب مفقود: %s", e)
            continue

        notif = Notification.objects.create(
            account_id=account_id, company_id=company_id,
            recipient_person_id=person_id, event_key=event_key,
            title=rendered["subject"] or spec.name_ar,
            body=rendered["body"], locale=rendered["locale"],
            payload=context, link_url=context.get("link_url", ""),
        )
        created.append(notif.id)

        for channel in spec.channels:
            if not _channel_allowed(account_id, person_id, event_key, channel):
                NotificationDelivery.objects.create(
                    account_id=account_id, notification=notif, channel=channel,
                    status=DeliveryStatus.SKIPPED,
                    error="معطّل في تفضيلات المستخدم")
                continue
            NotificationDelivery.objects.create(
                account_id=account_id, notification=notif, channel=channel,
                status=(DeliveryStatus.SENT if channel == Channel.IN_APP
                        else DeliveryStatus.PENDING),
                attempted_at=timezone.now() if channel == Channel.IN_APP else None,
            )

    return {"event": event_key, "notifications": created,
            "recipients": len(recipients)}
