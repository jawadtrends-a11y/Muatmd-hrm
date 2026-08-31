"""
حرّاس لوحة المنصة والانتحال (ق-46، ق-51).

أخطر ما فيها حارسان: جلسة عميل تُرفض من /platform/، والكتابة
أثناء الانتحال تحتاج تأكيدًا. فشل أيهما يعني أن العزل وهم.
"""
import base64
import json
import time
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from apps.accounts.models import Account
from apps.accounts.models_admin import (
    ImpersonationSession, PlatformAuditLog, PlatformRole, PlatformSession,
    PlatformUser, ROLE_CAPABILITIES,
)
from apps.accounts.services.platform import auth
from apps.accounts.services.platform import impersonation as imp
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope

PASSWORD = "Str0ng!Pass2026"


@pytest.fixture
def env(db):
    r = provision_account(slug="plt-test", display_name_ar="عميل تجريبي",
                          company_name_ar="شركة", is_sandbox=True)
    owner = auth.create_platform_user(
        username="p_owner", email="owner@platform.sa", full_name="مالك",
        password=PASSWORD, role=PlatformRole.OWNER)
    support = auth.create_platform_user(
        username="p_support", email="sup@platform.sa", full_name="دعم",
        password=PASSWORD, role=PlatformRole.SUPPORT)
    viewer = auth.create_platform_user(
        username="p_viewer", email="view@platform.sa", full_name="مطّلع",
        password=PASSWORD, role=PlatformRole.VIEWER)
    return {"account_id": r.account_id,
            "account": Account.objects.get(id=r.account_id),
            "owner": owner, "support": support, "viewer": viewer}


def _login(username):
    c = Client()
    r = c.post("/platform/auth/login/",
               data=json.dumps({"username": username, "password": PASSWORD}),
               content_type="application/json")
    assert r.status_code == 200, r.content
    return c


def _post(c, url, data=None, **headers):
    return c.post(url, data=json.dumps(data or {}),
                  content_type="application/json", **headers)


# ══════════ المصادقة ══════════

@pytest.mark.django_db(transaction=True)
def test_login_and_session(env):
    c = _login("p_owner")
    r = c.get("/platform/auth/me/")
    assert r.status_code == 200
    assert r.json()["role"] == PlatformRole.OWNER


