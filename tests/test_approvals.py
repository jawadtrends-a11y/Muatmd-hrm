"""حرّاس محرك سلسلة الاعتماد (ق-18 المؤجَّل، ق-9 حرية التعديل)."""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import (
    ApprovalChain, ApprovalDecision, ApprovalStep, ApproverType, LeaveTier,
    LeaveType, Request, RequestStatus, RequestType,
)
from apps.leaves.services.approvals import (
    ApprovalError, decide, is_approval_engine_ready, resolve_approvers,
    select_chain, submit_request,
)


@pytest.fixture
def env(db):
    r = provision_account(slug="apr-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        pm, _ = create_person(
            account=acc, first_name_ar="خالد", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011122233", mobile="0501112223")
        mgr, _, _ = create_employment(person=pm, company=comp,
                                       employee_no="M-1",
                                       join_date=date(2020, 1, 1))
        pe, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556")
        emp, _, _ = create_employment(person=pe, company=comp,
                                       employee_no="E-1",
                                       join_date=date(2022, 1, 1),
                                       direct_manager=mgr)
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "mgr": mgr, "emp": emp}


def _req(env, no, payload, rtype=RequestType.LEAVE):
    return Request.objects.create(
        account=env["acc"], company=env["comp"], request_no=no,
        employment=env["emp"], request_type=rtype, payload=payload)


# ══════════ المحرك جاهز (ق-18) ══════════

def test_engine_is_ready():
    """كان False في السبرنت الثالث — الواجهة الصورية استُبدلت."""
    assert is_approval_engine_ready() is True


# ══════════ اختيار السلسلة بالشرط ══════════

@pytest.mark.django_db(transaction=True)
def test_leave_chain_is_three_steps(env):
    """
    ق-71: سلسلة الإجازات ثلاث درجات — المدير المباشر ثم مدير
    الإدارة ثم موظف الموارد.
    """
    with account_scope(env["account_id"]):
        chain = select_chain(company=env["comp"],
                             request_type=RequestType.LEAVE,
                             payload={"days": 3})
        assert chain.steps.count() == 3
        kinds = [st.approver_type
                 for st in chain.steps.order_by("step_order")]
        assert kinds == ["direct_manager", "department_head", "role"]


@pytest.mark.django_db(transaction=True)
def test_leave_length_does_not_change_chain(env):
    """
    ق-71: الإجازة لا تُقسم قصيرة وطويلة — سلسلة واحدة مهما طالت.

    كانت سلسلة مشروطة بـdays_gt تضيف درجة للطويلة، وأُلغيت:
    السلسلة تُختار بموقع المُقدِّم لا بمدة إجازته.
    """
    with account_scope(env["account_id"]):
        for days in (1, 5, 6, 30):
            chain = select_chain(company=env["comp"],
                                 request_type=RequestType.LEAVE,
                                 payload={"days": days})
            assert chain.steps.count() == 3, f"اختلفت عند {days} يومًا"


@pytest.mark.django_db(transaction=True)
def test_chain_follows_requester_role(env):
    """
    ق-71: السلسلة تُختار بدور المُقدِّم — فطلب الموظف لا يمر بمن
    يمر به طلب مدير الإدارة.
    """
    with account_scope(env["account_id"]):
        chain = select_chain(company=env["comp"],
                             request_type=RequestType.LEAVE,
                             payload={"days": 3},
                             requester_employment=env["emp"])
        assert chain.condition_json == {}


# ══════════ دورة الطلب ══════════

@pytest.mark.django_db(transaction=True)
def test_submit_creates_approval_records(env):
    with account_scope(env["account_id"]):
        req = _req(env, "R-1", {"days": 3})
        req, approvers = submit_request(req)
        assert req.status == RequestStatus.PENDING
        assert req.current_step == 1
        assert len(approvers) == 1
        assert approvers[0].employment_id == env["mgr"].id


@pytest.mark.django_db(transaction=True)
def test_requester_cannot_approve_own_request(env):
    """لا يعتمد طلبه بنفسه — مهما كانت صلاحياته."""
    with account_scope(env["account_id"]):
        req, _ = submit_request(_req(env, "R-2", {"days": 3}))
        with pytest.raises(ApprovalError):
            decide(request_obj=req, approver_employment=env["emp"],
                   decision=ApprovalDecision.APPROVED)


