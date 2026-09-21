"""
حرّاس إشعارات الجوال (ق-232).

⚠️⚠️ **قناة الجوال كانت معرَّفةً بلا منفّذ** — تُسجَّل «قيد الإرسال» للأبد.
وExpo يُحاكى هنا: فالحارس لا يتوقّف على الشبكة.
"""
from datetime import date

import pytest

from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_person
from apps.accounts.models import Account
from apps.notifications import tasks
from apps.notifications.models import (
    Channel, DeliveryStatus, Notification, NotificationDelivery,
    NotificationPreference)
from apps.notifications.models_push import PushDevice
from apps.notifications.services import push as svc

TOK = "ExponentPushToken[guard-{}]"


class _Resp:
    def __init__(self, status, data):
        self.status_code, self._d, self.text = status, data, str(data)

    def json(self):
        return self._d


@pytest.fixture
def env(db):
    r = provision_account(slug="push-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        p, _ = create_person(
            account=acc, first_name_ar="فهد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1091112223", mobile="0509112223")
        yield {"acc": r.account_id, "p": p}


def _dev(env, n=1):
    for i in range(n):
        PushDevice.objects.create(account_id=env["acc"], person_id=env["p"].id,
                                  token=TOK.format(i), platform="android")


def _notif(env):
    return Notification.objects.create(
        account_id=env["acc"], recipient_person_id=env["p"].id,
        event_key="test.push", title="عنوان", body="نص")


def test_token_format():
    assert svc.valid_token(TOK.format(1))
    for bad in ("", "abc", "ExponentPushToken" + "x" * 300):
        assert not svc.valid_token(bad)


def test_no_device_no_delivery_row(env):
    """⚠️ بلا جهازٍ لا سجلّ — فمستخدمو الويب لا يُضخّمون الجدول."""
    n = _notif(env)
    tasks._queue_push(env["acc"], n, env["p"].id, "test.push")
    assert not NotificationDelivery.objects.filter(notification=n).exists()


def test_preference_off_is_skipped(env):
    _dev(env)
    NotificationPreference.objects.create(
        account_id=env["acc"], person_id=env["p"].id, event_key="test.push",
        channel=Channel.PUSH, is_enabled=False)
    n = _notif(env)
    tasks._queue_push(env["acc"], n, env["p"].id, "test.push")
    d = NotificationDelivery.objects.get(notification=n)
    assert d.status == DeliveryStatus.SKIPPED


def test_sent_is_recorded(env, monkeypatch):
    _dev(env)
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _Resp(
        200, {"data": [{"status": "ok", "id": "tk-1"}]}))
    n = _notif(env)
    tasks._queue_push(env["acc"], n, env["p"].id, "test.push")
    did = NotificationDelivery.objects.get(notification=n).id
    tasks.push_notification.apply(kwargs={"account_id": env["acc"], "delivery_id": did})
    with account_scope(env["acc"]):
        d = NotificationDelivery.objects.get(id=did)
        assert d.status == DeliveryStatus.SENT and d.provider_ref == "tk-1"


def test_unregistered_device_is_deactivated(env, monkeypatch):
    """⚠️⚠️ رفض Expo نهائيّ — الجهاز يُعطَّل فلا يُعاد إليه."""
    _dev(env)
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _Resp(200, {"data": [
        {"status": "error", "details": {"error": "DeviceNotRegistered"}}]}))
    res = svc.send_to_person(person_id=env["p"].id, title="t", body="b")
    assert res.failed == 1
    d = PushDevice.objects.get(token=TOK.format(0))
    assert not d.is_active and "Expo" in d.deactivated_reason


def test_expo_outage_is_transient(env, monkeypatch):
    """⚠️ انقطاع Expo عابر — يُعاد لا يُسجَّل فشلًا نهائيًّا."""
    _dev(env)
    monkeypatch.setattr(svc.requests, "post", lambda *a, **k: _Resp(503, {}))
    with pytest.raises(svc.PushTransient):
        svc.send_to_person(person_id=env["p"].id, title="t", body="b")
    assert PushDevice.objects.get(token=TOK.format(0)).is_active


def test_batches_of_hundred(env, monkeypatch):
    """يوم المسير يُشعر الجميع — ودفعات Expo لا تتجاوز مئة."""
    _dev(env, 150)
    sizes = []

    def fake(url, json, **k):
        sizes.append(len(json))
        return _Resp(200, {"data": [{"status": "ok", "id": "x"}] * len(json)})
    monkeypatch.setattr(svc.requests, "post", fake)
    res = svc.send_to_person(person_id=env["p"].id, title="t", body="b")
    assert sizes == [100, 50] and res.sent == 150


def test_every_in_app_notification_pushes():
    """⚠️⚠️ قرار جواد: كل إشعارٍ داخل النظام يُدفع — فالربط في الموزّع نفسه."""
    import inspect
    src = inspect.getsource(tasks.dispatch_notification.run)
    assert "_queue_push(" in src and "Channel.PUSH not in spec.channels" in src
