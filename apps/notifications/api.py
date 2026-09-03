"""
مسارات الإشعارات — جرس المستخدم (ق-58).

الإشعار يخصّ شخصًا بعينه، فكل استعلام هنا مقيَّد بـ
recipient_person_id=person.id — معزول ذاتيًا بلا حاجة لبوابة نطاق.
"""
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
