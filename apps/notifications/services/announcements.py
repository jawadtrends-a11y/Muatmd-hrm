"""
إرسال الإعلانات (ق-102).

المستقبلون يُحلّون **عند الإرسال ويُجمَّدون**: من انضم بعده لا
يُفاجأ بتعزية قديمة، ومن نُقل لا يفقد ما وصله. والعدد يُحفظ في
السجلّ ليعرف المرسِل كم بلغه إعلانه.

والنطاق في الصلاحية: من يملك send_company يخاطب الشركة كلّها،
ومن يملك send_department يخاطب إدارته وحدها — ويُرفض ما عداها
لا يُقصّ بصمت.
"""
import logging

from django.utils import timezone

from apps.notifications.bus import emit
from apps.notifications.models_announcement import (
    EVENT_KEY, Announcement, AudienceType)

logger = logging.getLogger(__name__)


class AnnouncementError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def resolve_recipients(*, account_id, company_id, audience_type,
                       audience_ids, allowed_department_ids=None):
    """
    أرقام الأشخاص المستقبلين.

    allowed_department_ids: إن مُرّرت، حُصر الحلّ فيها — وهو حصار
    مدير الإدارة بإدارته.
    """
    from apps.employees.models import Employment, EmploymentStatus

    qs = Employment.objects.filter(company_id=company_id,
                                   status=EmploymentStatus.ACTIVE)

    if audience_type == AudienceType.DEPARTMENTS:
        ids = [int(x) for x in (audience_ids or [])]
        if allowed_department_ids is not None:
            outside = set(ids) - set(allowed_department_ids)
            if outside:
                raise AnnouncementError(
                    "department_not_allowed",
                    "لا تملك إرسال إعلان لهذه الإدارة")
        qs = qs.filter(department_id__in=ids)

    elif audience_type == AudienceType.PERSONS:
        ids = [int(x) for x in (audience_ids or [])]
        qs = qs.filter(person_id__in=ids)
        if allowed_department_ids is not None:
            qs = qs.filter(department_id__in=allowed_department_ids)

    elif allowed_department_ids is not None:
        # طلب «كل الشركة» ممّن لا يملك إلا إدارته — يُرفض صراحةً
        # ولا يُحوَّل بصمت إلى إدارته: المرسِل ظنّ أنه خاطب الجميع.
        raise AnnouncementError(
            "company_wide_not_allowed",
            "لا تملك إرسال إعلان لكل الشركة")

    return list(qs.values_list("person_id", flat=True).distinct())


def publish(announcement, *, recipients, attachments=None):
    """يُرسل الإعلان — إشعارًا في النظام، وبريدًا إن اختير."""
    if not recipients:
        raise AnnouncementError("no_recipients",
                                "لا مستقبلين — راجع اختيارك")

    from apps.accounts.models import Company
    company = Company.objects.filter(id=announcement.company_id).first()

    context = {
        "announcement_id": announcement.id,
        "kind": announcement.kind,
        "title": announcement.title_ar,
        "body": announcement.body_ar,
        "title_en": announcement.title_en or announcement.title_ar,
        "body_en": announcement.body_en or announcement.body_ar,
        "company_name": company.legal_name_ar if company else "",
        # الاسم بلغته أيضًا — يبدّله المحرّك لمن لغته إنجليزية،
        # ويرتدّ للعربي إن لم تملأ الشركة اسمها الإنجليزي.
        "company_name_en": ((company.legal_name_en or company.legal_name_ar)
                            if company else ""),
        # يفتح أرشيف الإشعارات لا صفحة مستقلّة: الأرشيف يعرض
        # النصّ كاملًا بمرفقاته، وصفحةٌ ثالثة تكرّره.
        "link_url": "/me/notifications",
        "via_email": announcement.via_email,
        "attachments": attachments or [],
    }

    emit(EVENT_KEY,
         account_id=announcement.account_id,
         company_id=announcement.company_id,
         context=context,
         actor_person_id=announcement.sent_by_person_id,
         recipients=recipients)

    Announcement.objects.filter(id=announcement.id).update(
        recipient_count=len(recipients), sent_at=timezone.now())
    return len(recipients)
