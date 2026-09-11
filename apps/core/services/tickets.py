"""
تذاكر الدعم ومهلة الاستجابة (ق-133).

⚠️ **زمن الاستجابة يُقاس ولا يبقى وعدًا**: نبيع «٨ ساعات عمل»
فيجب أن يُحسب موعدُه بختم الوقت، وأن يُعلَم من تجاوزناه.
"""
import logging
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class TicketError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


#: مهلة كل باقة: (ساعات، أبساعات العمل؟)
#
# ⚠️ **بالباقة لا بالميزة**: الدعم مستوى خدمةٍ متدرّج، لا ميزةٌ
# تُفتح وتُغلق — فمن لا باقة له لا تذكرة أصلًا.
PLAN_SLA = {
    "basic": (24, False),        # ٢٤ ساعة جدارية
    "premium": (8, True),        # ٨ ساعات عمل
    "enterprise": (2, True),     # ساعتا عمل
    "government": (2, True),
}
DEFAULT_SLA = (24, False)

# ساعات عملنا نحن لا العميل: الأحد–الخميس ٨ص–٥م بتوقيت الرياض
WORK_START = time(8, 0)
WORK_END = time(17, 0)
WORK_DAYS = {6, 0, 1, 2, 3}      # الأحد=6 في weekday() … الخميس=3


def _is_work_day(d):
    return d.weekday() in WORK_DAYS


def add_business_hours(start, hours):
    """
    يضيف ساعات عملٍ إلى لحظة — متخطّيًا الليل والعطلة.

    فتذكرةٌ تُفتح الخميس ٤:٣٠م بمهلة ساعتين تستحقّ الأحد ٩:٣٠ص لا
    الخميس ٦:٣٠م — والوعد بساعات العمل يجب أن يُحسب بها.
    """
    remaining = timedelta(hours=hours)
    cursor = start

    # ⚠️ سقفٌ صريح للدوران: خللٌ في التقويم لا يجمّد الخادم
    for _ in range(400):
        if not _is_work_day(cursor.date()):
            cursor = datetime.combine(
                cursor.date() + timedelta(days=1), WORK_START,
                tzinfo=cursor.tzinfo)
            continue

        day_start = datetime.combine(cursor.date(), WORK_START,
                                     tzinfo=cursor.tzinfo)
        day_end = datetime.combine(cursor.date(), WORK_END,
                                   tzinfo=cursor.tzinfo)

        if cursor < day_start:
            cursor = day_start
        if cursor >= day_end:
            cursor = datetime.combine(
                cursor.date() + timedelta(days=1), WORK_START,
                tzinfo=cursor.tzinfo)
            continue

        available = day_end - cursor
        if available >= remaining:
            return cursor + remaining
        remaining -= available
        cursor = datetime.combine(
            cursor.date() + timedelta(days=1), WORK_START,
            tzinfo=cursor.tzinfo)

    return cursor


def sla_for(account_id):
    """مهلة هذا الحساب من باقته السارية."""
    from apps.accounts.models_billing_v2 import AccountSubscription

    sub = AccountSubscription.objects.filter(
        account_id=account_id).select_related("plan").first()
    code = getattr(getattr(sub, "plan", None), "code", "") or ""
    hours, business = PLAN_SLA.get(code, DEFAULT_SLA)
    return hours, business, code


def _next_no(company_id):
    """رقم التذكرة — أقصى مستعمل + ١."""
    from apps.core.models import SupportTicket

    year = timezone.localdate().year
    prefix = f"TKT-{year}-"
    last = (SupportTicket.objects
            .filter(company_id=company_id, ticket_no__startswith=prefix)
            .order_by("-ticket_no").values_list("ticket_no", flat=True)
            .first())
    n = int(last.rsplit("-", 1)[-1]) if last else 0
    return f"{prefix}{n + 1:05d}"


@transaction.atomic
def open_ticket(*, company, person, subject, body, screenshot_url,
                kind="bug", priority="normal"):
    """
    يفتح تذكرة — **والصورة إلزامية**.

    فـ«لا يعمل» بلا صورة تُستهلك في أسئلةٍ متبادلة، والشاشة تقول
    أكثر من فقرة.
    """
    from apps.core.models import SupportTicket, TicketMessage

    if not (subject or "").strip():
        raise TicketError("عنوان المشكلة مطلوب")
    if not (body or "").strip():
        raise TicketError("اشرح المشكلة لنفهمها")
    if not (screenshot_url or "").strip():
        raise TicketError("أرفق صورة الشاشة — بها نفهم أسرع")

    hours, business, code = sla_for(company.account_id)
    now = timezone.now()
    due = (add_business_hours(now, hours) if business
           else now + timedelta(hours=hours))

    t = SupportTicket.objects.create(
        account_id=company.account_id, company=company,
        ticket_no=_next_no(company.id),
        subject=subject.strip()[:200], body=body.strip(),
        screenshot_url=screenshot_url.strip(),
        kind=kind, priority=priority,
        opened_by_person_id=person.id,
        opened_by_name=person.display_name,
        # ⚠️ **تُجمَّد عند الفتح**: ترقية الباقة بعدها لا تُغيّر
        # تعهّدنا في تذكرةٍ قائمة، ولا تخفيضُها يُعفينا منه.
        sla_hours=hours, sla_business_hours=business,
        due_at=due, plan_code_at_open=code)

    TicketMessage.objects.create(
        account_id=t.account_id, company_id=t.company_id,
        ticket=t, body=t.body, attachment_url=t.screenshot_url,
        from_support=False, author_person_id=person.id,
        author_name=person.display_name)

    logger.info("تذكرة %s — مهلة %s%s", t.ticket_no, hours,
                " ساعة عمل" if business else " ساعة")
    return t


@transaction.atomic
def reply(*, ticket, body, from_support, person=None, attachment_url=""):
    """
    ردٌّ على تذكرة — ويضبط حالتها.

    ⚠️ **وأول ردٍّ من الدعم يُختم وقته**: به يُقاس الوفاء بالمهلة،
    وبدونه يبقى الوعد بلا دليل.
    """
    from apps.core.models import TicketMessage, TicketStatus

    if not (body or "").strip():
        raise TicketError("لا رسالة")
    if ticket.status == TicketStatus.RESOLVED:
        raise TicketError("التذكرة مغلقة — افتح تذكرةً جديدة")

    m = TicketMessage.objects.create(
        account_id=ticket.account_id, company_id=ticket.company_id,
        ticket=ticket, body=body.strip(),
        attachment_url=attachment_url or "",
        from_support=from_support,
        author_person_id=getattr(person, "id", None),
        author_name=getattr(person, "display_name", "") or "الدعم")

    fields = ["status", "updated_at"]
    if from_support:
        ticket.status = TicketStatus.WAITING
        if ticket.first_response_at is None:
            ticket.first_response_at = timezone.now()
            fields.append("first_response_at")
    else:
        ticket.status = TicketStatus.OPEN
    ticket.save(update_fields=fields)
    return m


@transaction.atomic
def resolve(*, ticket):
    """يُغلق التذكرة."""
    from apps.core.models import TicketStatus

    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_at = timezone.now()
    ticket.save(update_fields=["status", "resolved_at", "updated_at"])
    return ticket
