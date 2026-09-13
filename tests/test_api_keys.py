"""
حرّاس واجهة العملاء البرمجية (ق-151).

⚠️ **والمفتاح يُعرض مرّةً ويُخزَّن مجزّأً** — فمن يقرأ القاعدة لا
ينتحل عميلًا.

⚠️⚠️ **والمفتاح لشركةٍ واحدة**: فحسابٌ بثلاث شركات ومفتاحٌ يقرأ
الثلاث **تسريبٌ لا تكامل** (قرار جواد).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.models import ApiCallLog, ApiKey, ApiScope
from apps.core.services import api_keys as svc
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="api-t", display_name_ar="حساب",
                          company_name_ar="شركة أولى", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="وليد", family_name_ar="الرشيد",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011199988", mobile="0501119998")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="A-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("8000"))])

        # ⚠️ شركةٌ ثانية في الحساب نفسه — لاختبار العزل
        comp2 = Company.objects.create(
            account=acc, legal_name_ar="شركة ثانية",
            cr_number="1010999888")

        key, raw = svc.create_key(
            company=comp, name="تكامل",
            scopes=[ApiScope.EMPLOYEES, ApiScope.ORG])

        yield {"account_id": r.account_id, "comp": comp,
               "comp2": comp2, "emp": emp, "key": key, "raw": raw}


def test_key_is_not_stored_in_plain(env):
    """
    ⚠️⚠️ الأهمّ: **المفتاح لا يُحفظ نصًّا**.

    فمن يقرأ القاعدة لا ينتحل عميلًا.
    """
    with account_scope(env["account_id"]):
        k = ApiKey.objects.get(id=env["key"].id)
        assert env["raw"] not in k.key_hash
        assert k.key_hash != env["raw"]
        assert len(k.key_hash) >= 64, "ليست تجزئة"
        assert k.prefix == env["raw"][:8]


def test_authenticate_accepts_the_real_key(env):
    """والمفتاح الصحيح يُقبل."""
    k, err = svc.authenticate(env["raw"])
    assert k is not None, err
    assert k.id == env["key"].id


def test_wrong_key_is_refused(env):
    """والخاطئ يُرفض — ولو صحّت بادئته."""
    fake = env["raw"][:8] + "X" * 30
    k, err = svc.authenticate(fake)
    assert k is None
    assert err


def test_revoked_key_stops_working(env):
    """والموقوف لا يعمل."""
    with account_scope(env["account_id"]):
        svc.revoke(key=env["key"], reason="تسريب")
        k, err = svc.authenticate(env["raw"])
        assert k is None
        assert "موقوف" in err


def test_expired_key_stops_working(env):
    """
    ⚠️ **والمنتهي لا يعمل ولو كان مفعَّلًا** — فتاريخُ انتهاءٍ لا
    يُفحص زينةٌ لا ضابط.
    """
    with account_scope(env["account_id"]):
        env["key"].expires_on = date.today() - timedelta(days=1)
        env["key"].save(update_fields=["expires_on"])
        assert env["key"].is_usable is False
        k, err = svc.authenticate(env["raw"])
        assert k is None
        assert "منتهٍ" in err


def test_scope_is_enforced(env):
    """
    ⚠️ **والنطاق يُحترم**: فمفتاح تكاملٍ محاسبيّ لا يقرأ ملفّات
    الموظفين.
    """
    with account_scope(env["account_id"]):
        assert env["key"].allows(ApiScope.EMPLOYEES) is True
        assert env["key"].allows(ApiScope.PAYROLL) is False


def test_key_without_scopes_refused(env):
    """ومفتاحٌ بلا نطاق لا يُنشأ — فلا يقرأ شيئًا."""
    with account_scope(env["account_id"]):
        with pytest.raises(svc.ApiKeyError):
            svc.create_key(company=env["comp"], name="فارغ", scopes=[])


def test_key_is_bound_to_one_company(env):
    """
    ⚠️⚠️ **والمفتاح لشركةٍ واحدة**: فحسابٌ بشركتين ومفتاحٌ يقرأ
    الثانية تسريبٌ لا تكامل (قرار جواد).
    """
    with account_scope(env["account_id"]):
        assert env["key"].company_id == env["comp"].id
        assert env["key"].company_id != env["comp2"].id


def test_api_returns_only_key_company(env, client):
    """والنداء لا يُرجع إلا شركة المفتاح."""
    res = client.get("/api/v1/employees/",
                     HTTP_X_API_KEY=env["raw"])
    assert res.status_code == 200, res.content[:200]
    rows = res.json()["data"]
    assert all(r["employee_no"] == "A-1" for r in rows), rows


def test_no_key_is_401(env, client):
    """وبلا مفتاح: ٤٠١ لا انهيار."""
    assert client.get("/api/v1/employees/").status_code == 401


def test_out_of_scope_is_403(env, client):
    """وخارج النطاق: ٤٠٣."""
    res = client.get("/api/v1/payroll/runs/",
                     HTTP_X_API_KEY=env["raw"])
    assert res.status_code == 403


def test_sensitive_fields_are_not_exposed(env, client):
    """
    ⚠️⚠️ **ولا هويةَ ولا آيبان ولا راتب** في مخرجات الموظفين.

    فالتكامل لا يحتاجها، **وتسريبُها يضرّ صاحبها**.
    """
    res = client.get("/api/v1/employees/", HTTP_X_API_KEY=env["raw"])
    body = res.content.decode("utf-8")
    for bad in ("iban", "id_number", "salary", "basic_salary",
                "1011199988"):
        assert bad not in body.lower(), f"سُرّب: {bad}"


def test_calls_are_logged(env, client):
    """والنداءات تُسجَّل — للحدّ والمراجعة."""
    with account_scope(env["account_id"]):
        before = ApiCallLog.objects.filter(api_key=env["key"]).count()

    client.get("/api/v1/whoami/", HTTP_X_API_KEY=env["raw"])

    with account_scope(env["account_id"]):
        after = ApiCallLog.objects.filter(api_key=env["key"]).count()
        assert after == before + 1


def test_rate_limit_blocks_excess(env, client):
    """
    ⚠️ **والسقف يُطبَّق** — فمفتاحٌ بلا حدّ يُسقط الخادم.
    """
    with account_scope(env["account_id"]):
        env["key"].rate_limit_per_hour = 2
        env["key"].save(update_fields=["rate_limit_per_hour"])

    for _ in range(2):
        assert client.get("/api/v1/whoami/",
                          HTTP_X_API_KEY=env["raw"]).status_code == 200

    res = client.get("/api/v1/whoami/", HTTP_X_API_KEY=env["raw"])
    assert res.status_code == 429, res.status_code
    assert res.json()["code"] == "rate_limit"


def test_only_approved_runs_are_readable(env, client):
    """
    ⚠️ **والمسير غير المعتمد لا يُقرأ**: فأرقامٌ غير نهائية تُبنى
    عليها قيودٌ خاطئة.
    """
    from apps.payroll.models import PayrollRunType
    from apps.payroll.services import engine

    with account_scope(env["account_id"]):
        env["key"].scopes = [ApiScope.PAYROLL]
        env["key"].save(update_fields=["scopes"])

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)      # محتسبٌ لا معتمد

    res = client.get("/api/v1/payroll/runs/", HTTP_X_API_KEY=env["raw"])
    assert res.status_code == 200
    assert res.json()["data"] == [], "قُرئ مسيرٌ غير معتمد"