@pytest.mark.django_db(transaction=True)
def test_wrong_password_rejected(env):
    c = Client()
    r = _post(c, "/platform/auth/login/",
              {"username": "p_owner", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_lockout_after_failed_attempts(env):
    """خمس محاولات فاشلة تقفل الحساب."""
    c = Client()
    for _ in range(auth.MAX_FAILED):
        _post(c, "/platform/auth/login/",
              {"username": "p_owner", "password": "wrong"})
    env["owner"].refresh_from_db()
    assert env["owner"].is_locked

    r = _post(c, "/platform/auth/login/",
              {"username": "p_owner", "password": PASSWORD})
    assert r.status_code == 401
    assert "مقفل" in r.json()["detail"]


@pytest.mark.django_db(transaction=True)
def test_totp_required_when_enabled(env):
    """ق-51: التحقق الثنائي إلزامي لمن فعّله."""
    key = base64.b32decode(env["owner"].totp_secret, casefold=True)
    auth.enable_totp(env["owner"], auth._hotp(key, int(time.time()) // 30))

    c = Client()
    r = _post(c, "/platform/auth/login/",
              {"username": "p_owner", "password": PASSWORD})
    assert r.status_code == 401
    assert r.json()["code"] == "totp_required"

    r = _post(c, "/platform/auth/login/", {
        "username": "p_owner", "password": PASSWORD,
        "totp_code": auth._hotp(key, int(time.time()) // 30)})
    assert r.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_wrong_totp_rejected(env):
    key = base64.b32decode(env["owner"].totp_secret, casefold=True)
    auth.enable_totp(env["owner"], auth._hotp(key, int(time.time()) // 30))
    c = Client()
    r = _post(c, "/platform/auth/login/", {
        "username": "p_owner", "password": PASSWORD, "totp_code": "000000"})
    assert r.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_ip_allowlist(env):
    env["owner"].allowed_ips = "10.0.0.1"
    env["owner"].save()
    with pytest.raises(auth.AuthError):
        auth.authenticate(username="p_owner", password=PASSWORD,
                          ip="203.0.113.9")
    user, _ = auth.authenticate(username="p_owner", password=PASSWORD,
                                ip="10.0.0.1")
    assert user.username == "p_owner"


@pytest.mark.django_db(transaction=True)
def test_logout_invalidates_session(env):
    c = _login("p_owner")
    assert c.get("/platform/auth/me/").status_code == 200
    c.post("/platform/auth/logout/")
    assert c.get("/platform/auth/me/").status_code == 401


# ══════════ العزل بين البنيتين (ق-51) ══════════

@pytest.mark.django_db(transaction=True)
def test_client_session_cannot_reach_platform(env):
    """
    ⚠️ أخطر حارس: جلسة عميل لا تصل مسارات المنصة.

    فشله يعني أن العزل الذي بنيناه وهم — أي عميل يفتح لوحتك.
    """
    with account_scope(env["account_id"]):
        u = User.objects.create_user(username="client1", password="x")
    c = Client()
    c.force_login(u)

    for path in ("/platform/accounts/", "/platform/dashboard/",
                 "/platform/settings/", "/platform/auth/me/"):
        assert c.get(path).status_code == 401, f"تسرّب: {path}"


@pytest.mark.django_db(transaction=True)
def test_platform_user_is_not_django_user(env):
    """مستخدم المنصة ليس مستخدم Django — بنيتان منفصلتان."""
    assert not User.objects.filter(username="p_owner").exists()
    assert PlatformUser.objects.filter(username="p_owner").exists()


@pytest.mark.django_db(transaction=True)
def test_no_session_rejected(env):
    c = Client()
    assert c.get("/platform/accounts/").status_code == 401


# ══════════ الأدوار الثلاثة (ق-51) ══════════

@pytest.mark.django_db(transaction=True)
def test_role_capabilities_distinct():
    """viewer ⊂ support ⊂ owner — التدرّج محفوظ."""
    v = ROLE_CAPABILITIES[PlatformRole.VIEWER]
    s = ROLE_CAPABILITIES[PlatformRole.SUPPORT]
    o = ROLE_CAPABILITIES[PlatformRole.OWNER]
    assert v < s < o


@pytest.mark.django_db(transaction=True)
def test_viewer_reads_only(env):
    c = _login("p_viewer")
    assert c.get("/platform/accounts/").status_code == 200
    assert c.get("/platform/dashboard/").status_code == 200
    assert c.get("/platform/settings/").status_code == 403
    assert c.get("/platform/discounts/").status_code == 403


@pytest.mark.django_db(transaction=True)
def test_support_activates_but_not_settings(env):
    c = _login("p_support")
    assert c.get("/platform/accounts/").status_code == 200
    assert c.get("/platform/settings/").status_code == 403
    r = _post(c, f"/platform/accounts/{env['account'].id}/extend/",
              {"until": str(date.today() + timedelta(days=10)),
               "confirm": True})
    assert r.status_code in (200, 404)      # ليس 403


@pytest.mark.django_db(transaction=True)
def test_owner_full_access(env):
    c = _login("p_owner")
    for path in ("/platform/accounts/", "/platform/dashboard/",
                 "/platform/settings/", "/platform/discounts/"):
        assert c.get(path).status_code == 200, path


# ══════════ التأكيد قبل الكتابة (ق-46) ══════════

@pytest.mark.django_db(transaction=True)
def test_write_requires_confirmation(env):
    """
    ق-46: تحذير صريح قبل التعديل في حساب عميل.

    يمنع التعديل بالخطأ عند نسيان السياق.
    """
    c = _login("p_owner")
    r = _post(c, f"/platform/accounts/{env['account'].id}/extend/",
              {"until": str(date.today() + timedelta(days=10))})
    assert r.status_code == 428
    assert r.json()["code"] == "confirmation_required"
    assert env["account"].display_name_ar in r.json()["detail"]


@pytest.mark.django_db(transaction=True)
def test_write_proceeds_with_confirmation(env):
    from apps.accounts.services.billing_v2 import start_trial
    with account_scope(env["account_id"]):
        start_trial(env["account"])

    c = _login("p_owner")
    until = date.today() + timedelta(days=30)
    r = _post(c, f"/platform/accounts/{env['account'].id}/extend/",
              {"until": str(until), "confirm": True})
    assert r.status_code == 200
    assert r.json()["grace_until"] == str(until)


# ══════════ الانتحال (ق-51) ══════════

@pytest.mark.django_db(transaction=True)
def test_impersonation_starts_with_banner(env):
    c = _login("p_support")
    r = _post(c, f"/platform/accounts/{env['account'].id}/impersonate/",
              {"reason": "بلاغ عن خطأ", "as_role": "hr_manager"})
    assert r.status_code == 200
    b = r.json()
    assert b["active"] is True
    assert env["account"].display_name_ar in b["message"]
    assert b["minutes_left"] <= 60


@pytest.mark.django_db(transaction=True)
def test_viewer_cannot_impersonate(env):
    """المطّلع يقرأ الملخص ولا يدخل حسابات العملاء."""
    c = _login("p_viewer")
    r = _post(c, f"/platform/accounts/{env['account'].id}/impersonate/", {})
    assert r.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_impersonation_expires(env):
    """الجلسة مؤقتة — لا تُنسى مفتوحة."""
    session = imp.start_impersonation(
        platform_user=env["support"], account_id=env["account"].id)
    assert imp.resolve_impersonation(session.token) is not None

    session.expires_at = timezone.now() - timedelta(minutes=1)
    session.save()
    assert imp.resolve_impersonation(session.token) is None


@pytest.mark.django_db(transaction=True)
def test_only_one_active_impersonation(env):
    """جلسة جديدة تنهي السابقة — لا جلستان معًا."""
    s1 = imp.start_impersonation(
        platform_user=env["support"], account_id=env["account"].id)
    s2 = imp.start_impersonation(
        platform_user=env["support"], account_id=env["account"].id)
    s1.refresh_from_db()
    assert s1.ended_at is not None
    assert s2.is_active


@pytest.mark.django_db(transaction=True)
def test_impersonation_write_needs_header(env):
    """
    ⚠️ حارس حرج: الكتابة أثناء الانتحال تحتاج ترويسة تأكيد.

    فشله يعني أن السوبر أدمن قد يعدّل بيانات عميل بالخطأ.
    """
    session = imp.start_impersonation(
        platform_user=env["support"], account_id=env["account"].id)

    with account_scope(env["account_id"]):
        u = User.objects.create_user(username="c_user", password="x")
    c = Client()
    c.force_login(u)
    c.cookies[imp.COOKIE_NAME] = session.token

    r = c.post("/api/employees/", data=json.dumps({"employee_no": "X"}),
               content_type="application/json")
    assert r.status_code == 428
    assert r.json()["code"] == "impersonation_confirm_required"


@pytest.mark.django_db(transaction=True)
def test_impersonation_read_is_open(env):
    """القراءة مفتوحة — الدعم يحتاجها بلا احتكاك."""
    session = imp.start_impersonation(
        platform_user=env["support"], account_id=env["account"].id)
    with account_scope(env["account_id"]):
        u = User.objects.create_user(username="c_user2", password="x")
    c = Client()
    c.force_login(u)
    c.cookies[imp.COOKIE_NAME] = session.token

    r = c.get("/api/employees/")
    assert r.status_code != 428


@pytest.mark.django_db(transaction=True)
def test_impersonation_write_is_recorded(env):
    """كل كتابة تُسجَّل باسم السوبر أدمن لا باسم العميل."""
    session = imp.start_impersonation(
        platform_user=env["support"], account_id=env["account"].id)
    imp.record_write(session, action="test.write", detail={"x": 1})

    session.refresh_from_db()
    assert session.writes_count == 1
    log = PlatformAuditLog.objects.filter(
        action="impersonation.test.write").first()
    assert log is not None
    assert log.user_name == env["support"].full_name
    assert log.target_account_id == env["account"].id


@pytest.mark.django_db(transaction=True)
def test_impersonation_end_logs_duration(env):
    session = imp.start_impersonation(
        platform_user=env["support"], account_id=env["account"].id)
    imp.end_impersonation(session.token)

    log = PlatformAuditLog.objects.filter(
        action="impersonation.end").first()
    assert log is not None
    assert "duration_minutes" in log.detail


# ══════════ سجل المنصة ══════════

@pytest.mark.django_db(transaction=True)
def test_login_logged(env):
    _login("p_owner")
    assert PlatformAuditLog.objects.filter(
        action="login", success=True, user=env["owner"]).exists()


@pytest.mark.django_db(transaction=True)
def test_failed_login_logged(env):
    c = Client()
    _post(c, "/platform/auth/login/",
          {"username": "p_owner", "password": "wrong"})
    assert PlatformAuditLog.objects.filter(
        action="login", success=False).exists()


@pytest.mark.django_db(transaction=True)
def test_settings_change_logged(env):
    c = _login("p_owner")
    c.put("/platform/settings/", data=json.dumps({"vat_rate": "5"}),
          content_type="application/json")
    log = PlatformAuditLog.objects.filter(action="platform.settings").first()
    assert log is not None
    assert "vat_rate" in log.detail


# ══════════ الملخص بلا بيانات (ق-46) ══════════

@pytest.mark.django_db(transaction=True)
def test_accounts_list_has_no_employee_data(env):
    """
    ق-46: الشاشة الأولى ملخص لا بيانات — بلا رواتب ولا أسماء موظفين.
    """
    c = _login("p_owner")
    d = c.get("/platform/accounts/").json()
    body = json.dumps(d, ensure_ascii=False)
    for leaked in ("salary", "net_pay", "iban", "id_number"):
        assert leaked not in body, f"تسريب: {leaked}"
