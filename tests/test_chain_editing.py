"""
حرّاس تعديل سلاسل الاعتماد (ق-88).

ما تمنعه:
  • منع الشركة من ضبط سلسلتها — فمن يعتمد ماذا قرارها لا قرارنا
  • فجوة في ترتيب الدرجات بعد الحذف
  • اصطدام قيد الفرادة عند إعادة الترتيب
  • تعديل سلسلة شركة أخرى
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
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import ApprovalChain


@pytest.fixture
def env(db):
    r = provision_account(slug="chain-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        p, _ = create_person(
            account=acc, first_name_ar="دانة", family_name_ar="المطيري",
            gender="female", nationality_code="SA",
            id_type="national_id", id_number="1033344455",
            mobile="0503334445")
        create_employment(person=p, company=comp, employee_no="C1",
                          join_date=date(2023, 1, 1))

        u = User.objects.create_user(username="ch.hr", password="x")
        p.user = u
        p.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m,
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)

        chain = ApprovalChain.objects.filter(
            company=comp).order_by("id").first()

        yield {"account_id": r.account_id, "user": u,
               "chain_id": chain.id if chain else None}


def _chain(c, cid):
    """السلسلة بمعرّفها — لا بترتيبها في القائمة."""
    return next(x for x in c.get("/api/leaves/chains/").json()
                if x["id"] == cid)


def _client(env):
    c = Client()
    c.force_login(env["user"])
    return c


@pytest.mark.django_db(transaction=True)
def test_company_can_add_a_step(env):
    """
    ⚠️ الشركة تضبط سلسلتها — فمن يعتمد ماذا قرارها لا قرارنا.

    ومنع التعديل يفرض آليتنا على شركة تختلف عنها (ق-88).
    """
    if env["chain_id"] is None:
        pytest.skip("لا سلاسل افتراضية")

    c = _client(env)
    before = len(_chain(c, env["chain_id"])["steps"])

    r = c.post(f"/api/leaves/chains/{env['chain_id']}/steps/",
               data=json.dumps({"approver_type": "role",
                                "approver_role_code": "ceo"}),
               content_type="application/json")

    assert r.status_code == 201, r.content.decode()[:200]
    assert len(r.json()["steps"]) == before + 1


@pytest.mark.django_db(transaction=True)
def test_delete_closes_the_gap(env):
    """
    ⚠️ الترتيب يُرصّ بعد الحذف.

    ففجوة في الأرقام (1، 3، 4) تربك قراءة السلسلة، وقد تُوقف
    الطلب عند درجة لا وجود لها.
    """
    if env["chain_id"] is None:
        pytest.skip("لا سلاسل افتراضية")

    c = _client(env)
    cid = env["chain_id"]

    for code in ("ceo", "owner"):
        c.post(f"/api/leaves/chains/{cid}/steps/",
               data=json.dumps({"approver_type": "role",
                                "approver_role_code": code}),
               content_type="application/json")

    steps = _chain(c, cid)["steps"]
    middle = steps[len(steps) // 2]

    r = c.delete(f"/api/leaves/chains/{cid}/steps/"
                 f"?step_id={middle['id']}")
    assert r.status_code == 200

    orders = [s["step_order"] for s in r.json()["steps"]]
    assert orders == list(range(1, len(orders) + 1)), (
        f"فجوة في الترتيب: {orders}")


@pytest.mark.django_db(transaction=True)
def test_reorder_does_not_hit_unique_constraint(env):
    """
    ⚠️ إعادة الترتيب لا تصطدم بقيد الفرادة.

    فالترتيب فريد لكل سلسلة، والمبادلة المباشرة تجعل درجتين
    برقم واحد لحظةً — فيسقط الطلب بخطأ قاعدة لا برسالة.
    """
    if env["chain_id"] is None:
        pytest.skip("لا سلاسل افتراضية")

    c = _client(env)
    cid = env["chain_id"]

    c.post(f"/api/leaves/chains/{cid}/steps/",
           data=json.dumps({"approver_type": "role",
                            "approver_role_code": "ceo"}),
           content_type="application/json")

    steps = _chain(c, cid)["steps"]
    if len(steps) < 2:
        pytest.skip("درجة واحدة")

    last = steps[-1]
    r = c.put(f"/api/leaves/chains/{cid}/steps/",
              data=json.dumps({"step_id": last["id"], "move": "up"}),
              content_type="application/json")

    assert r.status_code == 200, r.content.decode()[:200]
    orders = [s["step_order"] for s in r.json()["steps"]]
    assert len(orders) == len(set(orders)), f"ترتيب مكرّر: {orders}"


@pytest.mark.django_db(transaction=True)
def test_specific_person_step(env):
    """
    الدرجة تُسند لموظف بعينه لا لدور فقط.

    فبعض الشركات تسمّي شخصًا معتمِدًا بذاته.
    """
    if env["chain_id"] is None:
        pytest.skip("لا سلاسل افتراضية")

    c = _client(env)
    pid = c.get("/api/employees/").json()[0]["person_id"]

    r = c.post(f"/api/leaves/chains/{env['chain_id']}/steps/",
               data=json.dumps({"approver_type": "specific_person",
                                "approver_person_id": pid}),
               content_type="application/json")

    assert r.status_code == 201, r.content.decode()[:200]
    added = r.json()["steps"][-1]
    assert added["approver_person_name"], "لم يُسنَد الموظف"


@pytest.mark.django_db(transaction=True)
def test_other_company_chain_is_invisible(env):
    """⚠️ سلسلة شركة أخرى لا تُعدَّل ولا تُرى."""
    other = provision_account(slug="chain-o", display_name_ar="آخر",
                              company_name_ar="شركة", is_sandbox=True)
    with account_scope(other.account_id):
        foreign = ApprovalChain.objects.filter(
            company_id=other.company_id).order_by("id").first()

    if foreign is None:
        pytest.skip("لا سلاسل في الحساب الآخر")

    c = _client(env)
    r = c.post(f"/api/leaves/chains/{foreign.id}/steps/",
               data=json.dumps({"approver_type": "role",
                                "approver_role_code": "ceo"}),
               content_type="application/json")

    assert r.status_code == 404, "وصل لسلسلة شركة أخرى"
