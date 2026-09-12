"""
سلسلة موافقات المسير (ق-140).

⚠️ **وبلا سلسلة يُعتمد مباشرةً** — فلا نكسر من لا يحتاجها.
"""
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class ChainError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def steps_for(company):
    """خطوات السلسلة المفعّلة بترتيبها."""
    from apps.payroll.models import PayrollApprovalStep

    return list(PayrollApprovalStep.objects
                .filter(company=company, is_active=True)
                .select_related("role").order_by("step_order"))


@transaction.atomic
def build(*, run):
    """
    يبني اعتمادات المسير من سلسلة شركته.

    ⚠️ **ويُعاد البناء عند كل رفع**: فمسيرٌ رُفض ثم صُحّح يبدأ
    السلسلة من أوّلها — ومن اعتمد نسخةً لا يُعدّ معتمدًا لأخرى.
    """
    from apps.payroll.models import PayrollApproval

    PayrollApproval.objects.filter(run=run).delete()

    steps = steps_for(run.company)
    if not steps:
        return []

    now = timezone.now()
    rows = []
    for st in steps:
        rows.append(PayrollApproval(
            account_id=run.account_id, company_id=run.company_id,
            run=run, step_order=st.step_order, role=st.role,
            title=st.title,
            due_at=(now + timezone.timedelta(hours=st.sla_hours)
                    if st.sla_hours else None)))
    PayrollApproval.objects.bulk_create(rows)
    return rows


def current_step(run):
    """الخطوة المنتظِرة — أو None إن اكتملت."""
    from apps.payroll.models import PayrollApproval, PayrollApprovalDecision

    return (PayrollApproval.objects
            .filter(run=run, decision=PayrollApprovalDecision.PENDING)
            .order_by("step_order").first())


def can_decide(user, approval):
    """
    أيملك هذا المستخدم قرار هذه الخطوة؟

    **بالدور لا بالشخص** — فمن غاب حلّ محلّه من يحمل دوره.
    """
    from apps.accounts.models_access import RoleAssignment

    person = getattr(user, "person", None)
    if person is None:
        return False

    return RoleAssignment.objects.filter(
        membership__user=user, role_id=approval.role_id).exists()


@transaction.atomic
def decide(*, run, user, approve, note=""):
    """
    قرارٌ على الخطوة المنتظِرة.

    ⚠️ **والرفض يُعيد المسير للتصحيح** — لا يُلغيه: فالعمل
    المحتسَب لا يُهدر، والسبب مكتوبٌ ليُعالَج.
    """
    from apps.payroll.models import (
        PayrollApprovalDecision, PayrollRunStatus)

    step = current_step(run)
    if step is None:
        raise ChainError("لا خطوة منتظِرة في هذا المسير")
    if not can_decide(user, step):
        raise ChainError(
            f"هذه الخطوة لدور «{step.role.name_ar}» — وليس لك")

    person = getattr(user, "person", None)
    step.decision = (PayrollApprovalDecision.APPROVED if approve
                     else PayrollApprovalDecision.REJECTED)
    step.decided_by_person_id = getattr(person, "id", None)
    step.decided_by_name = getattr(person, "display_name", "") or ""
    step.decided_at = timezone.now()
    step.note = (note or "")[:255]
    step.save()

    if not approve:
        # ⚠️ يعود للتصحيح لا للإلغاء
        run.status = PayrollRunStatus.CALCULATED
        run.submitted_at = None
        run.save(update_fields=["status", "submitted_at", "updated_at"])
        logger.info("رُفض المسير %s في الخطوة %s", run.run_no,
                    step.step_order)
        return {"rejected": True, "step": step.step_order,
                "note": step.note}

    remaining = current_step(run)
    if remaining is None:
        # اكتملت السلسلة — يصير جاهزًا للاعتماد النهائيّ
        logger.info("اكتملت سلسلة المسير %s", run.run_no)
        return {"completed": True}

    return {"next_step": remaining.step_order,
            "next_role": remaining.role.name_ar}


def chain_state(run):
    """حالة السلسلة — للعرض."""
    from apps.payroll.models import PayrollApproval

    rows = (PayrollApproval.objects.filter(run=run)
            .select_related("role").order_by("step_order"))
    cur = current_step(run)
    return {
        "has_chain": rows.exists(),
        "current_step": cur.step_order if cur else None,
        "completed": rows.exists() and cur is None,
        "steps": [{
            "step_order": r.step_order,
            "title": r.title or r.role.name_ar,
            "role": r.role.name_ar,
            "decision": r.decision,
            "decided_by": r.decided_by_name,
            "decided_at": r.decided_at,
            "note": r.note,
            "due_at": r.due_at,
        } for r in rows],
    }
