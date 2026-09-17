"""
حارس تفرّد جوال التسجيل (ق-213).

⚠️⚠️ **وجوالٌ واحد لحسابٍ واحد** (قرار جواد): فرقمٌ على حسابين
**يجعل الدخول به ملتبسًا** — فيُردّ صاحبه برسالة «يخصّ أكثر من
حساب» **وهو لم يُخطئ**.
"""
import pytest

from apps.accounts.services import signup as svc


def _new(mobile, email):
    return svc.create_signup(
        company_name="منشأة", full_name="مسؤول", email=email,
        mobile=mobile, password="Test@2026", ip="1.1.1.1")


@pytest.mark.django_db(transaction=True)
def test_duplicate_mobile_is_refused():
    """⚠️⚠️ الأهمّ: **ولا يُسجَّل جوالٌ مرّتين**."""
    _new("0512340001", "a1@x.sa")

    with pytest.raises(svc.SignupError) as e:
        _new("0512340001", "a2@x.sa")
    assert "مسجَّل" in str(e.value), str(e.value)


@pytest.mark.django_db(transaction=True)
def test_all_three_formats_are_one_number():
    """
    ⚠️ **والصيغ الثلاث رقمٌ واحد** (ق-94): فمن سجّل بـ`05` **لا
    يُسجّل ثانيةً بـ`+966`**.
    """
    _new("0512340002", "b1@x.sa")
    for v in ("966512340002", "+966512340002"):
        with pytest.raises(svc.SignupError):
            _new(v, f"b{v[-4:]}@x.sa")


@pytest.mark.django_db(transaction=True)
def test_new_mobile_is_accepted():
    """**ورقمٌ جديد يُقبل** — فالمنع للمكرّر وحده."""
    req, _raw = _new("0512340003", "c1@x.sa")
    assert req is not None


@pytest.mark.django_db(transaction=True)
def test_message_names_the_problem():
    """
    ⚠️ **والرسالة تُسمّي المشكلة** (مبدأ جواد): **فمن يُردّ يحتاج
    معرفة السبب والحلّ**.
    """
    _new("0512340004", "d1@x.sa")
    with pytest.raises(svc.SignupError) as e:
        _new("0512340004", "d2@x.sa")
    msg = str(e.value)
    assert "الجوال" in msg
    assert "الدخول" in msg or "رقمًا آخر" in msg
