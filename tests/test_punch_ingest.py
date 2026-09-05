"""
حرّاس استقبال البصمات (ق-84).

ما تمنعه:
  • قبول بصمة بلا مصادقة أو بمفتاح خاطئ
  • احتساب البصمة مرتين عند إعادة الرفع بعد الانقطاع
  • تسجيلها بوقت وصولها بدل وقتها الأصلي
  • تسرّب البصمات بين الشركات
"""
import json
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (AccountMembership, Role,
                                         RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import AttendancePunch
from apps.attendance.models_sites import PunchDevice
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person


@pytest.fixture
def env(db):
    r = provision_account(slug="ing-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        p, _ = create_person(
            account=acc, first_name_ar="وليد", family_name_ar="العنزي",
            gender="male", nationality_code="SA",
            id_type="national_id", id_number="1011122233",
            mobile="0501112223")
        emp, _, _ = create_employment(person=p, company=comp,
                                      employee_no="E1",
                                      join_date=date(2023, 1, 1))

        u = User.objects.create_user(username="ing.hr", password="x")
        hp, _ = create_person(
            account=acc, first_name_ar="دانة", family_name_ar="المطيري",
            gender="female", nationality_code="SA",
            id_type="national_id", id_number="1022233344",
            mobile="0502223334")
        hp.user = u
        hp.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m,
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp, "hr_user": u}


def _make_device(env, code="ZK-T"):
    """ينشئ جهازًا ويرجع مفتاحه — كما تفعل شاشة الأجهزة."""
    c = Client()
    c.force_login(env["hr_user"])
    r = c.post("/api/attendance/devices/",
               data=json.dumps({"device_code": code, "name_ar": "جهاز"}),
               content_type="application/json")
    assert r.status_code == 201, r.content.decode()[:200]
    return r.json()["api_key"]


def _send(code, key, punches):
    return Client().post(
        "/api/attendance/ingest/",
        data=json.dumps({"punches": punches}),
        content_type="application/json",
        HTTP_X_DEVICE_CODE=code, HTTP_X_DEVICE_KEY=key)


# ══════════ المصادقة ══════════

@pytest.mark.django_db(transaction=True)
def test_no_key_no_punches(env):
    """
    ⚠️ بلا مفتاح لا بصمة — فمن يعرف الرابط يزوّر حضور شركة كاملة.
    """
    r = Client().post("/api/attendance/ingest/",
                      data=json.dumps({"punches": []}),
                      content_type="application/json")
    assert r.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_wrong_key_rejected(env):
    """⚠️ المفتاح الخاطئ يُردّ — والمقارنة بالتجزئة لا بالنص."""
    _make_device(env)
    r = _send("ZK-T", "not-the-key",
              [{"employee_no": "E1", "punched_at": "2026-09-05T08:00:00"}])
    assert r.status_code == 401

    with account_scope(env["account_id"]):
        assert AttendancePunch.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_inactive_device_rejected(env):
    """الجهاز المعطّل لا يرسل — فتعطيله إجراء أمني لا تجميلي."""
    key = _make_device(env)
    with account_scope(env["account_id"]):
        PunchDevice.objects.filter(device_code="ZK-T").update(
            is_active=False)

    r = _send("ZK-T", key,
              [{"employee_no": "E1", "punched_at": "2026-09-05T08:00:00"}])
    assert r.status_code == 401


# ══════════ التعافي من الانقطاع ══════════

@pytest.mark.django_db(transaction=True)
def test_punch_recorded_with_its_own_time(env):
    """
    ⚠️ البصمة بوقتها الأصلي لا بوقت وصولها.

    فالجهاز يخزّنها حين ينقطع ويرفعها متأخرة — وتسجيلها بوقت
    الوصول يجعل حضور الأمس غيابًا.
    """
    key = _make_device(env)
    r = _send("ZK-T", key,
              [{"employee_no": "E1", "punched_at": "2026-09-01T07:58:12"}])
    assert r.status_code == 200, r.content.decode()[:200]

    with account_scope(env["account_id"]):
        p = AttendancePunch.objects.get()

    # التخزين بـUTC والمقارنة بالتوقيت المحلي: البصمة سُجّلت
    # 07:58 بتوقيت الرياض، وتُحفظ 04:58 UTC — والمهمّ أنها بوقتها
    # الأصلي لا بوقت وصولها.
    from django.utils import timezone
    local = timezone.localtime(p.punched_at)
    assert local.date().isoformat() == "2026-09-01", local
    assert local.hour == 7 and local.minute == 58, local


@pytest.mark.django_db(transaction=True)
def test_reupload_does_not_duplicate(env):
    """
    ⚠️ الحارس الحرج: إعادة الرفع لا تكرّر البصمة.

    فالوسيط يعيد رفع ما لم يتأكد من وصوله بعد الانقطاع — وبلا هذا
    يُحتسب حضور مضاعف وإضافي وهمي.
    """
    key = _make_device(env)
    rows = [
        {"employee_no": "E1", "punched_at": "2026-09-05T08:01:33"},
        {"employee_no": "E1", "punched_at": "2026-09-05T16:04:10"},
    ]

    first = _send("ZK-T", key, rows).json()
    second = _send("ZK-T", key, rows).json()

    assert first["accepted"] == 2, first
    assert second["accepted"] == 0, second
    assert second["duplicated"] == 2, second

    with account_scope(env["account_id"]):
        assert AttendancePunch.objects.count() == 2, "تكرّرت البصمات"


@pytest.mark.django_db(transaction=True)
def test_unknown_employee_reported_not_dropped_silently(env):
    """
    الموظف المجهول يُذكر في الرد — فمن يضبط الجهاز يعرف أن رقمًا
    لا يقابل موظفًا، ولا يكتشفه بعد شهر.
    """
    key = _make_device(env)
    r = _send("ZK-T", key,
              [{"employee_no": "NOBODY",
                "punched_at": "2026-09-05T08:00:00"}]).json()

    assert r["accepted"] == 0
    assert "NOBODY" in r["unknown_employees"]


@pytest.mark.django_db(transaction=True)
def test_bad_timestamp_reported(env):
    """التاريخ غير الصالح يُذكر ولا يُسقط الدفعة كلها."""
    key = _make_device(env)
    r = _send("ZK-T", key, [
        {"employee_no": "E1", "punched_at": "not-a-date"},
        {"employee_no": "E1", "punched_at": "2026-09-05T09:00:00"},
    ]).json()

    assert r["accepted"] == 1, "أسقطت بصمة صالحة بسبب أخرى فاسدة"
    assert r["invalid"], "لم يُذكر التاريخ الفاسد"


@pytest.mark.django_db(transaction=True)
def test_last_seen_updated(env):
    """
    آخر اتصال يُحدَّث — به يُعرف الجهاز الصامت قبل أن يشتكي أحد.
    """
    key = _make_device(env)
    _send("ZK-T", key,
          [{"employee_no": "E1", "punched_at": "2026-09-05T08:00:00"}])

    with account_scope(env["account_id"]):
        d = PunchDevice.objects.get(device_code="ZK-T")
    assert d.last_seen_at is not None


@pytest.mark.django_db(transaction=True)
def test_batch_cap(env):
    """دفعة ضخمة تُردّ برسالة — لا تستهلك الخادم بلا حدّ."""
    key = _make_device(env)
    rows = [{"employee_no": "E1",
             "punched_at": f"2026-09-05T08:{i % 60:02d}:00"}
            for i in range(600)]
    r = _send("ZK-T", key, rows)
    assert r.status_code == 413