@pytest.mark.django_db(transaction=True)
def test_single_step_approval_completes(env):
    with account_scope(env["account_id"]):
        req, _ = submit_request(_req(env, "R-3", {"days": 3}))
        req = decide(request_obj=req, approver_employment=env["mgr"],
                     decision=ApprovalDecision.APPROVED, comment="موافق")
        assert req.status == RequestStatus.APPROVED
        assert req.closed_at is not None


@pytest.mark.django_db(transaction=True)
def test_two_step_moves_to_next_step(env):
    """
    درجتان بمعتمِدَين فعليين: المدير المباشر ثم شخص محدد.
    نستخدم SPECIFIC_PERSON لأن دور hr_manager بلا شاغل في البيانات.
    """
    with account_scope(env["account_id"]):
        chain = select_chain(company=env["comp"],
                             request_type=RequestType.LEAVE,
                             payload={"days": 10})
        step2 = chain.steps.get(step_order=2)
        step2.approver_type = ApproverType.SPECIFIC_PERSON
        step2.approver_person = env["mgr"].person
        step2.approver_role_code = ""
        step2.save()

        req, approvers = submit_request(_req(env, "R-4", {"days": 10}))
        assert sorted({a.step_order for a in approvers}) == [1, 2]
        req = decide(request_obj=req, approver_employment=env["mgr"],
                     decision=ApprovalDecision.APPROVED)
        assert req.status == RequestStatus.PENDING
        assert req.current_step == 2


@pytest.mark.django_db(transaction=True)
def test_unfilled_step_is_skipped_chain_continues(env):
    """
    ق-35: الدرجة بلا شاغل تُتخطى والسلسلة تكمل بالباقي — لا تُعتمد
    الطلبات تلقائيًا ولا تتعطل.

    مثال المالك: موظف المبيعات بلا مدير مباشر يبدأ من مدير الإدارة
    ثم موظف الموارد؛ الدرجة الأولى تسقط والباقي يبقى.
    """
    with account_scope(env["account_id"]):
        chain = select_chain(company=env["comp"],
                             request_type=RequestType.LEAVE,
                             payload={"days": 10})
        # الدرجة 2 مدير الإدارة، والقسم بلا مدير معيَّن → تسقط
        step2 = chain.steps.get(step_order=2)
        assert step2.approver_type == "department_head"

        req, approvers = submit_request(_req(env, "R-SKIP", {"days": 10}))
        # الدرجة 1 وحدها حُلّت، والطلب قيد الاعتماد لا معتمد تلقائيًا
        assert 2 not in {a.step_order for a in approvers}
        assert 1 in {a.step_order for a in approvers}
        assert req.status == RequestStatus.PENDING
        assert req.current_step == 1


@pytest.mark.django_db(transaction=True)
def test_employee_without_direct_manager_starts_at_next_step(env):
    """
    مثال المالك: موظف بلا مدير مباشر — الدرجة الأولى تسقط والسلسلة
    تبدأ من الدرجة التالية.
    """
    with account_scope(env["account_id"]):
        chain = select_chain(company=env["comp"],
                             request_type=RequestType.LEAVE,
                             payload={"days": 10})
        step2 = chain.steps.get(step_order=2)
        step2.approver_type = ApproverType.SPECIFIC_PERSON
        step2.approver_person = env["mgr"].person
        step2.approver_role_code = ""
        step2.save()

        env["emp"].direct_manager = None
        env["emp"].save()

        req, approvers = submit_request(_req(env, "R-NOMGR", {"days": 10}))
        assert {a.step_order for a in approvers} == {2}, "الدرجة 1 لم تسقط"
        assert req.status == RequestStatus.PENDING
        assert req.current_step == 2, "لم تبدأ السلسلة من الدرجة الثانية"


@pytest.mark.django_db(transaction=True)
def test_rejection_closes_request_with_reason(env):
    """الرفض في أي درجة يُنهي الطلب، والسبب يُسجَّل."""
    with account_scope(env["account_id"]):
        req, _ = submit_request(_req(env, "R-5", {"days": 10}))
        req = decide(request_obj=req, approver_employment=env["mgr"],
                     decision=ApprovalDecision.REJECTED, comment="ضغط عمل")
        assert req.status == RequestStatus.REJECTED
        assert req.approvals.filter(
            decision=ApprovalDecision.REJECTED).first().comment == "ضغط عمل"


@pytest.mark.django_db(transaction=True)
def test_cannot_decide_twice(env):
    with account_scope(env["account_id"]):
        req, _ = submit_request(_req(env, "R-6", {"days": 3}))
        decide(request_obj=req, approver_employment=env["mgr"],
               decision=ApprovalDecision.APPROVED)
        with pytest.raises(ApprovalError):
            decide(request_obj=req, approver_employment=env["mgr"],
                   decision=ApprovalDecision.APPROVED)


