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
                  "request_no": request_obj.request_no,
                    "link_url": "/me/track"},
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
                  "request_no": delegation.request.request_no,
                    "link_url": "/me/track"},
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
    from django.db.models import Q
    return Delegation.objects.filter(
        Q(ends_on__gte=day) | Q(ends_on__isnull=True),
        deputy=employment, status=DelegationStatus.ACCEPTED,
        starts_on__lte=day,
    ).select_related("absentee")


# ══════════ الخلافة عند المغادرة (ق-79) ══════════

#: المواقع التي لا تُترك بلا بديل — من يعتمد أو يدير فريقًا
ADMIN_ROLES = {"ceo", "hr_manager", "hr_staff", "dept_manager", "supervisor"}


def holds_admin_position(employment):
    """
    هل يشغل موقعًا إداريًا؟

    فمغادرة الموظف العادي لا تقطع سلسلة — لا يعتمد شيئًا ولا
    يدير أحدًا. والبديل شرط لمن يعتمد أو يدير أو يملك الحساب.
    """
    user = getattr(getattr(employment, "person", None), "user", None)
    m = getattr(user, "account_membership", None)
    if m is None:
        return False
    if m.is_account_owner:
        return True
    codes = {a.role.code for a in m.role_assignments.select_related("role")}
    if codes & ADMIN_ROLES:
        return True
    # ومن يدير قسمًا أو يشرف على أحد ولو بلا دور إداري مسجَّل
    from apps.employees.models import Employment
    if Employment.objects.filter(direct_manager=employment).exists():
        return True
    from apps.organization.models import Department
    return Department.objects.filter(
        manager_employment_id=employment.id).exists()


@transaction.atomic
def appoint_successor(*, leaving, successor, effective_from,
                      actor=None, note=""):
    """
    يعيّن خليفة لمن يغادر موقعه (ق-79).

    الخليفة يبقى بدوره ويرث المهام: مشرف يخلف مدير إدارة يبقى
    مشرفًا ويدير الإدارة كاملة — كالإنابة تمامًا (ق-75) لكن بلا
    نهاية، فمن غادر لا يُنتظر رجوعه.
    """
    if successor.id == leaving.id:
        raise DelegationError("لا يخلف الموظف نفسه — اختر غيره")

    if successor.company_id != leaving.company_id:
        raise DelegationError("الخليفة من شركة أخرى")

    if successor.status != EmploymentStatus.ACTIVE:
        raise DelegationError("الخليفة غير نشط على رأس العمل")

    d = Delegation.objects.create(
        account_id=leaving.account_id, company_id=leaving.company_id,
        request=None, absentee=leaving, deputy=successor,
        starts_on=effective_from, ends_on=None,
        is_permanent=True, note=note,
        # الخلافة قرار إداري نافذ لا عرض يُقبل: من غادر لا يبقى
        # موقعه معلّقًا بانتظار موافقة. والاعتماد يقع على القرار
        # نفسه في سلسلته لا على الخلافة بعده.
        status=DelegationStatus.ACCEPTED)

    from apps.core.services.audit import log_action
    log_action(
        instance=d, action="create", actor=actor,
        label=f"{leaving.employee_no} → {successor.employee_no}",
        summary=(f"خلافة دائمة: {successor.person.display_name} يخلف "
                 f"{leaving.person.display_name} من {effective_from}"),
        channel="web")
    return d


def successor_of(employment):
    """خليفة هذا الموظف إن عُيّن — أحدث خلافة سارية."""
    return Delegation.objects.filter(
        absentee=employment, is_permanent=True,
        status=DelegationStatus.ACCEPTED
    ).select_related("deputy__person").order_by("-starts_on").first()
