"""
مسارات الإشعارات — جرس المستخدم (ق-58).

الإشعار يخصّ شخصًا بعينه، فكل استعلام هنا مقيَّد بـ
recipient_person_id=person.id — معزول ذاتيًا بلا حاجة لبوابة نطاق.
"""
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.notifications.models import Notification


def _person(request):
    return getattr(request.user, "person", None)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_notifications(request):
    """
    إشعاراتي — الأحدث أولًا، مع عدد غير المقروء.

    والقائمة محدودة بخمسين: الجرس يعرض ما يستحق الانتباه، لا أرشيفًا.
    """
    person = _person(request)
    if person is None:
        return Response({"unread": 0, "rows": []})

    # معزول ذاتيًا: مقيَّد بالمستقبل نفسه
    qs = Notification.objects.filter(recipient_person_id=person.id)

    return Response({
        "unread": qs.filter(read_at__isnull=True).count(),
        "rows": [{
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "event_key": n.event_key,
            "link_url": n.link_url,
            "is_read": n.read_at is not None,
            "created_at": n.created_at,
        } for n in qs[:50]],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_read(request):
    """
    تعليم إشعارات مقروءة — واحدًا أو الكل.

    يقبل {"ids": [1,2]} أو {"all": true}.
    """
    person = _person(request)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    # معزول ذاتيًا: مقيَّد بالمستقبل نفسه
    qs = Notification.objects.filter(
        recipient_person_id=person.id, read_at__isnull=True)

    if not request.data.get("all"):
        ids = request.data.get("ids") or []
        qs = qs.filter(id__in=ids)

    n = qs.update(read_at=timezone.now())
    return Response({"marked": n})


# ══════════ قوالب الإشعارات ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_templates(request):
    """
    قوالب الإشعارات مجمَّعة بالحدث.

    فلكل حدث قوالب بعدد قنواته ولغاته — وعرضها مسطّحة يجعلها
    مئتي سطر لا يُقرأ.
    """
    from apps.notifications.catalog import EVENTS
    from apps.notifications.models import NotificationTemplate

    Gate.require(request.user, "company.view")

    account_id = getattr(getattr(request, "account_ctx", None),
                         "account_id", None)

    # القوالب العامة (account_id=None) يشترك فيها الجميع، وقالب
    # الحساب يغلبها. معزول ذاتيًا: مقيَّد بحساب المنفّذ أو عام.
    from django.db.models import Q

    rows = NotificationTemplate.objects.filter(
        Q(account_id=account_id) | Q(account_id__isnull=True))

    # قالب الحساب يغلب العام لنفس (الحدث، القناة، اللغة)
    picked = {}
    for t in rows:
        k = (t.event_key, t.channel, t.locale)
        if k not in picked or t.account_id is not None:
            picked[k] = t

    by_event = {}
    for t in picked.values():
        by_event.setdefault(t.event_key, []).append({
            "id": t.id, "channel": t.channel, "locale": t.locale,
            "subject": t.subject, "body": t.body,
            "is_default": t.account_id is None,
        })

    # EVENTS قائمة EventSpec لا قاموسًا
    out = []
    for spec in EVENTS:
        out.append({
            "event_key": spec.key,
            "name_ar": spec.name_ar,
            "module": spec.module,
            "channels": list(spec.channels),
            "is_mandatory": spec.is_mandatory,
            "templates": sorted(
                by_event.get(spec.key, []),
                key=lambda x: (x["channel"], x["locale"])),
        })
    return Response(out)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def notification_template_detail(request, template_id):
    """
    تعديل نصّ قالب.

    والمتغيّرات بين قوسين معقوفين ({employee_name}) تُملأ عند
    الإرسال — فمن يحذفها يُرسل نصًّا ناقصًا.
    """
    from apps.notifications.models import NotificationTemplate

    Gate.require(request.user, "company.edit")

    account_id = getattr(getattr(request, "account_ctx", None),
                         "account_id", None)

    # معزول ذاتيًا: مقيَّد بحساب المنفّذ أو عام
    from django.db.models import Q

    t = NotificationTemplate.objects.filter(
        Q(id=template_id),
        Q(account_id=account_id) | Q(account_id__isnull=True)).first()
    if t is None:
        return Response({"detail": "القالب غير موجود"}, status=404)

    # القالب العام يشترك فيه كل الحسابات — فتعديله ينسخه للحساب
    # ولا يمسّ غيره
    if t.account_id is None:
        t = NotificationTemplate.objects.create(
            account_id=account_id, event_key=t.event_key,
            channel=t.channel, locale=t.locale,
            subject=t.subject, body=t.body)

    if "subject" in request.data:
        t.subject = request.data["subject"] or ""
    if "body" in request.data:
        t.body = request.data["body"] or ""
    t.save()

    from apps.core.services.audit import log_action
    log_action(instance=t, action="update",
               actor=getattr(request.user, "person", None),
               label=t.event_key,
               summary=f"عُدّل قالب {t.event_key} ({t.channel})",
               channel="web")
    return Response({
        "id": t.id, "channel": t.channel, "locale": t.locale,
        "subject": t.subject, "body": t.body,
    })
