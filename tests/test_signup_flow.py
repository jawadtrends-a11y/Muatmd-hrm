"""
حرّاس التسجيل الذاتيّ واستعادة كلمة المرور (ق-113).

⚠️ أخطرها: **لا يُفشى وجود الحساب** — وإلا صار المسار أداةً لكشف
من له حساب عندنا.
"""
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.accounts.models_signup import (
    PasswordReset, SignupRequest, SignupStatus)
from apps.accounts.services import signup as svc


@pytest.mark.django_db
def test_signup_creates_no_account_before_verification():
    """
    البريد يُؤكَّد أوّلًا — ولا يُنشأ حساب قبله.

    فالبريد غير المؤكَّد يملأ المنصّة بحسابات وهمية، ويحرم صاحبه
    من استعادة كلمة مروره حين ينساها.
    """
    from apps.accounts.models import Account

    before = Account.objects.count()
    req, raw = svc.create_signup(
        company_name="شركة تجربة", full_name="جواد", email="a@example.com",
        mobile="0500000000", password="Str0ngPass!")
    assert req.status == SignupStatus.PENDING
    assert Account.objects.count() == before
    assert not User.objects.filter(email="a@example.com").exists()
    assert raw and req.token_hash != raw, "الرمز خام في القاعدة"


@pytest.mark.django_db
def test_verification_creates_account_and_owner():
    """التأكيد يُنشئ الحساب، ومنشئه **مالك الحساب**."""
    from apps.accounts.models_access import AccountMembership

    _, raw = svc.create_signup(
        company_name="شركة", full_name="جواد", email="b@example.com",
        mobile="", password="Str0ngPass!")
    out = svc.verify_signup(raw)

    u = User.objects.get(id=out["user_id"])
    m = AccountMembership.objects.get(user=u)
    assert m.is_account_owner
    assert m.account_id == out["account_id"]


@pytest.mark.django_db
def test_verification_is_single_use():
    """الرابط يُستهلك — فلا يُنشئ حسابين."""
    _, raw = svc.create_signup(
        company_name="شركة", full_name="ج", email="c@example.com",
        mobile="", password="Str0ngPass!")
    svc.verify_signup(raw)
    with pytest.raises(svc.SignupError):
        svc.verify_signup(raw)


@pytest.mark.django_db
def test_expired_signup_is_refused():
    """الرابط المنتهي لا يُنشئ حسابًا."""
    req, raw = svc.create_signup(
        company_name="شركة", full_name="ج", email="d@example.com",
        mobile="", password="Str0ngPass!")
    SignupRequest.objects.filter(id=req.id).update(
        expires_at=timezone.now() - timedelta(hours=1))
    with pytest.raises(svc.SignupError):
        svc.verify_signup(raw)


@pytest.mark.django_db
def test_short_password_is_refused():
    with pytest.raises(svc.SignupError):
        svc.create_signup(company_name="ش", full_name="ج",
                          email="e@example.com", mobile="", password="123")


@pytest.mark.django_db
def test_reset_does_not_reveal_account_existence():
    """
    ⚠️ الأهمّ: طلب الاستعادة لبريد لا وجود له **لا يرفع خطأً**.

    فلو ميّز الردُّ بين موجودٍ ومفقود لصار المسار أداةً لكشف
    عملائنا واحدًا واحدًا.
    """
    user, raw = svc.request_reset("la-yujad@example.com")
    assert user is None and raw is None


@pytest.mark.django_db
def test_reset_changes_password_once():
    """الرمز يُستهلك — فلا يُستعمل مرّتين."""
    u = User.objects.create_user(username="r@example.com",
                                 email="r@example.com", password="Old@12345")
    user, raw = svc.request_reset("r@example.com")
    assert user is not None

    svc.apply_reset(raw, "New@123456")
    u.refresh_from_db()
    assert u.check_password("New@123456")

    with pytest.raises(svc.SignupError):
        svc.apply_reset(raw, "Another@123")


@pytest.mark.django_db
def test_expired_reset_is_refused():
    User.objects.create_user(username="x@example.com",
                             email="x@example.com", password="Old@12345")
    _, raw = svc.request_reset("x@example.com")
    PasswordReset.objects.all().update(
        expires_at=timezone.now() - timedelta(minutes=1))
    with pytest.raises(svc.SignupError):
        svc.apply_reset(raw, "New@123456")
