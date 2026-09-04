"""
خدمة التغيير الوظيفي (ق-82).

موظف الموارد يسجّل، ومدير الموارد يعتمد، ثم يسري. والاعتماد قبل
الاحتساب: الفصل لا تُحسب مخالصته حتى يُعتمد.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.employees.models import (ChangeStatus, ChangeType, Employment,
                                   EmploymentStatus, JobChange)


class JobChangeError(ValueError):
    """خطأ في التغيير الوظيفي — رسالة تخبر بما يُفعل."""


#: ما يفرغ موقعًا إداريًا فيلزمه بديل (ق-79)
VACATES_POSITION = {ChangeType.PROMOTION, ChangeType.DEMOTION,
                    ChangeType.TRANSFER, ChangeType.DISMISSAL}


def _role_code(employment):
    """دور الموظف في النظام — أو فراغ إن لم يكن له حساب."""
    user = getattr(getattr(employment, "person", None), "user", None)
    m = getattr(user, "account_membership", None)
    if m is None:
        return ""
    a = m.role_assignments.select_related("role").first()
    return a.role.code if a else ""


@transaction.atomic
def create_change(*, employment, change_type, effective_from,
                  new_job_title=None, new_department=None,
                  new_direct_manager=None, new_role_code="",
                  dismissal_reason="", successor=None, note="",
                  actor=None):
    """
    يسجّل تغييرًا وظيفيًا بانتظار اعتماد مدير الموارد.

    والقيم القديمة تُحفظ هنا: من يراجع بعد سنة يحتاج معرفة ما كان
    قبل ما صار (ق-80).
    """
    if employment.status != EmploymentStatus.ACTIVE:
        raise JobChangeError("الموظف غير نشط على رأس العمل")

    if JobChange.objects.filter(
            employment=employment, status=ChangeStatus.PENDING).exists():
        raise JobChangeError(
            "له تغيير وظيفي بانتظار الاعتماد — اعتمده أو ألغه أولًا")

    if change_type == ChangeType.TRANSFER and new_department is None:
        raise JobChangeError("حدّد الإدارة الجديدة")

    if change_type == ChangeType.DISMISSAL and not dismissal_reason:
        raise JobChangeError("حدّد سبب الفصل")

    # ق-79: لا يفرغ موقع إداري بلا بديل
    from apps.leaves.services.delegation import (holds_admin_position,
                                                 successor_of)
    if (change_type in VACATES_POSITION
            and holds_admin_position(employment)
            and successor is None
            and successor_of(employment) is None):
        raise JobChangeError(
            "سمِّ بديلًا يخلفه — فموقعه الإداري لا يُترك بلا شاغل")

    if successor is not None:
        if successor.id == employment.id:
            raise JobChangeError("لا يخلف الموظف نفسه")
        if successor.company_id != employment.company_id:
            raise JobChangeError("البديل من شركة أخرى")

    change = JobChange.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        employment=employment, change_type=change_type,
        effective_from=effective_from,
        new_job_title=new_job_title,
        new_department=new_department,
        new_direct_manager=new_direct_manager,
        new_role_code=new_role_code,
        dismissal_reason=dismissal_reason,
        successor=successor, note=note,
        old_job_title_id=employment.job_title_id,
        old_department_id=employment.department_id,
        old_direct_manager_id=employment.direct_manager_id,
        old_role_code=_role_code(employment),
        created_by_person_id=getattr(actor, "id", None),
    )

    # مدير الموارد يُعلَم فورًا — وإلا لم يعرف حتى يفتح الملف
    _notify_managers(change, "job_change.submitted")

    from apps.core.services.audit import log_create
    log_create(
        instance=change, actor=actor, label=employment.employee_no,
        summary=(f"سُجّل {change.get_change_type_display()} لـ"
                 f"{employment.person.display_name} يسري من "
                 f"{effective_from}"),
        channel="web")
    return change


@transaction.atomic
def decide_change(*, change, approve, actor=None, note=""):
    """
    مدير الموارد يعتمد التغيير أو يرفضه — وبالاعتماد يسري.

    والأثر هنا لا عند التسجيل: قد يُرفض، فلا يُحرَّك شيء قبل
    القرار (ق-80: وقت التسجيل غير تاريخ السريان).
    """
    if change.status != ChangeStatus.PENDING:
        raise JobChangeError(
            f"التغيير {change.get_status_display()} — لا يُعاد القرار فيه")

    change.status = (ChangeStatus.APPROVED if approve
                     else ChangeStatus.REJECTED)
    change.decided_by_person_id = getattr(actor, "id", None)
    change.decided_at = timezone.now()
    change.decision_note = note
    change.save(update_fields=["status", "decided_by_person_id",
                               "decided_at", "decision_note", "updated_at"])

    effect = {}
    if approve:
        effect = _apply(change, actor=actor)

    # ومن سجّله يُعلَم بالقرار
    _notify_creator(change, "job_change.approved" if approve
                    else "job_change.rejected", note=note)

    from apps.core.services.audit import log_action
    log_action(
        instance=change, action="approve" if approve else "reject",
        actor=actor, label=change.employment.employee_no,
        summary=(f"{'اعتُمد' if approve else 'رُفض'} "
                 f"{change.get_change_type_display()} لـ"
                 f"{change.employment.person.display_name}"),
        channel="web")

    return change, effect


def _apply(change, actor=None):
    """يطبّق التغيير المعتمد على ملف الموظف."""
    emp = change.employment
    out = {}
    fields = []

    if change.new_job_title_id:
        emp.job_title_id = change.new_job_title_id
        fields.append("job_title")

    if change.new_department_id:
        emp.department_id = change.new_department_id
        fields.append("department")

    if change.new_direct_manager_id:
        emp.direct_manager_id = change.new_direct_manager_id
        fields.append("direct_manager")

    if change.change_type == ChangeType.DISMISSAL:
        # الفصل لا يُنهي الخدمة هنا: المخالصة وإخلاء الطرف وإرجاع
        # العهد خطوات تالية (ق-54). والاعتماد يفتح الباب لها.
        out["settlement_due"] = True

    if fields:
        emp.save(update_fields=fields + ["updated_at"])

    # الدور في النظام
    if change.new_role_code:
        out["role"] = _switch_role(emp, change.new_role_code)

    # ق-79: البديل يخلفه في موقعه من تاريخ السريان
    if change.successor_id:
        from apps.leaves.services.delegation import (DelegationError,
                                                     appoint_successor,
                                                     successor_of)
        if successor_of(emp) is None:
            try:
                appoint_successor(
                    leaving=emp, successor=change.successor,
                    effective_from=change.effective_from, actor=actor,
                    note=f"خلافة بموجب {change.get_change_type_display()}")
                out["successor"] = change.successor.person.display_name
            except DelegationError as e:
                out["successor_error"] = str(e)

    return out


def _switch_role(employment, new_code):
    """يبدّل دور الموظف في النظام — بلا مساس بالاستثناءات الشخصية."""
    from apps.accounts.models_access import Role, RoleAssignment
    from apps.accounts.services.roles import DEFAULT_ROLES

    user = getattr(getattr(employment, "person", None), "user", None)
    m = getattr(user, "account_membership", None)
    if m is None:
        return "لا حساب دخول"

    role = Role.objects.filter(
        account_id=employment.account_id, code=new_code).first()
    if role is None:
        return f"دور غير معروف: {new_code}"

    scope = next((sp["scope"].value for c, sp in DEFAULT_ROLES.items()
                  if c.value == new_code), "own")

    RoleAssignment.objects.filter(membership=m).delete()
    RoleAssignment.objects.create(
        membership=m, role=role, company_id=employment.company_id,
        scope=scope)
    return role.name_ar


def _ctx(change, **extra):
    return {
        "change_type": change.get_change_type_display(),
        "employee": change.employment.person.display_name,
        "effective_from": str(change.effective_from),
        **extra,
    }


def _notify_managers(change, event_key):
    """يُعلم مديري الموارد بما ينتظر قرارهم."""
    from apps.accounts.models_access import RoleAssignment
    from apps.notifications.bus import emit

    people = [
        a.membership.user.person.id
        for a in RoleAssignment.objects.filter(
            role__code="hr_manager",
            membership__account_id=change.account_id
        ).select_related("membership__user__person")
        if getattr(a.membership.user, "person", None)
    ]
    if people:
        emit(event_key, account_id=change.account_id,
             company_id=change.company_id, context=_ctx(change),
             recipients=people)


def _notify_creator(change, event_key, note=""):
    """يُعلم من سجّل التغيير بالقرار."""
    from apps.notifications.bus import emit

    if not change.created_by_person_id:
        return
    emit(event_key, account_id=change.account_id,
         company_id=change.company_id,
         context=_ctx(change, reason=f" — {note}" if note else ""),
         recipients=[change.created_by_person_id])
