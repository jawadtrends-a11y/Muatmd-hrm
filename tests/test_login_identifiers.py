"""
حرّاس الدخول بالمعرّفات (ق-94).

ما تمنعه:
  • كسر الدخول بالبريد أو الهوية أو الجوال
  • ردّ الجوال لاختلاف صيغته
  • حسّاسية المعرّف للحالة
  • فقدان حسّاسية كلمة المرور
  • دخول لحساب غير حسابك عند تعارض المعرّف
"""
import json
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person


@pytest.fixture
def emp(db):
    r = provision_account(slug="login-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        p, _ = create_person(
            account=acc, first_name_ar="وليد", family_name_ar="العنزي",
            gender="male", nationality_code="SA",
            id_type="national_id", id_number="1099988877",
            mobile="0509998887", email="walid@example.com")
        create_employment(person=p, company=comp, employee_no="L1",
                          join_date=date(2023, 1, 1))

        u = User.objects.create_user(username="walid.a",
                                     password="Secret@2026")
        p.user = u
        p.save(update_fields=["user"])

        yield {"person": p, "user": u}


def _login(ident, password="Secret@2026"):
    return Client().post(
        "/api/auth/login/",
        data=json.dumps({"identifier": ident, "password": password}),
        content_type="application/json")


@pytest.mark.django_db(transaction=True)
def test_login_by_email(emp):
    """الدخول بالبريد — وهو ما يحفظه الموظف."""
    assert _login("walid@example.com").status_code == 200


@pytest.mark.django_db(transaction=True)
def test_login_by_id_number(emp):
    """الدخول برقم الهوية — وهو في جيبه."""
    assert _login("1099988877").status_code == 200


@pytest.mark.django_db(transaction=True)
def test_mobile_accepted_in_all_forms(emp):
    """
    ⚠️ الجوال يُقبل بصيغه الثلاث.

    فمن يكتب 05 ومن يكتب +966 يقصدان رقمًا واحدًا — وردّ أحدهما
    لاختلاف كتابة عائق لا أمان.
    """
    for form in ("0509998887", "+966509998887", "966509998887"):
        assert _login(form).status_code == 200, f"رُدّت {form}"


@pytest.mark.django_db(transaction=True)
def test_identifier_is_case_insensitive(emp):
    """المعرّف غير حسّاس للحالة — فالبريد لا يُكتب بحالة ثابتة."""
    assert _login("WALID@EXAMPLE.COM").status_code == 200


@pytest.mark.django_db(transaction=True)
def test_password_stays_case_sensitive(emp):
    """
    ⚠️ كلمة المرور حسّاسة كما هي.

    فهي سرٌّ يُطابَق حرفيًّا — وتخفيف ذلك يوسّع مجال التخمين.
    """
    r = _login("walid@example.com", password="secret@2026")
    assert r.status_code == 401, "قُبلت كلمة مرور بحالة مختلفة"


@pytest.mark.django_db(transaction=True)
def test_unknown_identifier_rejected(emp):
    """معرّف مجهول يُردّ بلا إفصاح عن السبب."""
    assert _login("0500000000").status_code == 401


@pytest.mark.django_db(transaction=True)
def test_ambiguous_identifier_is_blocked(emp):
    """
    ⚠️ المعرّف الذي يخصّ أكثر من حساب يمنع الدخول.

    فالدخول لحساب غيرك خطأ لا يُغتفر — ورسالة واضحة خير من دخول
    خاطئ.
    """
    other = provision_account(slug="login-o", display_name_ar="آخر",
                              company_name_ar="شركة", is_sandbox=True)
    with account_scope(other.account_id):
        acc2 = Account.objects.get(id=other.account_id)
        comp2 = Company.objects.get(id=other.company_id)

        p2, _ = create_person(
            account=acc2, first_name_ar="سالم",
            family_name_ar="القحطاني", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1088877766",
            mobile="0509998887")      # نفس جوال وليد
        create_employment(person=p2, company=comp2, employee_no="O1",
                          join_date=date(2023, 1, 1))
        u2 = User.objects.create_user(username="salem.q",
                                      password="Secret@2026")
        p2.user = u2
        p2.save(update_fields=["user"])

    assert _login("0509998887").status_code == 409, "دخل بمعرّف مزدوج"
