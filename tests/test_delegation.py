"""
حرّاس الإنابة أثناء الغياب (ق-75) ودرجة العلم (ق-74).

ما تمنعه:
  • الإنابة تُفرض بلا قبول — والقرار للنائب لا للغائب
  • النائب من خارج الإدارة — فهو لا يعرف عمل من ينوب عنه
  • المهام لا تنتقل بعد القبول — فلا معنى لقبولها
  • تنتقل قبل المدة أو بعدها — والتفويض بتاريخه لا بقرار يدوي
  • درجة العلم يكفيها أول تأكيد — ومقصدها أن يعلم الجميع
  • درجة الاعتماد تنتظر الجميع — فيعطّلها غياب أحدهم
"""
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.access.gate import Gate
from apps.core.tenancy.context import account_scope
from apps.employees.models import Employment
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import (Delegation, DelegationStatus, Request,
                                RequestType)
from apps.leaves.services.delegation import (DelegationError,
                                             create_delegation,
                                             decide_delegation,
                                             eligible_deputies)
from apps.organization.models import Department


@pytest.fixture
def env(db):
    """
    إدارتان: المشاريع فيها مشرفان وموظف، والعمليات فيها مشرف.

    الثانية هي المهمة: بلاها لا نعرف إن كان النائب يُختار من
    الإدارة أم من كل الشركة.
    """
    r = provision_account(slug="deleg-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        prj = Department.objects.create(account=acc, company=comp,
                                        name_ar="المشاريع", code="PRJ")
        ops = Department.objects.create(account=acc, company=comp,
                                        name_ar="العمليات", code="OPS")

        def hire(first, family, nid, mobile, no, code, scope, dept):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mobile)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=date(2023, 1, 1), department=dept)
            u = User.objects.create_user(username=f"dt.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, role=Role.objects.get(account=acc, code=code),
                company=comp, scope=scope.value)
            return e

        mgr = hire("نايف", "البقمي", "1011122233", "0501112223", "M1",
                   "dept_manager", Scope.COMPANY, prj)
        sup1 = hire("خالد", "الحربي", "1022233344", "0502223334", "S1",
                    "supervisor", Scope.TEAM, prj)
        sup2 = hire("سلطان", "الرشيدي", "1033344455", "0503334445", "S2",
                    "supervisor", Scope.TEAM, prj)
        emp = hire("وليد", "العنزي", "1044455566", "0504445556", "E1",
                   "employee", Scope.OWN, prj)
        outsider = hire("ماجد", "الدوسري", "1055566677", "0505556667", "S9",
                        "supervisor", Scope.TEAM, ops)

        prj.manager_employment_id = mgr.id
        prj.save(update_fields=["manager_employment_id"])
        for e in (sup1, sup2):
            e.direct_manager = mgr
            e.save(update_fields=["direct_manager"])
        emp.direct_manager = sup1
        emp.save(update_fields=["direct_manager"])

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "mgr": mgr, "sup1": sup1, "sup2": sup2, "emp": emp,
               "outsider": outsider, "prj": prj}


def _leave(env, emp, no, start, end):
    """طلب إجازة بلا سلسلة — نفحص الإنابة لا الاعتماد."""
    return Request.objects.create(
        account=env["acc"], company=env["comp"], request_no=no,
        employment=emp, request_type=RequestType.LEAVE,
        payload={"start_date": str(start), "end_date": str(end)})


# ══════════ اختيار النائب ══════════

@pytest.mark.django_db(transaction=True)
def test_deputies_are_department_colleagues(env):
    """
    المرشحون زملاء الإدارة — فالنائب يقوم بعمل من ينوب عنه،
    ومن هو خارج الإدارة لا يعرفه.
    """
    with account_scope(env["account_id"]):
        ids = set(eligible_deputies(env["sup1"]).values_list("id", flat=True))

    assert env["sup2"].id in ids, "زميله في الإدارة ليس مرشحًا"
    assert env["outsider"].id not in ids, (
        "مشرف إدارة أخرى مرشَّح — النائب يجب أن يكون من الإدارة")
    assert env["sup1"].id not in ids, "الموظف مرشَّح لينوب عن نفسه"


@pytest.mark.django_db(transaction=True)
def test_cannot_delegate_to_self(env):
    """لا يُناب الموظف عن نفسه — والرسالة تخبر بما يُفعل."""
    with account_scope(env["account_id"]):
        req = _leave(env, env["sup1"], "D-1",
                     date(2026, 5, 1), date(2026, 5, 3))
        with pytest.raises(DelegationError) as e:
            create_delegation(request_obj=req,
                              deputy_employment=env["sup1"],
                              starts_on=date(2026, 5, 1),
                              ends_on=date(2026, 5, 3))
        assert "زميل" in str(e.value)


