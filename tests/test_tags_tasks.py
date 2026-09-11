"""
حرّاس الدليل والوسوم والمهام (ق-131).

⚠️ **الدليل يفتحه كل موظف** — فلا بيانات حسّاسة فيه، ولا يمرّ
بنطاق «الموظفين» وإلا رأى من نطاقه نفسه نفسَه وحده في دليل
الزملاء.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.models import (
    EmployeeTag, EmployeeTagAssignment, Task, TaskStatus)
from apps.employees.services.hiring import create_employment, create_person

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="tt-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        def hire(first, nid, mob, no, code, scope):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar="الحارثي",
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=TODAY - timedelta(days=200),
                salary_lines=[(basic, Decimal("6000"))])
            u = User.objects.create_user(username=f"tt.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, employment=e,
                role=Role.objects.get(account=acc, code=code),
                company=comp, scope=scope)
            return u, e

        hr, hr_e = hire("فيصل", "1011122255", "0501112225", "T-1",
                        "hr_manager", Scope.COMPANY.value)
        emp, emp_e = hire("ريم", "1022233366", "0502223336", "T-2",
                          "employee", Scope.OWN.value)

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "hr": hr, "hr_e": hr_e, "emp": emp, "emp_e": emp_e}


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def test_directory_shows_all_colleagues(env):
    """
    ⚠️ الأهمّ: **الدليل يُظهر الزملاء كلّهم** لكل موظف.

    فلو مرّ بنطاق «الموظفين» لرأى من نطاقه نفسه نفسَه وحده — وهو
    دليلُ زملاء لا ملفّات.
    """
    with account_scope(env["account_id"]):
        d = _client(env["emp"]).get("/api/directory/")
        assert d.status_code == 200
        assert d.json()["count"] == 2, d.json()


def test_directory_hides_sensitive_fields(env):
    """
    ⚠️ **ولا بيانات حسّاسة فيه**: لا راتب ولا هوية ولا آيبان.

    فمن أراد الملفّ يذهب إليه بصلاحيته.
    """
    with account_scope(env["account_id"]):
        rows = _client(env["emp"]).get("/api/directory/").json()["rows"]
        text = str(rows)
        for leak in ("id_number", "iban", "salary", "basic"):
            assert leak not in text, f"تسريب: {leak}"


def test_directory_search_filters(env):
    """والبحث يرشّح بالاسم والرقم."""
    with account_scope(env["account_id"]):
        d = _client(env["hr"]).get("/api/directory/?q=ريم")
        assert d.json()["count"] == 1


def test_tag_assign_and_remove(env):
    """الوسم يُسند ويُنزع."""
    import json

    with account_scope(env["account_id"]):
        c = _client(env["hr"])
        r = c.post("/api/tags/", data=json.dumps({"name_ar": "سائق"}),
                   content_type="application/json")
        assert r.status_code == 201, r.content
        tag_id = r.json()["id"]

        emp_id = env["emp_e"].id
        a = c.post(f"/api/employees/{emp_id}/tags/",
                   data=json.dumps({"tag_id": tag_id}),
                   content_type="application/json")
        assert a.status_code == 201
        assert EmployeeTagAssignment.objects.filter(
            tag_id=tag_id, employment_id=emp_id).exists()

        c.delete(f"/api/employees/{emp_id}/tags/",
                 data=json.dumps({"tag_id": tag_id}),
                 content_type="application/json")
        assert not EmployeeTagAssignment.objects.filter(
            tag_id=tag_id, employment_id=emp_id).exists()


def test_duplicate_tag_is_refused(env):
    """ووسمٌ مكرّر يُرفض — فالتصنيف يفقد معناه بتكراره."""
    import json

    with account_scope(env["account_id"]):
        c = _client(env["hr"])
        body = json.dumps({"name_ar": "مناوب"})
        assert c.post("/api/tags/", data=body,
                      content_type="application/json").status_code == 201
        assert c.post("/api/tags/", data=body,
                      content_type="application/json").status_code == 409


def test_cannot_assign_task_outside_scope(env):
    """
    ⚠️ ولا يُسنِد مهمّةً إلا لمن يراه.

    فمن نطاقه نفسه يُسنِد لنفسه — ولا يُلقي بعملٍ على غيره.
    """
    import json

    with account_scope(env["account_id"]):
        r = _client(env["emp"]).post("/api/tasks/", data=json.dumps({
            "title": "مهمّة مدسوسة",
            "assignee_id": env["hr_e"].id,
        }), content_type="application/json")
        assert r.status_code == 403, r.content


def test_manager_assigns_and_employee_completes(env):
    """والمدير يُسنِد، والمسنَد إليه يُنجز."""
    import json

    with account_scope(env["account_id"]):
        r = _client(env["hr"]).post("/api/tasks/", data=json.dumps({
            "title": "جرد العهد",
            "assignee_id": env["emp_e"].id,
            "due_date": str(TODAY + timedelta(days=3)),
            "priority": "high",
        }), content_type="application/json")
        assert r.status_code == 201, r.content
        tid = r.json()["id"]

        done = _client(env["emp"]).put(
            f"/api/tasks/{tid}/",
            data=json.dumps({"status": "done",
                             "completion_note": "أُنجز"}),
            content_type="application/json")
        assert done.status_code == 200
        t = Task.objects.get(id=tid)
        assert t.status == TaskStatus.DONE
        assert t.completed_at is not None


def test_done_task_is_cancelled_not_deleted(env):
    """
    ⚠️ والمنجزة **لا تُحذف**: سجلُّ ما أُنجز يُراجَع، ومحوُه
    يُخفي عمل الموظف.
    """
    import json

    with account_scope(env["account_id"]):
        c = _client(env["hr"])
        tid = c.post("/api/tasks/", data=json.dumps({
            "title": "مهمّة", "assignee_id": env["emp_e"].id,
        }), content_type="application/json").json()["id"]

        c.put(f"/api/tasks/{tid}/", data=json.dumps({"status": "done"}),
              content_type="application/json")
        r = c.delete(f"/api/tasks/{tid}/")
        assert r.status_code == 409, r.content
        assert Task.objects.filter(id=tid).exists()


def test_overdue_is_flagged(env):
    """والمتأخّرة تُعلَّم — فالقائمة تنبيهٌ لا عرض."""
    import json

    with account_scope(env["account_id"]):
        c = _client(env["hr"])
        c.post("/api/tasks/", data=json.dumps({
            "title": "متأخّرة", "assignee_id": env["hr_e"].id,
            "due_date": str(TODAY - timedelta(days=2)),
        }), content_type="application/json")

        rows = c.get("/api/tasks/").json()
        assert rows and rows[0]["overdue"] is True
