"""
خدمة الإنابة أثناء الغياب (ق-75).

الموظف يختار نائبه بنفسه عند طلب إجازته، والنائب يقبل أو يرفض.
وبالقبول تنتقل مهام الغائب إليه طوال المدة — تلقائيًا بلا تفعيل
يدوي، وتنتهي بانتهائها.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.employees.models import Employment, EmploymentStatus
from apps.leaves.models import Delegation, DelegationStatus


class DelegationError(ValueError):
    """خطأ في الإنابة — رسالة تخبر بما يُفعل."""


def eligible_deputies(employment):
    """
    من يصلح نائبًا لهذا الموظف.

    زملاؤه في إدارته — فالنائب يقوم بعمله، ومن هو خارج الإدارة
    لا يعرفه. ولا يُرشَّح الموظف نفسه.
    """
    qs = Employment.objects.filter(
        company=employment.company,
        status=EmploymentStatus.ACTIVE,
    ).exclude(id=employment.id).select_related("person")

    if employment.department_id:
        qs = qs.filter(department_id=employment.department_id)
    return qs.order_by("employee_no")


@transaction.atomic
def create_delegation(*, request_obj, deputy_employment,
                      starts_on, ends_on, note=""):
    """
    ينشئ إنابة معلّقة بانتظار قبول النائب.

    ولا تُفعَّل إلا بقبوله (ق-75): الإنابة تُقبل لا تُفرض.
    """
    absentee = request_obj.employment

    if deputy_employment.id == absentee.id:
        raise DelegationError("لا يُناب الموظف عن نفسه — اختر زميلًا")

    if deputy_employment.company_id != absentee.company_id:
        raise DelegationError("النائب من شركة أخرى")

    if deputy_employment.status != EmploymentStatus.ACTIVE:
        raise DelegationError("النائب غير نشط على رأس العمل")

    existing = Delegation.objects.filter(request=request_obj).first()
    if existing is not None:
        raise DelegationError("لهذا الطلب نائب مسجَّل — احذفه أولًا")

    d = Delegation.objects.create(
        account_id=absentee.account_id, company_id=absentee.company_id,
        request=request_obj, absentee=absentee, deputy=deputy_employment,
        starts_on=starts_on, ends_on=ends_on, note=note)

    # النائب يُعلَم فورًا — وإلا لم يعرف أن إنابة تنتظره
    from apps.notifications.bus import emit
    emit("delegation.requested", account_id=absentee.account_id,
         company_id=absentee.company_id,
         context={"absentee": absentee.person.display_name,
                  "starts_on": str(starts_on), "ends_on": str(ends_on),
                  "request_no": request_obj.request_no},
         actor_person_id=absentee.person_id,
         recipients=[deputy_employment.person_id])
    return d


@transaction.atomic
def decide_delegation(*, delegation, deputy_employment, accept):
    """
    النائب يقبل أو يرفض.

    وبالرفض تمضي الإجازة كما هي — فرفض زميل لا يمنع حق الموظف في
    إجازته، والمهام تصعد لمدير الإدارة (ق-35).
    """
    if delegation.deputy_id != deputy_employment.id:
        raise DelegationError("هذه الإنابة ليست لك")

    if delegation.status != DelegationStatus.PENDING:
        raise DelegationError(
            f"سبق أن قرّرت: {delegation.get_status_display()}")

    delegation.status = (DelegationStatus.ACCEPTED if accept
                         else DelegationStatus.DECLINED)
    delegation.decided_at = timezone.now()
    delegation.save(update_fields=["status", "decided_at", "updated_at"])

    from apps.core.services.audit import log_action
    log_action(
        instance=delegation, action="update",
        actor=deputy_employment.person,
        label=f"{delegation.absentee.employee_no} → "
              f"{delegation.deputy.employee_no}",
        summary=("قبل الإنابة" if accept else "رفض الإنابة")
                + f" من {delegation.starts_on} إلى {delegation.ends_on}",
        channel="web")

    # الغائب يُعلَم بقرار نائبه — وإلا بقي لا يدري من يغطّيه
    from apps.notifications.bus import emit
    emit("delegation.accepted" if accept else "delegation.declined",
         account_id=delegation.account_id,
         company_id=delegation.company_id,
         context={"deputy": delegation.deputy.person.display_name,
                  "starts_on": str(delegation.starts_on),
                  "ends_on": str(delegation.ends_on),
                  "request_no": delegation.request.request_no},
         actor_person_id=delegation.deputy.person_id,
         recipients=[delegation.absentee.person_id])

    return delegation


def active_delegations_for(employment, on_day=None):
    """
    من ينوب عنهم هذا الموظف اليوم.

    يُستدعى من بوابة الصلاحيات: النائب يرى مرؤوسي الغائب كما
    يراهم صاحبهم — طوال المدة لا قبلها ولا بعدها.
    """
    day = on_day or date.today()
    return Delegation.objects.filter(
        deputy=employment, status=DelegationStatus.ACCEPTED,
        starts_on__lte=day, ends_on__gte=day,
    ).select_related("absentee")