# ══════════ القبول والرفض ══════════

@pytest.mark.django_db(transaction=True)
def test_delegation_starts_pending(env):
    """
    ⚠️ الإنابة تُقبل لا تُفرض: تُنشأ معلّقة بانتظار النائب.

    فإنشاؤها مقبولةً يعني أن زميلًا يجد نفسه مسؤولًا بلا علمه.
    """
    with account_scope(env["account_id"]):
        req = _leave(env, env["sup1"], "D-2",
                     date(2026, 5, 1), date(2026, 5, 3))
        d = create_delegation(request_obj=req,
                              deputy_employment=env["sup2"],
                              starts_on=date(2026, 5, 1),
                              ends_on=date(2026, 5, 3))
        assert d.status == DelegationStatus.PENDING
        assert d.decided_at is None


@pytest.mark.django_db(transaction=True)
def test_only_deputy_decides(env):
    """القرار للنائب وحده — لا للغائب ولا لغيره."""
    with account_scope(env["account_id"]):
        req = _leave(env, env["sup1"], "D-3",
                     date(2026, 5, 1), date(2026, 5, 3))
        d = create_delegation(request_obj=req,
                              deputy_employment=env["sup2"],
                              starts_on=date(2026, 5, 1),
                              ends_on=date(2026, 5, 3))
        with pytest.raises(DelegationError):
            decide_delegation(delegation=d,
                              deputy_employment=env["sup1"], accept=True)


@pytest.mark.django_db(transaction=True)
def test_decision_is_final(env):
    """القرار لا يُعاد — سجل لا يُعدَّل بعد اتخاذه."""
    with account_scope(env["account_id"]):
        req = _leave(env, env["sup1"], "D-4",
                     date(2026, 5, 1), date(2026, 5, 3))
        d = create_delegation(request_obj=req,
                              deputy_employment=env["sup2"],
                              starts_on=date(2026, 5, 1),
                              ends_on=date(2026, 5, 3))
        decide_delegation(delegation=d,
                          deputy_employment=env["sup2"], accept=True)
        with pytest.raises(DelegationError):
            decide_delegation(delegation=d,
                              deputy_employment=env["sup2"], accept=False)


# ══════════ انتقال المهام ══════════

@pytest.mark.django_db(transaction=True)
def test_accepted_delegation_transfers_team(env):
    """
    ⚠️ الحارس الحرج: المهام تنتقل فعلًا بعد القبول.

    فلا معنى لقبول إنابة يبقى معها الفريق محجوبًا — والنائب
    يرى مرؤوسي الغائب كما يراهم صاحبهم.
    """
    today = date.today()
    with account_scope(env["account_id"]):
        before = set(Gate.filter_queryset(
            env["sup2"].person.user, "employees.view",
            Employment.objects.all()).values_list("id", flat=True))
        assert env["emp"].id not in before, "يراه قبل الإنابة أصلًا"

        req = _leave(env, env["sup1"], "D-5", today, today)
        d = create_delegation(request_obj=req,
                              deputy_employment=env["sup2"],
                              starts_on=today, ends_on=today)
        decide_delegation(delegation=d,
                          deputy_employment=env["sup2"], accept=True)

        after = set(Gate.filter_queryset(
            env["sup2"].person.user, "employees.view",
            Employment.objects.all()).values_list("id", flat=True))

    assert env["emp"].id in after, (
        "المهام لم تنتقل بعد قبول الإنابة — فلا معنى للقبول")


@pytest.mark.django_db(transaction=True)
def test_declined_delegation_transfers_nothing(env):
    """
    ⚠️ الحارس المقابل: الاعتذار لا ينقل شيئًا.

    وإجازة الغائب تمضي كما هي — فرفض زميل لا يمنع حقه فيها.
    """
    today = date.today()
    with account_scope(env["account_id"]):
        req = _leave(env, env["sup1"], "D-6", today, today)
        d = create_delegation(request_obj=req,
                              deputy_employment=env["sup2"],
                              starts_on=today, ends_on=today)
        decide_delegation(delegation=d,
                          deputy_employment=env["sup2"], accept=False)

        seen = set(Gate.filter_queryset(
            env["sup2"].person.user, "employees.view",
            Employment.objects.all()).values_list("id", flat=True))
        req.refresh_from_db()

    assert env["emp"].id not in seen, "نُقلت المهام رغم الاعتذار"
    assert req.status != "cancelled", "أُلغيت الإجازة باعتذار زميل"


