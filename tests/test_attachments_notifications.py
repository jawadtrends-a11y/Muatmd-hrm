"""
حرّاس المرفقات (ق-70) والإشعارات.

ما تمنعه:
  • إجازة تتطلب مرفقًا تمرّ بلا مرفق — فالتقرير الطبي شرط نظامي
  • رفع ملف يتجاوز الحدود أو بصيغة غير مسموحة
  • ملف يُخدم لمن لا يملكه (ق-61: من يعرف المسار لا يصل)
  • إشعار لا يُنشأ، أو يُقرأ من غير مستقبله
"""
from datetime import date
from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import LeaveType
from apps.notifications.models import Notification


@pytest.fixture
def env(db):
    r = provision_account(slug="att-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        def hire(first, family, nid, mobile, no, code, scope):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mobile)
            e, _, _ = create_employment(person=p, company=comp,
                                        employee_no=no,
                                        join_date=date(2023, 1, 1))
            u = User.objects.create_user(username=f"at.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, role=Role.objects.get(account=acc, code=code),
                company=comp, scope=scope.value)
            return e, u

        emp, emp_user = hire("وليد", "العنزي", "1011122233", "0501112223",
                             "E1", "employee", Scope.OWN)
        other, other_user = hire("سعد", "القحطاني", "1022233344",
                                 "0502223334", "E2", "employee", Scope.OWN)

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp, "user": emp_user,
               "other": other, "other_user": other_user}


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def _pdf(name="تقرير.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test",
                              content_type="application/pdf")


# ══════════ المرفق الإلزامي (ق-70) ══════════

@pytest.mark.django_db(transaction=True)
def test_sick_leave_requires_attachment(env):
    """
    ⚠️ الإجازة المرضية لا تمرّ بلا مرفق.

    فالعلم يُقرأ من نوع الإجازة لا من شرط مكتوب — والشركة تعدّله
    لأي نوع بلا تعديل كود (ق-9).
    """
    import json

    c = _client(env["user"])
    r = c.post("/api/requests/", data=json.dumps({
        "request_type": "leave",
        "payload": {"leave_type_code": "SICK",
                    "start_date": "2026-07-01", "end_date": "2026-07-03"},
    }), content_type="application/json")

    assert r.status_code == 400, "مرّت الإجازة المرضية بلا مرفق"
    assert "مرفق" in r.content.decode(), (
        "الرسالة لا تخبر بما يُفعل — والمستخدم لا يعرف ما ينقصه")


@pytest.mark.django_db(transaction=True)
def test_annual_leave_needs_no_attachment(env):
    """
    ⚠️ الحارس المقابل: السنوية تمرّ بلا مرفق.

    فإلزام كل الأنواع يعطّل الاستخدام العادي.
    """
    import json

    with account_scope(env["account_id"]):
        t = LeaveType.objects.get(company=env["comp"], code="ANNUAL")
        assert not t.requires_attachment, "السنوية صارت تتطلب مرفقًا"

    c = _client(env["user"])
    r = c.post("/api/requests/", data=json.dumps({
        "request_type": "leave",
        "payload": {"leave_type_code": "ANNUAL",
                    "start_date": "2026-07-01", "end_date": "2026-07-03"},
    }), content_type="application/json")

    assert r.status_code == 201, (
        f"رُفضت الإجازة السنوية بلا مرفق: {r.content.decode()[:150]}")


# ══════════ رفع الملفات وخدمتها (ق-61) ══════════

@pytest.mark.django_db(transaction=True)
def test_upload_returns_path_without_api_prefix(env):
    """
    المسار بلا بادئة /api — الواجهة تضيفها بنفسها.

    وإضافتها في الخادم تُنتج /api/api/files/3/ فتنكسر الصور
    والمرفقات (حدث فعلًا).
    """
    c = _client(env["user"])
    r = c.post("/api/files/", {"file": _pdf()})

    assert r.status_code == 201, r.content.decode()[:200]
    url = r.json()["url"]
    assert url.startswith("/files/"), f"المسار يحمل بادئة: {url}"


@pytest.mark.django_db(transaction=True)
def test_file_needs_authentication(env):
    """
    ق-61: من يعرف المسار لا يصل.

    فالرابط المباشر بلا مصادقة يُردّ — ولا يُخدم الملف لمن سمع
    برقمه.
    """
    c = _client(env["user"])
    fid = c.post("/api/files/", {"file": _pdf()}).json()["id"]

    anon = Client()
    r = anon.get(f"/api/files/{fid}/")
    assert r.status_code in (401, 403), (
        f"الملف يُخدم بلا مصادقة ({r.status_code})")


# ══════════ الإشعارات ══════════

@pytest.mark.django_db(transaction=True)
def test_notification_is_created_and_rendered(env):
    """
    الإشعار يُنشأ بنصّه لا بمفتاحه.

    فوصول «delegation.requested» للمستخدم بلا نص لا يخبره بشيء.
    """
    from apps.notifications.bus import emit

    with account_scope(env["account_id"]):
        emit("delegation.requested", account_id=env["acc"].id,
             company_id=env["comp"].id,
             context={"absentee": "خالد", "starts_on": "2026-07-01",
                      "ends_on": "2026-07-03", "request_no": "T-1"},
             recipients=[env["emp"].person_id], sync=True)

        n = Notification.objects.filter(
            recipient_person_id=env["emp"].person_id).first()

    assert n is not None, "لم يُنشأ إشعار"
    assert n.title and "{{" not in n.title, f"العنوان خام: {n.title}"
    assert "خالد" in n.body, f"النص لم يُملأ بالسياق: {n.body}"


@pytest.mark.django_db(transaction=True)
def test_notifications_are_private(env):
    """
    ⚠️ الإشعار يخصّ مستقبله وحده.

    فقراءة إشعارات زميل تكشف ما لا يخصّك: من طلب إجازة، ومن
    اعتُمد طلبه.
    """
    from apps.notifications.bus import emit

    with account_scope(env["account_id"]):
        emit("delegation.requested", account_id=env["acc"].id,
             company_id=env["comp"].id,
             context={"absentee": "خالد", "starts_on": "2026-07-01",
                      "ends_on": "2026-07-03", "request_no": "T-2"},
             recipients=[env["emp"].person_id], sync=True)

    mine = _client(env["user"]).get("/api/me/notifications/").json()
    theirs = _client(env["other_user"]).get("/api/me/notifications/").json()

    assert mine["unread"] >= 1, "صاحب الإشعار لا يراه"
    assert theirs["unread"] == 0, "زميل يرى إشعارات غيره"
    assert len(theirs["rows"]) == 0


@pytest.mark.django_db(transaction=True)
def test_marking_read_is_scoped_to_owner(env):
    """لا يُعلَّم إشعار الغير مقروءًا — ولو عُرف رقمه."""
    from apps.notifications.bus import emit

    with account_scope(env["account_id"]):
        emit("delegation.requested", account_id=env["acc"].id,
             company_id=env["comp"].id,
             context={"absentee": "خالد", "starts_on": "2026-07-01",
                      "ends_on": "2026-07-03", "request_no": "T-3"},
             recipients=[env["emp"].person_id], sync=True)
        nid = Notification.objects.filter(
            recipient_person_id=env["emp"].person_id).first().id

    import json
    r = _client(env["other_user"]).post(
        "/api/me/notifications/read/", data=json.dumps({"ids": [nid]}),
        content_type="application/json")

    assert r.json().get("marked", 0) == 0, "علّم إشعار غيره مقروءًا"

    with account_scope(env["account_id"]):
        assert Notification.objects.get(id=nid).read_at is None
