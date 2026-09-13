"""
حرّاس فجوتَي الهيكل (ق-156).

**بلاغ جواد:** «ليش ما أقدر أضيف مدير للإدارات؟»

⚠️⚠️ **فالحقل كان مبنيًّا في النموذج ولا يصله شيء** — إدارةٌ بلا
مديرٍ معلَن رغم أن مكانه محجوز.

**ومركز التكلفة نموذجٌ بلا مسار** — والواجهة تناديه فيردّ ٤٠٤ في
كل فتح لملفّ موظف.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.organization.models import CostCenter, Department
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="org-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="راكان", family_name_ar="السهلي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1088001100", mobile="0508801100")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="O-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])

        u = User.objects.create_user(username="org.hr", password="x")
        p.user = u
        p.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, employment=emp,
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)

        dept = (Department.objects.filter(company=comp).first()
                or Department.objects.create(
                    account=acc, company=comp, code="OPS",
                    name_ar="العمليات"))

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "user": u, "dept": dept}


def test_department_manager_can_be_assigned(env, client):
    """
    ⚠️⚠️ الأهمّ: **ومدير الإدارة يُسنَد** — فالحقل كان معطَّلًا.
    """
    client.force_login(env["user"])
    res = client.put(
        f"/api/org/departments/{env['dept'].id}/",
        data={"manager_employment_id": env["emp"].id},
        content_type="application/json")
    assert res.status_code == 200, res.content[:200]

    with account_scope(env["account_id"]):
        env["dept"].refresh_from_db()
        assert env["dept"].manager_employment_id == env["emp"].id


def test_manager_appears_in_the_list(env, client):
    """ويظهر في القائمة باسمه — فلا يُقرأ برقمه."""
    with account_scope(env["account_id"]):
        env["dept"].manager_employment_id = env["emp"].id
        env["dept"].save(update_fields=["manager_employment_id"])

    client.force_login(env["user"])
    rows = client.get("/api/org/departments/").json()
    row = next(r for r in rows if r["id"] == env["dept"].id)
    assert row["manager_employment_id"] == env["emp"].id
    assert row["manager_name"], "المدير بلا اسم"


def test_manager_from_another_company_refused(env, client):
    """
    ⚠️ **ولا يُسنَد مديرٌ من شركةٍ أخرى**: فيكسر سلسلة الاعتماد
    ويطّلع على ما ليس له.
    """
    from apps.employees.models import Employment

    with account_scope(env["account_id"]):
        acc = Account.objects.get(id=env["account_id"])
        other = Company.objects.create(
            account=acc, legal_name_ar="شركة ثانية",
            cr_number="1010777666")
        p2, _ = create_person(
            account=acc, first_name_ar="سلطان",
            family_name_ar="الخالدي", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1099002200", mobile="0509900220")
        from apps.payroll.models import PayComponent
        b2 = PayComponent.objects.filter(company=other,
                                         code="BASIC").first()
        e2, _, _ = create_employment(
            person=p2, company=other, employee_no="X-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(b2, Decimal("8000"))] if b2 else None)

    client.force_login(env["user"])
    res = client.put(
        f"/api/org/departments/{env['dept'].id}/",
        data={"manager_employment_id": e2.id},
        content_type="application/json")
    assert res.status_code == 404, res.status_code

    with account_scope(env["account_id"]):
        env["dept"].refresh_from_db()
        assert env["dept"].manager_employment_id != e2.id


def test_manager_can_be_cleared(env, client):
    """ويُنزع بإرسال فراغ — فمن تغيّر منصبه لا يبقى مديرًا."""
    with account_scope(env["account_id"]):
        env["dept"].manager_employment_id = env["emp"].id
        env["dept"].save(update_fields=["manager_employment_id"])

    client.force_login(env["user"])
    client.put(f"/api/org/departments/{env['dept'].id}/",
               data={"manager_employment_id": None},
               content_type="application/json")

    with account_scope(env["account_id"]):
        env["dept"].refresh_from_db()
        assert env["dept"].manager_employment_id is None


def test_cost_centers_route_exists(env, client):
    """
    ⚠️⚠️ **ومسار مراكز التكلفة موجود** — فكان يردّ ٤٠٤ في كل فتح
    لملفّ موظف (بلاغ جواد).
    """
    client.force_login(env["user"])
    res = client.get("/api/org/cost-centers/")
    assert res.status_code == 200, res.status_code


def test_cost_center_crud(env, client):
    """ويُنشأ ويُقرأ ويُعدَّل."""
    client.force_login(env["user"])

    res = client.post("/api/org/cost-centers/",
                      data={"code": "CC9", "name_ar": "مركز جدة"},
                      content_type="application/json")
    assert res.status_code == 201, res.content[:200]
    cid = res.json()["id"]

    rows = client.get("/api/org/cost-centers/").json()
    assert any(r["id"] == cid for r in rows)

    client.put(f"/api/org/cost-centers/{cid}/",
               data={"name_ar": "مركز جدة الرئيسيّ"},
               content_type="application/json")
    with account_scope(env["account_id"]):
        assert CostCenter.objects.get(id=cid).name_ar == (
            "مركز جدة الرئيسيّ")


def test_duplicate_cost_center_code_refused(env, client):
    """ولا يتكرّر رمزٌ في شركة."""
    client.force_login(env["user"])
    client.post("/api/org/cost-centers/",
                data={"code": "CC8", "name_ar": "أوّل"},
                content_type="application/json")
    res = client.post("/api/org/cost-centers/",
                      data={"code": "CC8", "name_ar": "ثانٍ"},
                      content_type="application/json")
    assert res.status_code == 409


def test_used_cost_center_is_deactivated(env, client):
    """
    ⚠️ **والمستعمل يُعطَّل ولا يُحذف**: فموظفون وقيودٌ تشير إليه.
    """
    client.force_login(env["user"])
    res = client.post("/api/org/cost-centers/",
                      data={"code": "CC7", "name_ar": "مستعمل"},
                      content_type="application/json")
    cid = res.json()["id"]

    with account_scope(env["account_id"]):
        env["emp"].cost_center_id = cid
        env["emp"].save(update_fields=["cost_center"])

    out = client.delete(f"/api/org/cost-centers/{cid}/")
    assert out.status_code == 200
    assert out.json().get("deactivated") is True

    with account_scope(env["account_id"]):
        assert CostCenter.objects.filter(id=cid).exists()
        assert CostCenter.objects.get(id=cid).is_active is False
