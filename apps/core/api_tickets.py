"""مسارات تذاكر الدعم (ق-133)."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import SupportTicket, TicketKind, TicketStatus
from apps.core.services import tickets as svc


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _json(t, messages=None):
    out = {
        "id": t.id, "ticket_no": t.ticket_no, "subject": t.subject,
        "kind": t.kind, "kind_label": t.get_kind_display(),
        "priority": t.priority, "priority_label": t.get_priority_display(),
        "status": t.status, "status_label": t.get_status_display(),
        "opened_by": t.opened_by_name,
        "created_at": t.created_at,
        "due_at": t.due_at,
        "sla_hours": t.sla_hours,
        "sla_business": t.sla_business_hours,
        "answered": t.first_response_at is not None,
        "breached": t.breached,
    }
    if messages is not None:
        out["body"] = t.body
        out["screenshot_url"] = t.screenshot_url
        out["messages"] = [{
            "id": m.id, "body": m.body,
            "attachment_url": m.attachment_url,
            "from_support": m.from_support,
            "author": m.author_name,
            "at": m.created_at,
        } for m in messages]
    return out


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def tickets(request):
    """
    تذاكري — عرضًا وفتحًا.

    ⚠️ **كل موظف يفتح ويرى تذاكره وحده**: فمن واجه العلّة أدرى
    بوصفها، وإحالتُه لمديره تُضيع الوقت والتفاصيل. ولا يرى تذاكر
    غيره — فقد يشكو من مديره نفسه.
    """
    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    if request.method == "GET":
        qs = SupportTicket.objects.filter(
            company_id=_company_id(request),
            opened_by_person_id=person.id)
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        hours, business, _ = svc.sla_for(
            getattr(request, "account_ctx", None).account_id
            if getattr(request, "account_ctx", None) else None)
        return Response({
            "tickets": [_json(t) for t in qs[:200]],
            "kinds": [{"value": v, "label": lbl}
                      for v, lbl in TicketKind.choices],
            "sla": {"hours": hours, "business": business},
        })

    from apps.accounts.models import Company

    # مقيَّد بشركة المنفّذ النشطة
    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    try:
        t = svc.open_ticket(
            company=comp, person=person,
            subject=d.get("subject", ""), body=d.get("body", ""),
            screenshot_url=d.get("screenshot_url", ""),
            kind=d.get("kind") or TicketKind.BUG,
            priority=d.get("priority") or "normal")
    except svc.TicketError as e:
        return Response({"detail": str(e)}, status=400)

    return Response(_json(t), status=status.HTTP_201_CREATED)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def ticket_detail(request, ticket_id):
    """تذكرةٌ برسائلها — وردٌّ عليها."""
    person = getattr(request.user, "person", None)
    t = SupportTicket.objects.filter(
        id=ticket_id, company_id=_company_id(request)).first()
    if t is None or person is None:
        return Response({"detail": "غير موجودة"}, status=404)

    # ⚠️ تذكرته وحده — ولو كان مديرًا
    if t.opened_by_person_id != person.id:
        return Response({"detail": "ليست لك"}, status=403)

    if request.method == "GET":
        return Response(_json(t, list(t.messages.all())))

    try:
        svc.reply(ticket=t, body=request.data.get("body", ""),
                  from_support=False, person=person,
                  attachment_url=request.data.get("attachment_url", ""))
    except svc.TicketError as e:
        return Response({"detail": str(e)}, status=400)

    t.refresh_from_db()
    return Response(_json(t, list(t.messages.all())))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def close_ticket(request, ticket_id):
    """يغلقها صاحبها — فمن فتحها أدرى بانتهاء حاجته."""
    person = getattr(request.user, "person", None)
    t = SupportTicket.objects.filter(
        id=ticket_id, company_id=_company_id(request)).first()
    if t is None or person is None:
        return Response({"detail": "غير موجودة"}, status=404)
    if t.opened_by_person_id != person.id:
        return Response({"detail": "ليست لك"}, status=403)

    svc.resolve(ticket=t)
    return Response(_json(t))