@pytest.mark.django_db(transaction=True)
def test_delegation_respects_its_dates(env):
    """
    ⚠️ التفويض بتاريخه: لا قبله ولا بعده.

    فإنابة الشهر القادم لا تنقل المهام اليوم — والتفعيل تلقائي
    بلا زر ولا مهمة مجدولة.
    """
    future = date.today() + timedelta(days=30)
    with account_scope(env["account_id"]):
        req = _leave(env, env["sup1"], "D-7", future, future)
        d = create_delegation(request_obj=req,
                              deputy_employment=env["sup2"],
                              starts_on=future, ends_on=future)
        decide_delegation(delegation=d,
                          deputy_employment=env["sup2"], accept=True)

        seen = set(Gate.filter_queryset(
            env["sup2"].person.user, "employees.view",
            Employment.objects.all()).values_list("id", flat=True))

    assert env["emp"].id not in seen, (
        "المهام انتقلت قبل بداية الإنابة")


# ══════════ درجة العلم (ق-74) ══════════

@pytest.mark.django_db(transaction=True)
def test_acknowledgement_step_waits_for_all(env):
    """
    ⚠️ درجة العلم تنتظر الجميع — فمقصدها أن يعلم كل واحد منهم،
    وتأكيد واحد لا يحقّق علم البقية.
    """
    from apps.leaves.models import ApprovalChain, ApprovalDecision
    from apps.leaves.services.approvals import decide, submit_request

    with account_scope(env["account_id"]):
        ch = ApprovalChain.objects.get(
            request_type="leave",
            condition_json={"requester_role": "dept_manager"})
        st = ch.steps.get(step_order=1)
        assert st.is_acknowledgement, "درجة المشرفين ليست علمًا"

        req = _leave(env, env["mgr"], "A-1",
                     date(2026, 6, 1), date(2026, 6, 3))
        req, approvers = submit_request(req)
        step1 = {a.employment_id for a in approvers if a.step_order == 1}
        assert step1 == {env["sup1"].id, env["sup2"].id}, (
            f"معتمِدو درجة العلم غير المشرفَين: {step1}")

        # أول تأكيد لا يُمضي السلسلة
        req = decide(request_obj=req, approver_employment=env["sup1"],
                     decision=ApprovalDecision.APPROVED)
        assert req.current_step == 1, (
            "السلسلة مضت بتأكيد واحد — ودرجة العلم تنتظر الجميع")

        # والثاني يُمضيها — إما لدرجة تالية أو لاكتمال الطلب
        req = decide(request_obj=req, approver_employment=env["sup2"],
                     decision=ApprovalDecision.APPROVED)
        moved = req.current_step > 1 or req.status != "pending"
        assert moved, (
            f"السلسلة لم تمضِ بعد تأكيد الجميع — "
            f"الدرجة {req.current_step} والحالة {req.status}")


@pytest.mark.django_db(transaction=True)
def test_approval_step_needs_one_decision(env):
    """
    ق-74 بالمقابل: درجة الاعتماد يكفيها أول قرار.

    فشركة فيها خمسة موظفي موارد لا تنتظر خمس موافقات، وغياب
    أحدهم لا يعطّل الطلب.
    """
    from apps.leaves.models import (ApprovalDecision, RequestApproval)
    from apps.leaves.services.approvals import decide, submit_request

    with account_scope(env["account_id"]):
        req = _leave(env, env["emp"], "A-2",
                     date(2026, 6, 1), date(2026, 6, 3))
        req, approvers = submit_request(req)
        first = req.current_step
        who = RequestApproval.objects.filter(
            request=req, step_order=first, decision="").first()

        req = decide(request_obj=req,
                     approver_employment=who.approver_employment,
                     decision=ApprovalDecision.APPROVED)

        assert req.current_step != first or req.status != "pending", (
            "الدرجة لم تمضِ بأول قرار — وهي درجة اعتماد لا علم")


@pytest.mark.django_db(transaction=True)
def test_acknowledgement_stays_in_department(env):
    """
    ق-71: درجة العلم محصورة في إدارة مقدّم الطلب.

    فمشرف إدارة أخرى لا شأن له بغياب مدير هذه الإدارة.
    """
    from apps.leaves.services.approvals import submit_request

    with account_scope(env["account_id"]):
        req = _leave(env, env["mgr"], "A-3",
                     date(2026, 6, 1), date(2026, 6, 3))
        req, approvers = submit_request(req)
        step1 = {a.employment_id for a in approvers if a.step_order == 1}

    assert env["outsider"].id not in step1, (
        "مشرف إدارة أخرى في درجة العلم — النطاق مخترق")