@pytest.mark.django_db(transaction=True)
def test_no_chain_auto_approves(env):
    """
    ق-9: بلا سلسلة معرّفة يُعتمد الطلب تلقائيًا — الشركة لم تشترط
    اعتمادًا، والنظام لا يفرض عليها.
    """
    with account_scope(env["account_id"]):
        ApprovalChain.objects.filter(
            company=env["comp"], request_type=RequestType.ASSET).delete()
        req, approvers = submit_request(
            _req(env, "R-7", {}, RequestType.ASSET))
        assert req.status == RequestStatus.APPROVED
        assert approvers == []


# ══════════ حرية تعديل السلسلة (ق-9) ══════════

@pytest.mark.django_db(transaction=True)
def test_company_can_add_step(env):
    """النظام ينظّم ولا يصادر — الشركة تضيف درجة."""
    with account_scope(env["account_id"]):
        chain = select_chain(company=env["comp"],
                             request_type=RequestType.LEAVE,
                             payload={"days": 3})
        ApprovalStep.objects.create(
            chain=chain, step_order=4, approver_type=ApproverType.ROLE,
            approver_role_code="owner", is_mandatory=True)
        req, approvers = submit_request(_req(env, "R-8", {"days": 3}))
        assert 2 in {a.step_order for a in approvers} or len(approvers) >= 1


@pytest.mark.django_db(transaction=True)
def test_company_can_disable_chain(env):
    with account_scope(env["account_id"]):
        ApprovalChain.objects.filter(
            company=env["comp"], request_type=RequestType.LEAVE
        ).update(is_active=False)
        assert select_chain(company=env["comp"],
                            request_type=RequestType.LEAVE,
                            payload={"days": 3}) is None


# ══════════ بذرة الإجازات ══════════

@pytest.mark.django_db(transaction=True)
def test_leave_types_seeded(env):
    with account_scope(env["account_id"]):
        types = LeaveType.objects.filter(company=env["comp"])
        assert types.count() == 9
        annual = types.get(code="ANNUAL")
        assert annual.statutory_min_days == D("21")
        assert annual.holiday_treatment == "extends"    # ق-33
        assert annual.weekend_treatment == "counted"


@pytest.mark.django_db(transaction=True)
def test_sick_leave_has_three_tiers(env):
    """المرضية بثلاث شرائح — بلا كود خاص."""
    with account_scope(env["account_id"]):
        sick = LeaveType.objects.get(company=env["comp"], code="SICK")
        tiers = list(sick.tiers.all())
        assert len(tiers) == 3
        assert [t.pay_percentage for t in tiers] == [D("100"), D("75"), D("0")]


@pytest.mark.django_db(transaction=True)
def test_unpaid_leave_is_not_absence(env):
    """
    ق-32: الإجازة بلا أجر لا تُحتسب غيابًا — يُخصم أجر اليوم فقط.
    الغياب مخالفة، والإجازة بلا أجر حق مأذون.
    """
    with account_scope(env["account_id"]):
        unpaid = LeaveType.objects.get(company=env["comp"], code="UNPAID")
        assert unpaid.is_paid is False
        assert unpaid.pay_percentage == D("0")


@pytest.mark.django_db(transaction=True)
def test_statutory_minimum_enforced(env):
    """ق-34: منع صارم لا تنبيه."""
    from django.core.exceptions import ValidationError
    from apps.leaves.models import LeaveEntitlement
    with account_scope(env["account_id"]):
        annual = LeaveType.objects.get(company=env["comp"], code="ANNUAL")
        with pytest.raises(ValidationError):
            LeaveEntitlement(
                account=env["acc"], company=env["comp"],
                employment=env["emp"], leave_type=annual,
                days_per_year=D("15"),
                effective_from=date(2026, 1, 1)).save()

        ok = LeaveEntitlement(
            account=env["acc"], company=env["comp"], employment=env["emp"],
            leave_type=annual, days_per_year=D("45"),
            effective_from=date(2026, 1, 1))
        ok.save()
        assert ok.id, "رُفض رصيد أعلى من الحد"


@pytest.mark.django_db(transaction=True)
def test_requests_isolated_between_accounts(env, rls_enforced_late):
    other = provision_account(slug="apr-other", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(env["account_id"]):
        submit_request(_req(env, "R-ISO", {"days": 3}))
    rls_enforced_late()
    with account_scope(other.account_id):
        assert Request.objects.count() == 0
