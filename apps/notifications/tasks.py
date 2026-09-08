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


def _localized_context(context, locale):
    """
    يستبدل قيم المفاتيح بنظيراتها بلغة المستقبل.

    السياق يحمل title وtitle_en معًا؛ فمن لغته en يأخذ title_en
    مكان title. وما لا نظير له يبقى كما هو، وما كان نظيره فارغًا
    يرتدّ للأصل — فلا موظف يقرأ فراغًا.
    """
    if locale != "en":
        return context
    out = dict(context)
    for k, v in context.items():
        if k.endswith("_en") and str(v or "").strip():
            out[k[:-3]] = v
    return out


def _locale_of(person_id, fallback="ar"):
    from apps.employees.models import Person
    loc = (Person.objects.filter(id=person_id)
           .values_list("preferred_locale", flat=True).first())
    return loc or fallback


def _email_of(person_id):
    from apps.employees.models import Person
    return (Person.objects.filter(id=person_id)
            .values_list("email", flat=True).first() or "").strip()


def _deliver_email(*, account_id, company_id, notif, person_id,
                   event_key, locale, context):
    """
    إرسال فعليّ للبريد — كان الصفّ يُنشأ pending ويقف.

    وفشله لا يُسقط الإشعار داخل النظام: الموظف يراه في الجرس
    ولو لم يصله بريد.
    """
    from apps.notifications.services.sender import send_email

    to = _email_of(person_id)
    if not to:
        # ليست تخطّيًا بتفضيل المستخدم — بل تعذّرًا لغياب العنوان.
        # والتمييز مقصود: SKIPPED محجوزة لمن أوقف القناة بنفسه،
        # وحارس الأحداث الإلزامية يفحصها.
        return DeliveryStatus.FAILED, "لا بريد للموظف"
    try:
        r = render(event_key, Channel.EMAIL, locale, context, account_id)
    except TemplateNotFound:
        r = {"subject": notif.title, "body": notif.body}
    ok = send_email(
        to=to, subject=r["subject"] or notif.title,
        text=r["body"] or notif.body,
        html=context.get("html_body") or None,
        company_id=company_id,
        attachments=context.get("attachments") or None)
    return ((DeliveryStatus.SENT, "") if ok
            else (DeliveryStatus.FAILED, "تعذّر الإرسال"))


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
        # لغة المستقبل من ملفّه — لا لغة واحدة للجميع. فمن ضبط
        # الإنجليزية يقرأ إشعاره بها ولو أرسله عربيّ.
        locale = _locale_of(person_id, context.get("recipient_locale", "ar"))
        # نصّ المستقبل بلغته: من وضع {{title}} في القالب يريد نصّ
        # المستقبل لا نصّ المرسِل. والمفاتيح المنتهية بـ_en تُبدَّل
        # مكان أصلها حين تكون لغته الإنجليزية.
        ctx = _localized_context(context, locale)
        try:
            rendered = render(event_key, Channel.IN_APP, locale,
                              ctx, account_id)
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
            if channel == Channel.IN_APP:
                st, err = DeliveryStatus.SENT, ""
            elif channel == Channel.EMAIL:
                st, err = _deliver_email(
                    account_id=account_id, company_id=company_id,
                    notif=notif, person_id=person_id, event_key=event_key,
                    locale=locale, context=ctx)
            else:
                # واتساب وإشعار الجوال — لا مزوّد بعد (ق-90)
                st, err = DeliveryStatus.PENDING, ""
            NotificationDelivery.objects.create(
                account_id=account_id, notification=notif, channel=channel,
                status=st, error=err,
                attempted_at=(timezone.now()
                              if st != DeliveryStatus.PENDING else None),
            )

    return {"event": event_key, "notifications": created,
            "recipients": len(recipients)}
