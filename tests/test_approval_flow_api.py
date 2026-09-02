"""
حرّاس مسار الاعتماد — طبقة الـAPI فوق محرّك السلسلة.

الفجوة: test_approvals.py يحرس المحرّك بخمسة عشر حارسًا لكن بلا
استدعاء HTTP واحد. فالخدمة محروسة والمسار الذي يستدعيها عارٍ —
وهناك عاشت علّتان كسرتا السلسلة الأساسية (موظف ← مشرف ← مدير
إدارة ← موارد) عند خطوتها الأولى:

  1. decide_request كان يفلتر الطلب بنطاق requests.approve قبل
     تمريره للمحرّك. والمشرف نطاقه team، فيُردّ عليه «الطلب غير
     موجود» وهو معتمِده الرسمي المسجَّل.
  2. apply_approved_leave كانت تُستدعى لكل نوع معتمد بلا شرط،
     وهي ترفض غير الإجازة صراحةً — فطلب تصحيح البصمة ينهار بـ500
     بعد أن يكون القرار قد اتُّخذ.
"""
from datetime import date

import json
import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import Request, RequestStatus, RequestType
from apps.leaves.services.approvals import submit_request


@pytest.fixture
def env(db):
    """مشرف بنطاق team، ومرؤوس تحته يقدّم الطلبات."""
    r = provision_account(slug="apiflow", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        u = User.objects.create_user(username="flow.sup", password="x")
        role = Role.objects.get(account=acc, code="supervisor")
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, role=role, company=comp, scope=Scope.TEAM.value)

        pm, _ = create_person(
            account=acc, first_name_ar="خالد", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011122233", mobile="0501112223", user=u)
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
               "user": u, "emp": emp}


def _make_request(env, no, rtype, payload):
    with account_scope(env["account_id"]):
        req = Request.objects.create(
            account=env["acc"], company=env["comp"], request_no=no,
            employment=env["emp"], request_type=rtype, payload=payload)
        submit_request(req)
        return req


def _client(env):
    c = Client()
    c.force_login(env["user"])
    return c


@pytest.mark.django_db(transaction=True)
def test_inbox_shows_pending_request(env):
    """
    صندوق الاعتمادات يعرض الطلب المنتظر.

    كان ينهار بـ500 على ApprovalDecision.PENDING — عضو غير موجود
    في النموذج. والواجهة تبلع الخطأ في catch فتُخفي القسم كله،
    فيبدو المشرف كمن لا يملك صلاحية اعتماد.
    """
    _make_request(env, "R-1", RequestType.LEAVE, {"days": 3})
    r = _client(env).get("/api/me/approvals/")

    assert r.status_code == 200, f"الصندوق ينهار: {r.status_code}"
    assert any(x["request_no"] == "R-1" for x in r.json())


@pytest.mark.django_db(transaction=True)
def test_assigned_approver_can_decide(env):
    """
    ⚠️ المعتمِد المكلَّف يقرّر — ولو خرج الطلب من نطاق عرضه.

    سجل RequestApproval هو التكليف. والنطاق يحكم ما تراه في
    القوائم، لا ما كُلّفت به شخصيًا.
    """
    req = _make_request(env, "R-2", RequestType.LEAVE,
                        {"days": 3, "start_date": "2026-03-01",
                         "end_date": "2026-03-03"})
    r = _client(env).post(
        f"/api/leaves/requests/{req.id}/decide/",
        data=json.dumps({"decision": "approved", "comment": "موافق"}),
        content_type="application/json")

    assert r.status_code == 200, (
        f"المعتمِد المكلَّف لا يستطيع القرار ({r.status_code}): "
        f"{r.content.decode()[:200]}")


