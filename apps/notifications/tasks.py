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
            elif channel == Channel.PUSH:
                _queue_push(account_id, notif, person_id, event_key)
                continue
            else:
                # واتساب — لا مزوّد بعد (ق-90)
                st, err = DeliveryStatus.PENDING, ""
            NotificationDelivery.objects.create(
                account_id=account_id, notification=notif, channel=channel,
                status=st, error=err,
                attempted_at=(timezone.now()
                              if st != DeliveryStatus.PENDING else None),
            )

        # ق-232: \u26a0\u26a0 **كل إشعارٍ داخل النظام يُدفع للجوال** (قرار جواد) —
        # فلا يُعدَّل حدثٌ واحد: القائم والقادم يصلان بلا عمل.
        if Channel.PUSH not in spec.channels:
            _queue_push(account_id, notif, person_id, event_key)

    return {"event": event_key, "notifications": created,
            "recipients": len(recipients)}



# ══════════ إشعارات الجوال (ق-232) ══════════

def _queue_push(account_id, notif, person_id, event_key):
    """
    يُسجّل التسليم ويُرسله **بعد اكتمال الحفظ**.

    \u26a0 **بلا جهازٍ نشط لا سجلّ** — فمستخدمو الويب بلا تطبيق يُضيفون
    سطرًا لكل إشعار: جدولٌ يتضخّم بلا فائدة.
    """
    from django.db import transaction

    from apps.notifications.models_push import PushDevice

    if not PushDevice.objects.filter(person_id=person_id,
                                     is_active=True).exists():
        return
    if not _channel_allowed(account_id, person_id, event_key, Channel.PUSH):
        NotificationDelivery.objects.create(
            account_id=account_id, notification=notif, channel=Channel.PUSH,
            status=DeliveryStatus.SKIPPED, error="معطّل في تفضيلات المستخدم")
        return
    d = NotificationDelivery.objects.create(
        account_id=account_id, notification=notif, channel=Channel.PUSH,
        status=DeliveryStatus.PENDING)
    transaction.on_commit(lambda: push_notification.apply_async(
        kwargs={"account_id": account_id, "delivery_id": d.id}))


@shared_task(base=AccountTask, bind=True, max_retries=3,
             default_retry_delay=30)
def push_notification(self, *, account_id, delivery_id):
    """يدفع إشعارًا واحدًا لأجهزة مستقبله — ويكتب النتيجة في سجلّ التسليم."""
    from apps.notifications.services.push import PushTransient, send_to_person

    d = (NotificationDelivery.objects.select_related("notification")
         .filter(id=delivery_id).first())
    if d is None or d.status != DeliveryStatus.PENDING:
        return {"skipped": True}
    n = d.notification
    try:
        res = send_to_person(
            person_id=n.recipient_person_id, title=n.title, body=n.body,
            data={"notification_id": n.id, "event_key": n.event_key,
                  "link_url": n.link_url})
    except PushTransient as e:
        if self.request.retries >= self.max_retries:
            d.status = DeliveryStatus.FAILED
            d.error = f"Expo غير متاح بعد {self.max_retries} محاولات: {e}"[:500]
            d.attempted_at = timezone.now()
            d.save()
            return {"failed": True}
        raise self.retry(exc=e)

    if res.no_devices:
        d.status, d.error = DeliveryStatus.SKIPPED, "لا جهاز نشط"
    elif res.sent:
        d.status = DeliveryStatus.SENT
        d.error = "; ".join(res.errors)[:500]
    else:
        d.status = DeliveryStatus.FAILED
        d.error = "; ".join(res.errors)[:500] or "رُفض"
    d.provider_ref = ",".join(res.ticket_ids)[:120]
    d.attempted_at = timezone.now()
    d.save()
    return {"sent": res.sent, "failed": res.failed}
