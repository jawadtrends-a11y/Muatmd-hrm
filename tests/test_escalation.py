"""
حرّاس التصعيد عند التأخر (ق-87).

ما تمنعه:
  • تجاوز آخر درجة — فالصمت يصير اعتمادًا
  • تجاوز مدير الموارد أو المدير العام — فالوقت ينوب عن قرارهما
  • تصعيد قبل انقضاء المهلة
  • ضياع أثر التصعيد في السجل
"""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import (ApprovalChain, ApprovalStep, Request,
                                RequestApproval, RequestStatus)
from apps.leaves.services.approvals import (NO_SKIP_ROLES, _can_skip,
                                            escalate_overdue)


@pytest.fixture
def env(db):
    r = provision_account(slug="esc-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        p, _ = create_person(
            account=acc, first_name_ar="وليد", family_name_ar="العنزي",
            gender="male", nationality_code="SA",
            id_type="national_id", id_number="1044455566",
            mobile="0504445556")
        emp, _, _ = create_employment(person=p, company=comp,
                                      employee_no="E1",
                                      join_date=date(2023, 1, 1))

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp}


def _make_chain(env, steps):
    """
    سلسلة بدرجاتها — كل درجة (نوع، رمز دور، مهلة).
    """
    chain = ApprovalChain.objects.create(
        account=env["acc"], company=env["comp"],
        request_type="leave", name_ar="سلسلة اختبار", priority=999)

    for i, (kind, role, hours) in enumerate(steps, start=1):
        ApprovalStep.objects.create(
            chain=chain, step_order=i, approver_type=kind,
            approver_role_code=role, escalate_after_hours=hours)
    return chain


def _pending_request(env, chain, step_order=1, age_hours=48):
    """طلب قيد الاعتماد عند درجة، بدأ قبل ساعات."""
    req = Request.objects.create(
        account=env["acc"], company=env["comp"],
        request_no=f"T-{timezone.now().timestamp()}",
        employment=env["emp"], request_type="leave",
        status=RequestStatus.PENDING, current_step=step_order,
        payload={})

    rec = RequestApproval.objects.create(
        account=env["acc"], company=env["comp"],
        request=req, step_order=step_order,
        approver_employment=env["emp"], decision="")

    old = timezone.now() - timedelta(hours=age_hours)
    RequestApproval.objects.filter(id=rec.id).update(created_at=old)
    return req


# ══════════ الحدود ══════════

@pytest.mark.django_db(transaction=True)
def test_last_step_is_never_skipped(env):
    """
    ⚠️ الحارس الحرج: آخر درجة لا تُتجاوَز أيًّا كانت.

    فمن وصل الطلب عنده وهو الأخير يبقى حتى يقرّر — وتجاوزه يجعل
    الصمت اعتمادًا، ومسير رواتب يُعتمد بلا أن يراه أحد.
    """
    with account_scope(env["account_id"]):
        chain = _make_chain(env, [("direct_manager", "", 1)])
        req = _pending_request(env, chain, step_order=1, age_hours=99)

        res = escalate_overdue()
        req.refresh_from_db()

    assert res["escalated"] == 0, "صُعِّدت آخر درجة"
    assert req.current_step == 1
    assert req.status == RequestStatus.PENDING


@pytest.mark.django_db(transaction=True)
def test_hr_manager_is_never_skipped(env):
    """
    ⚠️ مدير الموارد لا يُتجاوَز — والوقت لا ينوب عن قراره.
    """
    with account_scope(env["account_id"]):
        chain = _make_chain(env, [
            ("role", "hr_manager", 1),
            ("role", "ceo", 1),
        ])
        req = _pending_request(env, chain, step_order=1, age_hours=99)

        res = escalate_overdue()
        req.refresh_from_db()

    assert res["escalated"] == 0, "تُجووِز مدير الموارد"
    assert req.current_step == 1


@pytest.mark.django_db(transaction=True)
def test_direct_manager_is_skipped_after_deadline(env):
    """
    المدير المباشر يُتجاوَز بعد مهلته — فالتصعيد يحرّك ما يُعطَّل
    بغيابه.
    """
    with account_scope(env["account_id"]):
        chain = _make_chain(env, [
            ("direct_manager", "", 24),
            ("role", "hr_manager", 0),
        ])
        req = _pending_request(env, chain, step_order=1, age_hours=48)

        res = escalate_overdue()
        req.refresh_from_db()

    assert res["escalated"] == 1, "لم يُصعَّد المتأخر"
    assert req.current_step == 2


@pytest.mark.django_db(transaction=True)
def test_no_escalation_before_deadline(env):
    """⚠️ لا تصعيد قبل انقضاء المهلة."""
    with account_scope(env["account_id"]):
        chain = _make_chain(env, [
            ("direct_manager", "", 48),
            ("role", "hr_manager", 0),
        ])
        req = _pending_request(env, chain, step_order=1, age_hours=2)

        res = escalate_overdue()
        req.refresh_from_db()

    assert res["escalated"] == 0, "صُعِّد قبل المهلة"
    assert req.current_step == 1


@pytest.mark.django_db(transaction=True)
def test_zero_hours_disables_escalation(env):
    """صفر ساعة يعني بلا تصعيد — فالمهلة اختيار لا فرض."""
    with account_scope(env["account_id"]):
        chain = _make_chain(env, [
            ("direct_manager", "", 0),
            ("role", "hr_manager", 0),
        ])
        req = _pending_request(env, chain, step_order=1, age_hours=999)

        res = escalate_overdue()
        req.refresh_from_db()

    assert res["escalated"] == 0
    assert req.current_step == 1


@pytest.mark.django_db(transaction=True)
def test_escalation_is_recorded(env):
    """
    ⚠️ التصعيد يُوسم في السجل.

    فالسجل يفرّق بين من قرّر ومن مضى الطلب دونه (ق-44) — وبلا
    الوسم يبدو المتجاوَز كأنه اعتمد.
    """
    with account_scope(env["account_id"]):
        chain = _make_chain(env, [
            ("direct_manager", "", 24),
            ("role", "hr_manager", 0),
        ])
        req = _pending_request(env, chain, step_order=1, age_hours=48)

        escalate_overdue()

        rec = RequestApproval.objects.get(request=req, step_order=1)

    assert rec.escalated is True, "لم يُوسم القرار مُصعَّدًا"
    assert rec.decision == "", "سُجّل قرارًا وهو تصعيد"


@pytest.mark.django_db(transaction=True)
def test_named_person_is_never_skipped(env):
    """
    الشخص المسمّى بعينه لا يُتجاوَز — فقد قُصد بذاته لا بدوره.
    """
    with account_scope(env["account_id"]):
        chain = ApprovalChain.objects.create(
            account=env["acc"], company=env["comp"],
            request_type="leave", name_ar="سلسلة", priority=999)
        step = ApprovalStep.objects.create(
            chain=chain, step_order=1,
            approver_type="specific_person",
            approver_person=env["emp"].person,
            escalate_after_hours=1)

        assert _can_skip(step) is False


@pytest.mark.django_db(transaction=True)
def test_protected_roles_are_explicit():
    """الأدوار المحميّة معلومة لا مستنتجة."""
    assert "hr_manager" in NO_SKIP_ROLES
    assert "ceo" in NO_SKIP_ROLES
    assert "owner" in NO_SKIP_ROLES
