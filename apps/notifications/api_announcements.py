"""
مسارات الإعلانات (ق-102).

الإرسال فوريّ: يضغط المرسِل فيصل الإعلان في ثانيته — إشعارًا في
النظام، وبريدًا إن اختاره.
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.notifications.models_announcement import (
    Announcement, AnnouncementAttachment, AnnouncementKind, AudienceType)
from apps.notifications.services.announcements import (
    AnnouncementError, publish, resolve_recipients)

logger = logging.getLogger(__name__)
MAX_ATTACHMENTS = 5


def _ctx(request):
    c = getattr(request, "account_ctx", None)
    return (getattr(c, "account_id", None),
            getattr(c, "active_company_id", None))


def _my_person_id(request):
    return getattr(getattr(request.user, "person", None), "id", None)


def _my_department_ids(request):
    """إدارات المرسِل — لمن لا يملك إلا send_department."""
    from apps.employees.models import Employment, EmploymentStatus
    pid = _my_person_id(request)
    if not pid:
        return []
    return list(Employment.objects.filter(
        person_id=pid, status=EmploymentStatus.ACTIVE
    ).exclude(department_id=None).values_list("department_id", flat=True))


def _serialize(a, locale="ar"):
    return {
        "id": a.id,
        "kind": a.kind,
        "title": a.title_for(locale),
        "body": a.body_for(locale),
        "title_ar": a.title_ar, "title_en": a.title_en,
        "body_ar": a.body_ar, "body_en": a.body_en,
        "audience_type": a.audience_type,
        "audience_ids": a.audience_ids,
        "via_email": a.via_email,
        "recipient_count": a.recipient_count,
        "sent_at": a.sent_at.isoformat() if a.sent_at else None,
        "attachments": [
            {"id": x.id, "name": x.stored_file.original_name,
             "size": x.stored_file.size_bytes}
            for x in a.attachments.select_related("stored_file")
        ],
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def announcements(request):
    account_id, company_id = _ctx(request)

    if request.method == "GET":
        Gate.require(request.user, "announcements.view")
        qs = Gate.filter_queryset(request.user, "announcements.view",
                                  Announcement.objects.all())
        qs = qs.filter(company_id=company_id).order_by("-created_at")[:100]
        locale = request.headers.get("Accept-Language", "ar")[:2]
        return Response([_serialize(a, locale) for a in qs])

    # ── الإرسال ──
    # check يفحص ولا يرمي — فمن لا يملك الشاملة يُجرَّب بالإداريّة
    wide = bool(Gate.check(request.user, "announcements.send_company"))
    if not wide:
        Gate.require(request.user, "announcements.send_department")

    d = request.data or {}
    kind = d.get("kind") or AnnouncementKind.GENERAL
    if kind not in AnnouncementKind.values:
        return Response({"detail": "نوع غير معروف"}, status=400)

    audience_type = d.get("audience_type")
    if audience_type not in AudienceType.values:
        return Response({"detail": "لم تحدّد المستقبلين"}, status=400)

    title_ar = str(d.get("title_ar") or "").strip()
    body_ar = str(d.get("body_ar") or "").strip()
    if not title_ar or not body_ar:
        return Response({"detail": "العنوان والنص مطلوبان"}, status=400)

    file_ids = d.get("file_ids") or []
    if len(file_ids) > MAX_ATTACHMENTS:
        return Response(
            {"detail": f"الحد {MAX_ATTACHMENTS} مرفقات"}, status=400)

    allowed = None if wide else _my_department_ids(request)
    try:
        recipients = resolve_recipients(
            account_id=account_id, company_id=company_id,
            audience_type=audience_type,
            audience_ids=d.get("audience_ids") or [],
            allowed_department_ids=allowed)
    except AnnouncementError as e:
        return Response({"code": e.code, "detail": str(e)}, status=403)

    if not recipients:
        return Response({"code": "no_recipients",
                         "detail": "لا مستقبلين — راجع اختيارك"}, status=400)

    from apps.core.models_files import StoredFile
    with transaction.atomic():
        a = Announcement.objects.create(
            account_id=account_id, company_id=company_id,
            kind=kind,
            title_ar=title_ar, title_en=str(d.get("title_en") or "").strip(),
            body_ar=body_ar, body_en=str(d.get("body_en") or "").strip(),
            audience_type=audience_type,
            audience_ids=d.get("audience_ids") or [],
            via_email=bool(d.get("via_email")),
            sent_by_person_id=_my_person_id(request),
        )
        files = list(StoredFile.objects.filter(
            id__in=file_ids, account_id=account_id, is_deleted=False))
        for f in files:
            AnnouncementAttachment.objects.create(
                account_id=account_id, announcement=a, stored_file=f)

    # المرفقات للبريد: (اسم، بايتات، نوع)
    att = []
    if a.via_email:
        for f in files:
            try:
                with f.file.open("rb") as fh:
                    att.append((f.original_name, fh.read(),
                                f.content_type or "application/octet-stream"))
            except (OSError, ValueError) as e:
                # مرفق تعذّرت قراءته لا يُسقط الإعلان: الإشعار يصل،
                # والملفّ يبقى متاحًا في النظام.
                logger.error("تعذّرت قراءة مرفق %s: %s", f.id, e)

    try:
        count = publish(a, recipients=recipients, attachments=att)
    except AnnouncementError as e:
        return Response({"code": e.code, "detail": str(e)}, status=400)

    return Response({**_serialize(a), "recipient_count": count},
                    status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_announcements(request):
    """ما وصل الموظف — من إشعاراته لا من الإعلانات كلّها."""
    from apps.notifications.models import Notification
    from apps.notifications.models_announcement import EVENT_KEY

    pid = _my_person_id(request)
    if not pid:
        return Response([])
    qs = Notification.objects.filter(
        recipient_person_id=pid, event_key=EVENT_KEY
    ).order_by("-created_at")[:100]
    return Response([{
        "id": n.id,
        "announcement_id": (n.payload or {}).get("announcement_id"),
        "kind": (n.payload or {}).get("kind", "general"),
        "title": n.title, "body": n.body,
        "created_at": n.created_at.isoformat(),
        "read_at": n.read_at.isoformat() if n.read_at else None,
    } for n in qs])
