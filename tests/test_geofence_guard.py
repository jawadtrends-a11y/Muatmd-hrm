"""
حرّاس سلامة موقع البصمة (ق-233).

⚠️⚠️ **الموقع المزيَّف كان يُقبل** — وتطبيقات التزييف مجّانيّة. **والدقّة كانت
تُستقبل ولا تُستعمل** — فموقعٌ بدقّة ±٨٠٠م يقع مركزه داخل النطاق كان يُقبل.
والموقع يُحاكى هنا: فالحارس يختبر المنطق لا تهيئة المواقع.
"""
from types import SimpleNamespace

import pytest

from apps.attendance.services import geofence as g

RIYADH = (24.7136, 46.6753)
SITE = SimpleNamespace(code="HQ", name_ar="المقرّ", name_en="HQ",
                       latitude=RIYADH[0], longitude=RIYADH[1],
                       effective_radius=100, enforce_geofence=True,
                       has_coordinates=True)
EMP = SimpleNamespace(id=1, company_id=1, account_id=1)


@pytest.fixture(autouse=True)
def one_site(monkeypatch):
    monkeypatch.setattr(g, "sites_for", lambda e: [SITE])
    monkeypatch.setattr(g, "_mobile_punch_allowed", lambda e: True)


def _verify(lat=RIYADH[0], lng=RIYADH[1], acc=None):
    return g.verify_location(employment=EMP, latitude=lat, longitude=lng,
                             accuracy_m=acc)


def test_mocked_location_always_rejected():
    """⚠️⚠️ الأهمّ: **المزيَّف يُرفض دائمًا** — ولو كانت إحداثيّاته في قلب الموقع."""
    with pytest.raises(g.GeofenceError) as e:
        g.record_punch(employment=EMP, latitude=RIYADH[0], longitude=RIYADH[1],
                       accuracy_m=5, method="mobile_gps", mocked=True)
    assert e.value.code == "mock_location"
    assert "مزيَّف" in str(e.value) and "spoofed" in e.value.en


def test_low_accuracy_rejected_even_inside():
    """⚠️⚠️ **±٥٠٠م في موقعٍ نصف قطره ١٠٠م لا يُثبت شيئًا** — ولو وقع المركز داخله."""
    with pytest.raises(g.GeofenceError) as e:
        _verify(acc=500)
    assert e.value.code == "low_accuracy" and "±500" in str(e.value)


def test_good_accuracy_accepted():
    site, d = _verify(acc=20)
    assert site is SITE and d == 0


def test_accuracy_as_text_is_parsed():
    """الجوال قد يرسلها نصًّا — «35.5» تُفهم رقمًا."""
    assert _verify(acc="35.5")[0] is SITE
    with pytest.raises(g.GeofenceError):
        _verify(acc="250")


def test_missing_accuracy_does_not_block():
    """بلا دقّةٍ مُرسَلة لا يُمنع — فلا يُرفض ما لا يُعرف."""
    assert _verify(acc=None)[0] is SITE
    assert _verify(acc="غير رقم")[0] is SITE


def test_outside_has_english_and_code():
    """⚠️ والرفض بلغتين — فموظف الإنجليزية كان يقرؤه بالعربية."""
    with pytest.raises(g.GeofenceError) as e:
        _verify(lat=RIYADH[0] + 0.01)       # ~١١٠٠م شمالًا
    assert e.value.code == "outside_geofence"
    assert "outside" in e.value.en and "خارج" in str(e.value)


def test_device_punch_ignores_mocked_flag():
    """والعلامة للجوال وحده — الإدخال اليدويّ من الموارد لا يتأثّر بها."""
    import inspect
    src = inspect.getsource(g.record_punch)
    assert "method == PunchMethod.MOBILE_GPS and mocked" in src
