"""
حارس: إنشاء الموظف عملية واحدة لا تتجزأ.

الخلل الذي يمنعه: create_person تنجح وتُحفظ بمعاملتها الخاصة،
ثم create_employment تفشل — فيبقى شخص بلا ارتباط وظيفي يحجز
هويته وجواله وبريده، ويمنع إعادة المحاولة بنفس البيانات.

حدث فعلًا عند أول تجربة إدخال حقيقية.
"""
import json
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.models import Employment, Person
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="atomic-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        u = User.objects.create_user(username="hrm", password="x")
        role = Role.objects.get(account=acc, code="hr_manager")
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, role=role, company=comp,
            scope=Scope.COMPANY.value)

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "user": u}


def _client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.mark.django_db(transaction=True)
def test_failed_hire_leaves_no_orphan_person(env):
    """
    ⚠️ الحارس الحرج: فشل إنشاء الارتباط لا يترك شخصًا محفوظًا.

    فشله يعني أن العميل لا يستطيع إعادة إدخال موظف بعد أول خطأ.
    """
    with account_scope(env["account_id"]):
        # موظف قائم يحجز الرقم الوظيفي
        p, _ = create_person(
            account=env["acc"], first_name_ar="قائم",
            family_name_ar="موظف", gender="male", nationality_code="SA",
            id_type="national_id", id_number="1011223344",
            mobile="0501112233", force=True)
        comps = {c.code: c for c in PayComponent.objects.filter(
            company=env["comp"])}
        create_employment(
            person=p, company=env["comp"], employee_no="E100",
            join_date=date(2024, 1, 1),
            salary_lines=[(comps["BASIC"], 5000)])

        before = Person.objects.count()

    c = _client(env["user"])
    # نفس الرقم الوظيفي — يفشل بعد إنشاء الشخص
    r = c.post("/api/employees/", data=json.dumps({
        "first_name_ar": "جديد", "family_name_ar": "شخص",
        "gender": "male", "nationality_code": "SA",
        "id_type": "national_id", "id_number": "1099887755",
        "mobile": "0509998811",
        "employee_no": "E100",          # مستخدم
        "join_date": "2026-01-01",
        "salary_lines": [{"code": "BASIC", "amount": "5000"}],
    }), content_type="application/json")

    assert r.status_code == 400

    with account_scope(env["account_id"]):
        assert Person.objects.count() == before, (
            "بقي شخص يتيم بعد فشل الإنشاء — المعاملة لا تلفّ "
            "العمليتين معًا")
        assert not Person.objects.filter(
            id_number="1099887755").exists()


@pytest.mark.django_db(transaction=True)
def test_successful_hire_creates_both(env):
    """النجاح ينشئ الشخص والارتباط معًا."""
    c = _client(env["user"])
    r = c.post("/api/employees/", data=json.dumps({
        "first_name_ar": "سالم", "family_name_ar": "الحربي",
        "gender": "male", "nationality_code": "SA",
        "id_type": "national_id", "id_number": "1077665544",
        "mobile": "0507776655",
        "employee_no": "E200", "join_date": "2026-02-01",
        "salary_lines": [{"code": "BASIC", "amount": "7000"}],
    }), content_type="application/json")

    assert r.status_code == 201, r.content

    with account_scope(env["account_id"]):
        person = Person.objects.filter(id_number="1077665544").first()
        assert person is not None
        assert Employment.objects.filter(person=person).exists()


@pytest.mark.django_db(transaction=True)
def test_duplicate_returns_detailed_message(env):
    """
    رسالة التكرار تذكر الحقل المتكرر — لا كلمة «مكرر» وحدها.

    العميل يحتاج معرفة ما يصححه.
    """
    with account_scope(env["account_id"]):
        create_person(
            account=env["acc"], first_name_ar="أول",
            family_name_ar="شخص", gender="male", nationality_code="SA",
            id_type="national_id", id_number="1033445566",
            mobile="0503334455", force=True)

    c = _client(env["user"])
    r = c.post("/api/employees/", data=json.dumps({
        "first_name_ar": "ثانٍ", "family_name_ar": "شخص",
        "gender": "male", "nationality_code": "SA",
        "id_type": "national_id", "id_number": "1033445566",
        "mobile": "0509990000",
        "employee_no": "E300", "join_date": "2026-01-01",
        "salary_lines": [{"code": "BASIC", "amount": "5000"}],
    }), content_type="application/json")

    assert r.status_code == 409
    data = r.json()
    assert data["code"] == "duplicate_person"
    assert len(data["detail"]) > 12, "الرسالة مقتضبة بلا تفصيل"
    assert data.get("blocking")