@pytest.mark.django_db(transaction=True)
def test_non_leave_request_decides_without_crash(env):
    """
    اعتماد طلب غير إجازة لا ينهار.

    apply_approved_leave ترفض غير الإجازة صراحةً («ليس طلب إجازة»)،
    وكانت تُستدعى لكل نوع — فتصحيح البصمة ينهار بـ500 بعد أن يكون
    المحرّك قد طبّق أثره الصحيح.
    """
    req = _make_request(env, "R-3", RequestType.ATTENDANCE_FIX, {
        "work_date": "2026-03-02", "first_in": "08:00",
        "last_out": "16:00", "fix_target": "both", "reason": "نسيان"})

    r = _client(env).post(
        f"/api/leaves/requests/{req.id}/decide/",
        data=json.dumps({"decision": "approved"}),
        content_type="application/json")

    assert r.status_code == 200, (
        f"اعتماد تصحيح البصمة ينهار ({r.status_code}): "
        f"{r.content.decode()[:200]}")

    # الأثر الحقيقي: الطلب المعتمد يترك أثرًا — بصمة تُصحَّح.
    # فحص رمز الحالة وحده لا يكفي: try/except قد يبتلع الانهيار
    # ويعيد 200 بينما لم يحدث شيء.
    from apps.attendance.models import AttendanceDay
    with account_scope(env["account_id"]):
        req.refresh_from_db()
        assert req.status == RequestStatus.APPROVED, "الطلب لم يُعتمد"
        day = AttendanceDay.objects.filter(
            employment=env["emp"], work_date=date(2026, 3, 2)).first()
        assert day is not None, "أثر تصحيح البصمة لم يُطبَّق"
        assert day.first_in is not None, "وقت الحضور لم يُسجَّل"


@pytest.mark.django_db(transaction=True)
def test_rejection_closes_request(env):
    """الرفض يقطع السلسلة ويُنهي الطلب — لا ينتقل للدرجة التالية."""
    req = _make_request(env, "R-4", RequestType.LEAVE, {"days": 3})
    r = _client(env).post(
        f"/api/leaves/requests/{req.id}/decide/",
        data=json.dumps({"decision": "rejected", "comment": "غير مبرر"}),
        content_type="application/json")

    assert r.status_code == 200
    with account_scope(env["account_id"]):
        req.refresh_from_db()
        assert req.status == RequestStatus.REJECTED
        assert req.closed_at is not None


@pytest.mark.django_db(transaction=True)
def test_supervisor_assigns_request_to_subordinate(env):
    """
    ق-68: المشرف يقدّم طلبًا نيابةً عن مرؤوسه — الموظف ينسى فيسنده
    مشرفه، وهو أحد بنود شاشة المرؤوسين الأربعة.
    """
    r = _client(env).post("/api/requests/", data=json.dumps({
        "employment_id": env["emp"].id,
        "request_type": "permission",
        "payload": {"work_date": "2026-09-10", "from_time": "10:00",
                    "to_time": "12:00", "reason": "إسناد"},
    }), content_type="application/json")

    assert r.status_code == 201, (
        f"المشرف لا يستطيع الإسناد ({r.status_code}): "
        f"{r.content.decode()[:200]}")


@pytest.mark.django_db(transaction=True)
def test_supervisor_cannot_assign_outside_team(env):
    """
    ⚠️ الحارس المقابل: الإسناد محصور في الفريق.

    النطاق team هو ما يحمي — لا اسم الدور. فمن ليس مرؤوسًا للمشرف
    لا يستطيع الإسناد له ولو ملك requests.manage.
    """
    with account_scope(env["account_id"]):
        po, _ = create_person(
            account=env["acc"], first_name_ar="نايف",
            family_name_ar="الشمري", gender="male", nationality_code="SA",
            id_type="national_id", id_number="1088899900",
            mobile="0508889990")
        outsider, _, _ = create_employment(
            person=po, company=env["comp"], employee_no="E-9",
            join_date=date(2022, 1, 1))

    r = _client(env).post("/api/requests/", data=json.dumps({
        "employment_id": outsider.id,
        "request_type": "permission",
        "payload": {"work_date": "2026-09-10", "from_time": "10:00",
                    "to_time": "12:00", "reason": "إسناد"},
    }), content_type="application/json")

    assert r.status_code == 404, (
        f"المشرف أسند طلبًا لمن ليس مرؤوسه ({r.status_code}) — "
        f"النطاق team مخترق")
