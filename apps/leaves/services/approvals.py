"""
محرك سلسلة الاعتماد — التنفيذ الفعلي لما أُجّل في ق-18.

المبدأ الحاكم (ق-9): سلسلة افتراضية جاهزة تعدّلها الشركة بحرية.
درجة أو درجتان أو أكثر، وشروط تُحدد أيها ينطبق.

الموديولات تنادي resolve_approvers ولا تفحص الصلاحية مباشرة —
لهذا كان بناء المحرك الآن تغييرًا في ملف واحد لا إعادة كتابة.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.leaves.models import (
    ApprovalChain, ApprovalDecision, ApproverType, Request, RequestApproval,
    RequestStatus,
)


class ApprovalError(Exception):
    pass


@dataclass(frozen=True)
class Approver:
    employment_id: int
    step_order: int
    is_mandatory: bool = True
    sla_hours: int | None = None
    source: str = ""


# ══════════ اختيار السلسلة المناسبة ══════════

def _condition_matches(condition: dict, payload: dict) -> bool:
    """
    يفحص شرط السلسلة على بيانات الطلب.

    المشغّلات المدعومة: _gt _gte _lt _lte _eq _in
    مثال: {"days_gt": 5} أو {"amount_gte": 5000}
    """
    if not condition:
        return True

    for key, expected in condition.items():
        for suffix, test in (
            ("_gte", lambda a, b: a >= b),
            ("_lte", lambda a, b: a <= b),
            ("_gt", lambda a, b: a > b),
            ("_lt", lambda a, b: a < b),
            ("_in", lambda a, b: a in b),
            ("_eq", lambda a, b: a == b),
        ):
            if key.endswith(suffix):
                field_name = key[: -len(suffix)]
                actual = payload.get(field_name)
                if actual is None:
                    return False
                try:
                    if suffix == "_in":
                        if not test(actual, expected):
                            return False
                    else:
                        if not test(Decimal(str(actual)),
                                    Decimal(str(expected))):
                            return False
                except (TypeError, ValueError):
                    return False
                break
        else:
            # بلا لاحقة = مساواة مباشرة
            if payload.get(key) != expected:
                return False
    return True


# ترتيب الأدوار من الأعلى — لاختيار دور واحد لمن يحمل أكثر من دور
ROLE_RANK = ["ceo", "owner", "hr_manager", "hr_staff", "dept_manager",
             "supervisor", "employee"]


def requester_role(employment):
    """
    دور مقدّم الطلب — الأعلى إن حمل أكثر من دور (ق-71).

    السلسلة تُختار بموقع المُقدِّم لا بنوع الطلب وحده: فطلب مدير
    الإدارة لا يمر بمن يمر به طلب الموظف.
    """
    if employment is None:
        return "employee"
    user = getattr(getattr(employment, "person", None), "user", None)
    membership = getattr(user, "account_membership", None)
    if membership is None:
        return "employee"
    # ق-76: الملكية سيطرة إدارية لا موقع في سلسلة الاعتماد.
    #
    # فمالك الحساب غالبًا مدير الموارد — وحسابه بـowner جعل طلبه
    # يسلك سلسلة المدير العام بدل سلسلته. والدور الوظيفي وحده
    # يحدّد من يعتمد طلبه.

    codes = {a.role.code for a in
             membership.role_assignments.select_related("role")}
    for code in ROLE_RANK:
        if code in codes:
            return code
    return "employee"


def select_chain(*, company, request_type, payload, requester_employment=None):
    """
    يختار السلسلة المنطبقة — الأعلى أولوية أولًا.

    السلاسل المشروطة تُفحص قبل العامة، فسلسلة «إجازة تتجاوز 5 أيام»
    بأولوية 10 تسبق السلسلة العامة بأولوية 0.

    ودور المُقدِّم يُحقن في بيانات الفحص (ق-71) فتصير سلسلة مشروطة
    بـ{"requester_role": "supervisor"} ممكنة بلا تغيير المحرّك.
    """
    chains = ApprovalChain.objects.filter(
        company=company, request_type=request_type, is_active=True
    ).order_by("-priority").prefetch_related("steps")

    facts = dict(payload or {})
    facts["requester_role"] = requester_role(requester_employment)

    for chain in chains:
        if _condition_matches(chain.condition_json or {}, facts):
            return chain
    return None


# ══════════ حل المعتمِدين ══════════

def _resolve_step(step, requester_employment):
    """يحوّل درجة الاعتماد إلى ارتباطات وظيفية فعلية."""
    from apps.employees.models import Employment, EmploymentStatus

    company = requester_employment.company

    if step.approver_type == ApproverType.DIRECT_MANAGER:
        mgr = requester_employment.direct_manager
        return [mgr] if mgr else []

    if step.approver_type == ApproverType.DEPARTMENT_HEAD:
        dept = requester_employment.department
        if dept is None or dept.manager_employment_id is None:
            return []
        head = Employment.objects.filter(
            id=dept.manager_employment_id,
            status=EmploymentStatus.ACTIVE).first()
        return [head] if head else []

    if step.approver_type == ApproverType.SPECIFIC_PERSON:
        if step.approver_person_id is None:
            return []
        return list(Employment.objects.filter(
            person_id=step.approver_person_id, company=company,
            status=EmploymentStatus.ACTIVE))

    if step.approver_type == ApproverType.ROLE:
        qs = Employment.objects.filter(
            company=company, status=EmploymentStatus.ACTIVE,
            person__user__account_membership__role_assignments__role__code
            =step.approver_role_code,
        )
        # مربع «ضمن نفس الإدارة»: مشرفو إدارة أخرى لا شأن لهم
        # بغياب مدير هذه الإدارة
        if step.same_department:
            qs = qs.filter(department_id=requester_employment.department_id)
        return list(qs.distinct())

    return []


def resolve_approvers(*, request_obj=None, request_type=None, company=None,
                      requester_employment=None, payload=None,
                      permission_key=None, account_id=None):
    """
    يرجع المعتمِدين بالترتيب — الواجهة التي تناديها الموديولات.

    التوقيع متوافق مع الواجهة الصورية في apps/core/approvals/resolver.py
    التي بُنيت في السبرنت الثالث (ق-18).
    """
    if request_obj is not None:
        request_type = request_obj.request_type
        company = request_obj.company
        requester_employment = request_obj.employment
        payload = request_obj.payload

    if company is None or requester_employment is None:
        return []

    chain = select_chain(company=company, request_type=request_type,
                         payload=payload or {},
                         requester_employment=requester_employment)
    if chain is None:
        return []

    approvers = []
    for step in chain.steps.all():
        for emp in _resolve_step(step, requester_employment):
            if emp.id == requester_employment.id:
                continue          # لا يعتمد طلبه بنفسه
            approvers.append(Approver(
                employment_id=emp.id, step_order=step.step_order,
                is_mandatory=step.is_mandatory, sla_hours=step.sla_hours,
                source=step.approver_type,
            ))
    return approvers


def is_approval_engine_ready() -> bool:
    """صار True — المحرك مبنيّ (ق-18)."""
    return True


# ══════════ دورة حياة الطلب ══════════

@transaction.atomic
def submit_request(request_obj):
    """
    يرفع الطلب للاعتماد ويُنشئ سجلات الدرجات.

    بلا سلسلة معرّفة: الطلب يُعتمد تلقائيًا — الشركة لم تشترط اعتمادًا.
    """
    if request_obj.status not in (RequestStatus.DRAFT,):
        raise ApprovalError(
            f"لا يمكن رفع طلب حالته: {request_obj.get_status_display()}")

    approvers = resolve_approvers(request_obj=request_obj)
    now = timezone.now()

    if not approvers:
        request_obj.status = RequestStatus.APPROVED
        request_obj.submitted_at = now
        request_obj.closed_at = now
        request_obj.current_step = 0
        request_obj.save()
        return request_obj, []

    records = []
    for a in approvers:
        records.append(RequestApproval(
            account=request_obj.account, company=request_obj.company,
            request=request_obj, step_order=a.step_order,
            approver_employment_id=a.employment_id,
            due_at=(now + timedelta(hours=a.sla_hours)) if a.sla_hours else None,
        ))
    RequestApproval.objects.bulk_create(records)

    request_obj.status = RequestStatus.PENDING
    request_obj.submitted_at = now
    request_obj.current_step = min(a.step_order for a in approvers)
    request_obj.save()

    from apps.notifications.bus import emit
    emit("request.submitted", account_id=request_obj.account_id,
         company_id=request_obj.company_id,
         context={"request_no": request_obj.request_no,
                  "request_type": request_obj.get_request_type_display(),
                  "employee_name": request_obj.employment.person.display_name},
         recipients=[])
    return request_obj, approvers


@transaction.atomic
def decide(*, request_obj, approver_employment, decision, comment="",
           via="web"):
    """
    قرار اعتماد أو رفض.

    الرفض في أي درجة يُنهي الطلب. والاعتماد ينقله للدرجة التالية،
    فإن لم تبقَ درجة صار معتمدًا.
    """
    if request_obj.status != RequestStatus.PENDING:
        raise ApprovalError(
            f"الطلب ليس قيد الاعتماد: {request_obj.get_status_display()}")

    record = RequestApproval.objects.filter(
        request=request_obj, step_order=request_obj.current_step,
        approver_employment=approver_employment, decision="").first()
    if record is None:
        raise ApprovalError(
            "لست ضمن معتمِدي هذه الدرجة، أو سبق أن اتخذت قرارًا")

    record.decision = decision
    record.decided_at = timezone.now()
    record.comment = comment
    record.acted_via = via
    record.save()

    # سجل العمليات (ق-44)
    from apps.core.services.audit import log_action
    log_action(
        instance=request_obj, action=decision,
        actor=approver_employment.person,
        label=request_obj.request_no,
        summary=(f"{'اعتماد' if decision == 'approved' else 'رفض'} "
                 f"{request_obj.get_request_type_display()} "
                 f"بالدرجة {request_obj.current_step}"
                 + (f" — {comment}" if comment else "")),
        channel=via)

    from apps.notifications.bus import emit
    ctx = {"request_no": request_obj.request_no,
           "request_type": request_obj.get_request_type_display(),
           "reason": comment}

    if decision == ApprovalDecision.REJECTED:
        request_obj.status = RequestStatus.REJECTED
        request_obj.closed_at = timezone.now()
        request_obj.save()
        emit("request.rejected", account_id=request_obj.account_id,
             company_id=request_obj.company_id, context=ctx, recipients=[])
        return request_obj

    # ق-74: درجة الاعتماد يكفيها أول قرار — فالدرجة موقع لا أشخاص،
    # وشركة فيها خمسة موظفي موارد لا تنتظر خمس موافقات على إجازة.
    # ودرجة العلم وحدها تنتظر الجميع، فمقصدها أن يعلم كل واحد
    # منهم — وتأكيد واحد لا يحقّق علم البقية.
    if _step_is_acknowledgement(request_obj, request_obj.current_step):
        pending_same_step = RequestApproval.objects.filter(
            request=request_obj, step_order=request_obj.current_step,
            decision="").exists()
        if pending_same_step:
            return request_obj      # ننتظر بقية من يجب أن يعلموا

    # وفي درجة الاعتماد: من لم يقرّر تُغلق درجته بأثر أول قرار،
    # فلا تبقى معلّقة في صندوقه بعد أن مضى الطلب
    else:
        RequestApproval.objects.filter(
            request=request_obj, step_order=request_obj.current_step,
            decision="").update(decision=ApprovalDecision.DELEGATED,
                                decided_at=timezone.now())

    next_step = (RequestApproval.objects
                 .filter(request=request_obj,
                         step_order__gt=request_obj.current_step, decision="")
                 .order_by("step_order")
                 .values_list("step_order", flat=True).first())

    if next_step is None:
        request_obj.status = RequestStatus.APPROVED
        request_obj.closed_at = timezone.now()
        request_obj.save()

        # الطلب المعتمد يترك أثرًا حقيقيًا: سلفة تُنشأ، وبصمة
        # تُصحَّح، ويوم يُسجَّل حاضرًا (ق-54). فشل الأثر يُسجَّل
        # ولا يلغي الاعتماد — القرار الإداري تمّ.
        from apps.leaves.services.requests import apply_effect
        effect = apply_effect(request_obj)
        ctx["effect"] = effect

        emit("request.approved", account_id=request_obj.account_id,
             company_id=request_obj.company_id, context=ctx, recipients=[])
    else:
        request_obj.current_step = next_step
        request_obj.save()
        emit("request.pending_approval", account_id=request_obj.account_id,
             company_id=request_obj.company_id, context=ctx, recipients=[])

    return request_obj


def _step_is_acknowledgement(request_obj, step_order):
    """
    هل هذه الدرجة درجة علم؟ (ق-74)

    تُقرأ من السلسلة لا من سجل الاعتماد — فالسجل لا يحمل الوصف،
    والسلسلة هي مصدر التعريف.
    """
    chain = select_chain(
        company=request_obj.company, request_type=request_obj.request_type,
        payload=request_obj.payload or {},
        requester_employment=request_obj.employment)
    if chain is None:
        return False
    step = chain.steps.filter(step_order=step_order).first()
    return bool(step and step.is_acknowledgement)


def pending_for(employment):
    """طلبات بانتظار اعتماد هذا الموظف — لمكوّن اللوحة."""
    return Request.objects.filter(
        status=RequestStatus.PENDING,
        approvals__approver_employment=employment,
        approvals__decision="",
        approvals__step_order=models_f_current_step(),
    ).distinct()


def models_f_current_step():
    from django.db.models import F
    return F("current_step")


class CancelError(Exception):
    """لا يُلغى الطلب — رسالة تخبر بما يُفعل."""


@transaction.atomic
def cancel_request(*, request_obj, by_employment, reason=""):
    """
    مقدّم الطلب يسحبه ما لم ينظر فيه أحد (ق-81).

    فالخطأ في التقديم وارد، والرأي يتغيّر. لكن بعد أول قرار يكون
    معتمِد قد نظر وقرّر — وسحبه بعده يُهدر قراره ويربك السجل.

    والرصيد سليم: الإجازة تُخصم عند الاعتماد لا عند التقديم، فلا
    شيء يُردّ.
    """
    if request_obj.employment_id != by_employment.id:
        raise CancelError("لا يُلغي الطلب إلا مقدّمه")

    if request_obj.status != RequestStatus.PENDING:
        raise CancelError(
            f"الطلب {request_obj.get_status_display()} — لا يُلغى")

    decided = RequestApproval.objects.filter(
        request=request_obj).exclude(decision="").exists()
    if decided:
        raise CancelError(
            "بدأ الاعتماد — راجع معتمِدك ليرفضه إن أردت التراجع")

    request_obj.status = RequestStatus.CANCELLED
    request_obj.closed_at = timezone.now()
    request_obj.save(update_fields=["status", "closed_at", "updated_at"])

    # الدرجات المعلّقة تُغلق فلا تبقى في صناديق المعتمِدين
    RequestApproval.objects.filter(
        request=request_obj, decision="").update(
        decision=ApprovalDecision.DELEGATED, decided_at=timezone.now())

    from apps.core.services.audit import log_action
    log_action(
        instance=request_obj, action="update",
        actor=by_employment.person, label=request_obj.request_no,
        summary=f"ألغى مقدّمه الطلب{f' — {reason}' if reason else ''}",
        channel="web")

    return request_obj
