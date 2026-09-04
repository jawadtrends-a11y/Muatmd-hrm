"""
حرّاس الملكية (ق-79 أ) والخلافة (ق-79 ب) والإلغاء (ق-81).

ما تمنعه:
  • حساب بلا مالك — فتُقفل السيطرة الإدارية
  • نزع ملكية المؤسس — وهي محمية حتى يُحذف من الشركة
  • مغادرة موقع إداري بلا خليفة — فتنقطع سلاسل الموافقات
  • خلافة تسري قبل الاعتماد — وقد يُرفض الطلب
  • إلغاء طلب بعد أن قرّر فيه معتمِد — فيُهدر قراره
  • ظهور الملغى لمن لم يصله
"""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (AccountMembership, Role,
                                         RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.access.gate import Gate
from apps.core.tenancy.context import account_scope
from apps.employees.models import Employment
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import (ApprovalDecision, Delegation, Request,
                                RequestApproval, RequestStatus)
from apps.leaves.services.approvals import (CancelError, cancel_request,
                                            decide, submit_request)
from apps.leaves.services.delegation import (DelegationError,
                                             appoint_successor,
                                             holds_admin_position,
                                             successor_of)


@pytest.fixture
def env(db):
    """مدير عام ومدير موارد ومشرف وموظفان — أدنى ما يكفي."""
    r = provision_account(slug="own-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        def hire(first, family, nid, mobile, no, code, scope, owner=False):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mobile)
            e, _, _ = create_employment(person=p, company=comp,
                                        employee_no=no,
                                        join_date=date(2023, 1, 1))
            u = User.objects.create_user(username=f"ow.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp,
                is_account_owner=owner, is_founding_owner=owner)
            RoleAssignment.objects.create(
                membership=m, role=Role.objects.get(account=acc, code=code),
                company=comp, scope=scope.value)
            return e

        # أسماء متباينة: حارس التشابه يمنع تكرار العائلة (ق-14)
        ceo = hire("هشام", "الشهري", "1011122233", "0501112223", "C1",
                   "ceo", Scope.ACCOUNT)
        hrm = hire("دانة", "المطيري", "1022233344", "0502223334", "H1",
                   "hr_manager", Scope.COMPANY, owner=True)
        sup = hire("خالد", "الحربي", "1033344455", "0503334445", "S1",
                   "supervisor", Scope.TEAM)
        sup2 = hire("سلطان", "الرشيدي", "1044455566", "0504445556", "S2",
                    "supervisor", Scope.TEAM)
        emp = hire("وليد", "العنزي", "1055566677", "0505556667", "E1",
                   "employee", Scope.OWN)

        emp.direct_manager = sup
        emp.save(update_fields=["direct_manager"])

        # قسم بمدير: فتصير سلسلة الموظف درجتين على الأقل، وإلا
        # أُغلق طلبه بأول قرار ولم يُفحص شرط الإلغاء (ق-81)
        from apps.organization.models import Department
        dept = Department.objects.create(
            account=acc, company=comp, name_ar="قسم", code="D1",
            manager_employment_id=sup2.id)
        for e in (emp, sup, sup2):
            e.department = dept
            e.save(update_fields=["department"])

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "ceo": ceo, "hrm": hrm, "sup": sup, "sup2": sup2, "emp": emp}


def _client(employment):
    c = Client()
    c.force_login(employment.person.user)
    return c


def _post(employment, path, body):
    import json
    return _client(employment).post(
        path, data=json.dumps(body), content_type="application/json")


# ══════════ ملكية الحساب (ق-79 أ) ══════════

@pytest.mark.django_db(transaction=True)
def test_owner_is_added_not_transferred(env):
    """
    الملكية تُضاف ولا تُنقل — الشركات الكبرى تحتاج أكثر من مالك
    لئلا يتوقف كل شيء بغياب واحد.
    """
    r = _post(env["ceo"], f"/api/access/members/{env['sup'].id}/ownership/",
              {"grant": True})
    assert r.status_code == 200, r.content.decode()[:200]

    with account_scope(env["account_id"]):
        owners = AccountMembership.objects.filter(
            account_id=env["account_id"], is_account_owner=True).count()
    assert owners == 2, f"الملكية نُقلت بدل أن تُضاف — الملاك {owners}"


@pytest.mark.django_db(transaction=True)
def test_founding_owner_is_protected(env):
    """
    ⚠️ المالك المؤسس لا تُنزع ملكيته — تُنقل بحذفه من الشركة.

    فنزعها بقرار غيره يفتح باب الانقلاب على من أسّس الحساب.
    """
    _post(env["ceo"], f"/api/access/members/{env['sup'].id}/ownership/",
          {"grant": True})
    r = _post(env["ceo"], f"/api/access/members/{env['hrm'].id}/ownership/",
              {"grant": False})

    assert r.status_code == 400, "نُزعت ملكية المؤسس"
    assert r.json().get("code") == "founding_owner"


@pytest.mark.django_db(transaction=True)
def test_last_owner_cannot_be_removed(env):
    """
    ⚠️ لا يُزال آخر مالك — فيبقى الحساب بلا سيطرة إدارية.
    """
    with account_scope(env["account_id"]):
        # نجعل المشرف المالك الوحيد غير المؤسس
        m = env["hrm"].person.user.account_membership
        m.is_founding_owner = False
        m.save(update_fields=["is_founding_owner"])

    r = _post(env["ceo"], f"/api/access/members/{env['hrm'].id}/ownership/",
              {"grant": False})
    assert r.status_code == 400, "أُزيل آخر مالك"
    assert r.json().get("code") == "last_owner"


@pytest.mark.django_db(transaction=True)
def test_only_owner_or_ceo_grants_ownership(env):
    """الملكية بيد مالكها أو المدير العام — لا غيرهما."""
    r = _post(env["sup"], f"/api/access/members/{env['sup2'].id}/ownership/",
              {"grant": True})
    assert r.status_code == 403, "منح مشرفٌ الملكية"


# ══════════ الخلافة (ق-79 ب) ══════════

@pytest.mark.django_db(transaction=True)
def test_admin_position_is_detected(env):
    """
    من يشغل موقعًا إداريًا يُعرف — والموظف العادي لا.

    فإلزام الجميع ببديل يعطّل الاستخدام، وإعفاء الجميع يقطع
    السلاسل.
    """
    with account_scope(env["account_id"]):
        assert holds_admin_position(env["sup"]), "المشرف ليس إداريًا"
        assert holds_admin_position(env["hrm"]), "مدير الموارد ليس إداريًا"
        assert not holds_admin_position(env["emp"]), "الموظف عُدّ إداريًا"


@pytest.mark.django_db(transaction=True)
def test_admin_cannot_resign_without_successor(env):
    """
    ⚠️ لا يفرغ موقع إداري بلا بديل — فتنقطع سلاسل الموافقات
    ويبقى المرؤوسون بلا مرجع.
    """
    r = _post(env["sup"], "/api/requests/", {
        "request_type": "resignation",
        "payload": {"termination_reason": "resignation",
                    "request_date": "2026-10-01"},
    })
    assert r.status_code == 400, "مرّت استقالة المشرف بلا بديل"
    assert r.json().get("code") == "successor_required"


@pytest.mark.django_db(transaction=True)
def test_employee_resigns_without_successor(env):
    """الحارس المقابل: الموظف العادي يمرّ — لا يعتمد ولا يدير."""
    r = _post(env["emp"], "/api/requests/", {
        "request_type": "resignation",
        "payload": {"termination_reason": "resignation",
                    "request_date": "2026-10-01"},
    })
    assert r.status_code == 201, r.content.decode()[:200]


@pytest.mark.django_db(transaction=True)
def test_successor_inherits_only_after_approval(env):
    """
    ⚠️ الخلافة تسري بالاعتماد لا بالتقديم (ق-80: وقت التسجيل غير
    تاريخ السريان) — فقد يُرفض الطلب.
    """
    with account_scope(env["account_id"]):
        before = set(Gate.filter_queryset(
            env["sup2"].person.user, "employees.view",
            Employment.objects.all()).values_list("id", flat=True))

    r = _post(env["sup"], "/api/requests/", {
        "request_type": "resignation",
        "payload": {"termination_reason": "resignation",
                    "request_date": str(date.today()),
                    "successor_employment_id": env["sup2"].id},
    })
    assert r.status_code == 201, r.content.decode()[:200]

    with account_scope(env["account_id"]):
        mid = set(Gate.filter_queryset(
            env["sup2"].person.user, "employees.view",
            Employment.objects.all()).values_list("id", flat=True))
        assert mid == before, "ورث الخليفة قبل اعتماد الطلب"

        # نمرّر السلسلة كاملة
        req = Request.objects.get(id=r.json()["id"])
        guard = 0
        while req.status == RequestStatus.PENDING and guard < 8:
            guard += 1
            a = RequestApproval.objects.filter(
                request=req, step_order=req.current_step,
                decision="").first()
            if a is None:
                break
            req = decide(request_obj=req,
                         approver_employment=a.approver_employment,
                         decision=ApprovalDecision.APPROVED)

        after = set(Gate.filter_queryset(
            env["sup2"].person.user, "employees.view",
            Employment.objects.all()).values_list("id", flat=True))

    assert req.status == RequestStatus.APPROVED, req.status
    assert env["emp"].id in after, "لم يرث الخليفة بعد الاعتماد"


@pytest.mark.django_db(transaction=True)
def test_successor_keeps_own_role(env):
    """
    الخليفة يبقى بدوره ويرث المهام — مشرف يخلف مديرًا يبقى مشرفًا.
    """
    with account_scope(env["account_id"]):
        appoint_successor(leaving=env["sup"], successor=env["sup2"],
                          effective_from=date.today())
        codes = {a.role.code for a in
                 env["sup2"].person.user.account_membership
                 .role_assignments.select_related("role")}
    assert codes == {"supervisor"}, f"تغيّر دور الخليفة: {codes}"


# ══════════ إلغاء الطلب (ق-81) ══════════

@pytest.mark.django_db(transaction=True)
def test_owner_cancels_before_any_decision(env):
    """مقدّم الطلب يسحبه ما لم ينظر فيه أحد."""
    with account_scope(env["account_id"]):
        req = Request.objects.create(
            account=env["acc"], company=env["comp"], request_no="C-1",
            employment=env["emp"], request_type="leave",
            payload={"days": 2})
        req, _ = submit_request(req)
        req = cancel_request(request_obj=req, by_employment=env["emp"])
    assert req.status == RequestStatus.CANCELLED


@pytest.mark.django_db(transaction=True)
def test_cannot_cancel_after_first_decision(env):
    """
    ⚠️ بعد أول قرار لا يُسحب — فمعتمِد نظر وقرّر، وسحبه بعده
    يُهدر قراره ويربك السجل.
    """
    with account_scope(env["account_id"]):
        req = Request.objects.create(
            account=env["acc"], company=env["comp"], request_no="C-2",
            employment=env["emp"], request_type="leave",
            payload={"days": 2})
        req, _ = submit_request(req)
        a = RequestApproval.objects.filter(request=req, decision="").first()
        assert a is not None, (
            "لا معتمِد للطلب — الحارس لا يفحص شيئًا بلا سلسلة")

        decide(request_obj=req,
               approver_employment=a.approver_employment,
               decision=ApprovalDecision.APPROVED)
        req.refresh_from_db()

        # الحارس يفحص شرط القرار لا شرط الحالة: لو أُغلق الطلب
        # باعتماد درجته الوحيدة، لصار الرفض بسبب الحالة ومرّ
        # الكسر بلا كشف.
        assert req.status == RequestStatus.PENDING, (
            "الطلب أُغلق بأول قرار — الحارس يفحص الحالة لا القرار")

        with pytest.raises(CancelError) as e:
            cancel_request(request_obj=req, by_employment=env["emp"])
        assert "بدأ الاعتماد" in str(e.value), str(e.value)


@pytest.mark.django_db(transaction=True)
def test_only_requester_cancels(env):
    """لا يُلغي الطلب إلا مقدّمه — لا مشرفه ولا غيره."""
    with account_scope(env["account_id"]):
        req = Request.objects.create(
            account=env["acc"], company=env["comp"], request_no="C-3",
            employment=env["emp"], request_type="leave",
            payload={"days": 2})
        req, _ = submit_request(req)
        with pytest.raises(CancelError):
            cancel_request(request_obj=req, by_employment=env["sup"])


@pytest.mark.django_db(transaction=True)
def test_cancelled_hidden_from_others(env):
    """
    ⚠️ الملغى يظهر لمقدّمه وحده — سحبه قبل أن ينظر فيه أحد، ولا
    شأن للمعتمِدين بما لم يصلهم.
    """
    with account_scope(env["account_id"]):
        req = Request.objects.create(
            account=env["acc"], company=env["comp"], request_no="C-4",
            employment=env["emp"], request_type="leave",
            payload={"days": 2})
        req, _ = submit_request(req)
        cancel_request(request_obj=req, by_employment=env["emp"])

    mine = _client(env["emp"]).get("/api/leaves/requests/").json()
    theirs = _client(env["hrm"]).get("/api/leaves/requests/").json()

    assert any(x["request_no"] == "C-4" for x in mine), "أُخفي عن مقدّمه"
    assert not any(x["request_no"] == "C-4" for x in theirs), (
        "الملغى ظاهر لمن لم يصله")

# ══════════ حذف حساب الدخول والخلافة (ق-79) ══════════

@pytest.mark.django_db(transaction=True)
def test_login_removal_keeps_employment(env):
    """
    ⚠️ يُحذف حساب الدخول لا الملف الوظيفي.

    فالسجل لا يُمحى (ق-44): الموظف يبقى بملفه وطلباته وسجل
    عملياته، ويُنزع وصوله وحده.
    """
    r = _client(env["ceo"]).delete(
        f"/api/access/members/{env['sup'].id}/login/")
    assert r.status_code == 200, r.content.decode()[:200]

    env["sup"].refresh_from_db()
    assert env["sup"].id, "حُذف الملف الوظيفي"
    assert env["sup"].status == "active", "أُنهيت الخدمة بحذف الحساب"

    user = env["sup"].person.user
    user.refresh_from_db()
    assert not user.is_active, "بقي الوصول بعد الحذف"


@pytest.mark.django_db(transaction=True)
def test_founding_owner_heir_gets_protection(env):
    """
    ⚠️ حذف المؤسس ينقل وسمه لأقدم مالك بعده.

    فبلا ذلك يبقى الحساب بلا مالك محميّ، وتُنزع ملكية الجميع
    بقرار واحد.
    """
    _post(env["ceo"], f"/api/access/members/{env['sup'].id}/ownership/",
          {"grant": True})

    r = _client(env["ceo"]).delete(
        f"/api/access/members/{env['hrm'].id}/login/")
    assert r.status_code == 200, r.content.decode()[:200]

    with account_scope(env["account_id"]):
        owners = list(AccountMembership.objects.filter(
            account_id=env["account_id"], is_account_owner=True))

    assert len(owners) == 1, f"الملاك: {len(owners)}"
    assert owners[0].is_founding_owner, "لم يرث الخليفة الحماية"


@pytest.mark.django_db(transaction=True)
def test_hr_takes_over_when_owners_gone(env):
    """
    ⚠️ زال الملاك جميعًا فناب مدير الموارد — ولا يُترك حساب بلا
    من يديره.
    """
    # نجعل المشرف المالك الوحيد ثم نحذفه
    with account_scope(env["account_id"]):
        m = env["hrm"].person.user.account_membership
        m.is_account_owner = False
        m.is_founding_owner = False
        m.save(update_fields=["is_account_owner", "is_founding_owner"])
        sm = env["sup"].person.user.account_membership
        sm.is_account_owner = True
        sm.is_founding_owner = True
        sm.save(update_fields=["is_account_owner", "is_founding_owner"])

    r = _client(env["ceo"]).delete(
        f"/api/access/members/{env['sup'].id}/login/")
    assert r.status_code == 200, r.content.decode()[:200]

    with account_scope(env["account_id"]):
        owners = list(AccountMembership.objects.filter(
            account_id=env["account_id"], is_account_owner=True))

    assert owners, "الحساب بلا مالك — لا سيطرة إدارية عليه"
    codes = {a.role.code for a in owners[0].role_assignments.select_related(
        "role")}
    assert codes & {"hr_manager", "hr_staff"}, (
        f"ناب غير الموارد: {codes}")


@pytest.mark.django_db(transaction=True)
def test_cannot_delete_own_login(env):
    """لا يحذف أحد حسابه بنفسه — فيقفل الباب على نفسه."""
    r = _client(env["hrm"]).delete(
        f"/api/access/members/{env['hrm'].id}/login/")
    assert r.status_code == 400
    assert r.json().get("code") == "self_delete"


@pytest.mark.django_db(transaction=True)
def test_only_owner_or_ceo_removes_login(env):
    """حذف الوصول بيد مالك الحساب أو المدير العام."""
    r = _client(env["sup"]).delete(
        f"/api/access/members/{env['emp'].id}/login/")
    assert r.status_code == 403, "حذف مشرفٌ حساب غيره"
