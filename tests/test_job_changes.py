"""
حرّاس التغيير الوظيفي (ق-82).

ما تمنعه:
  • تسجيل تغيير يفرغ موقعًا إداريًا بلا بديل
  • اعتماد موظف الموارد لما يسجّله — فهو ينفّذ لا يقرّر
  • سريان الأثر قبل الاعتماد
  • تغييران معلّقان لموظف واحد
  • ضياع القيم القديمة — فالمراجعة تحتاج ما كان قبل ما صار
"""
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (AccountMembership, Role,
                                         RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.models import (ChangeStatus, ChangeType, Employment,
                                   JobChange)
from apps.employees.services.hiring import create_employment, create_person
from apps.employees.services.job_changes import (JobChangeError,
                                                 create_change,
                                                 decide_change)
from apps.organization.models import Department


@pytest.fixture
def env(db):
    r = provision_account(slug="jc-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        d1 = Department.objects.create(account=acc, company=comp,
                                       name_ar="المبيعات", code="SAL")
        d2 = Department.objects.create(account=acc, company=comp,
                                       name_ar="المشتريات", code="PUR")

        def hire(first, family, nid, mobile, no, code, scope, dept):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mobile)
            e, _, _ = create_employment(person=p, company=comp,
                                        employee_no=no,
                                        join_date=date(2023, 1, 1),
                                        department=dept)
            u = User.objects.create_user(username=f"jc.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, role=Role.objects.get(account=acc, code=code),
                company=comp, scope=scope.value)
            return e

        hrm = hire("دانة", "المطيري", "1011122233", "0501112223", "H1",
                   "hr_manager", Scope.COMPANY, d1)
        hrs = hire("أمل", "الغامدي", "1022233344", "0502223334", "H2",
                   "hr_staff", Scope.COMPANY, d1)
        sup = hire("خالد", "الحربي", "1033344455", "0503334445", "S1",
                   "supervisor", Scope.TEAM, d1)
        peer = hire("سلطان", "الرشيدي", "1044455566", "0504445556", "S2",
                    "supervisor", Scope.TEAM, d1)
        emp = hire("وليد", "العنزي", "1055566677", "0505556667", "E1",
                   "employee", Scope.OWN, d1)

        emp.direct_manager = sup
        emp.save(update_fields=["direct_manager"])

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "d1": d1, "d2": d2, "hrm": hrm, "hrs": hrs,
               "sup": sup, "peer": peer, "emp": emp}


def _client(employment):
    c = Client()
    c.force_login(employment.person.user)
    return c


def _post(employment, path, body):
    import json
    return _client(employment).post(
        path, data=json.dumps(body), content_type="application/json")


# ══════════ البديل شرط (ق-79) ══════════

@pytest.mark.django_db(transaction=True)
def test_admin_change_needs_successor(env):
    """
    ⚠️ من يُرقّى أو يُنقل يترك موقعه كمن يستقيل — فالبديل شرط.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(JobChangeError) as e:
            create_change(employment=env["sup"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today(),
                          new_department=env["d2"])
        assert "بديل" in str(e.value)


@pytest.mark.django_db(transaction=True)
def test_regular_employee_needs_no_successor(env):
    """الحارس المقابل: الموظف العادي يُنقل بلا بديل."""
    with account_scope(env["account_id"]):
        c = create_change(employment=env["emp"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today(),
                          new_department=env["d2"])
        assert c.status == ChangeStatus.PENDING


# ══════════ الاعتماد قبل الأثر (ق-82) ══════════

@pytest.mark.django_db(transaction=True)
def test_effect_waits_for_approval(env):
    """
    ⚠️ الأثر بالاعتماد لا بالتسجيل — فقد يُرفض التغيير.
    """
    with account_scope(env["account_id"]):
        c = create_change(employment=env["emp"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today(),
                          new_department=env["d2"])
        env["emp"].refresh_from_db()
        assert env["emp"].department_id == env["d1"].id, (
            "انتقل القسم قبل الاعتماد")

        decide_change(change=c, approve=True)
        env["emp"].refresh_from_db()
        assert env["emp"].department_id == env["d2"].id, (
            "لم ينتقل القسم بعد الاعتماد")


@pytest.mark.django_db(transaction=True)
def test_rejection_changes_nothing(env):
    """الرفض لا يحرّك شيئًا — والتغيير يبقى مسجّلًا مرفوضًا."""
    with account_scope(env["account_id"]):
        c = create_change(employment=env["emp"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today(),
                          new_department=env["d2"])
        c, _ = decide_change(change=c, approve=False)
        env["emp"].refresh_from_db()

    assert c.status == ChangeStatus.REJECTED
    assert env["emp"].department_id == env["d1"].id, "تغيّر رغم الرفض"


@pytest.mark.django_db(transaction=True)
def test_decision_is_final(env):
    """لا يُعاد القرار — سجل لا يُعدَّل بعد اتخاذه (ق-44)."""
    with account_scope(env["account_id"]):
        c = create_change(employment=env["emp"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today(),
                          new_department=env["d2"])
        decide_change(change=c, approve=True)
        with pytest.raises(JobChangeError):
            decide_change(change=c, approve=False)


# ══════════ الفصل بين التسجيل والاعتماد ══════════

@pytest.mark.django_db(transaction=True)
def test_hr_staff_registers_but_does_not_decide(env):
    """
    ⚠️ موظف الموارد ينفّذ ولا يقرّر — ومدير الموارد يعتمد (ق-82).
    """
    r = _post(env["hrs"], f"/api/employees/{env['emp'].id}/job-changes/", {
        "change_type": "transfer",
        "effective_from": str(date.today()),
        "new_department_id": env["d2"].id,
    })
    assert r.status_code == 201, r.content.decode()[:200]
    cid = r.json()["id"]

    denied = _post(env["hrs"], f"/api/job-changes/{cid}/decide/",
                   {"approve": True})
    assert denied.status_code == 403, "اعتمد موظف الموارد ما سجّله"

    ok = _post(env["hrm"], f"/api/job-changes/{cid}/decide/",
               {"approve": True})
    assert ok.status_code == 200, ok.content.decode()[:200]


# ══════════ سلامة السجل ══════════

@pytest.mark.django_db(transaction=True)
def test_old_values_are_kept(env):
    """
    ⚠️ القيم القديمة تُحفظ — من يراجع بعد سنة يحتاج معرفة ما كان
    قبل ما صار (ق-80).
    """
    with account_scope(env["account_id"]):
        c = create_change(employment=env["emp"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today(),
                          new_department=env["d2"])
    assert c.old_department_id == env["d1"].id, "ضاع القسم القديم"
    assert c.old_direct_manager_id == env["sup"].id, "ضاع المدير القديم"


@pytest.mark.django_db(transaction=True)
def test_one_pending_change_at_a_time(env):
    """
    تغييران معلّقان لموظف واحد يتضاربان — فالثاني يُرفض.
    """
    with account_scope(env["account_id"]):
        create_change(employment=env["emp"],
                      change_type=ChangeType.TRANSFER,
                      effective_from=date.today(),
                      new_department=env["d2"])
        with pytest.raises(JobChangeError) as e:
            create_change(employment=env["emp"],
                          change_type=ChangeType.PROMOTION,
                          effective_from=date.today())
        assert "بانتظار الاعتماد" in str(e.value)


@pytest.mark.django_db(transaction=True)
def test_dismissal_needs_reason(env):
    """الفصل بلا سبب نظامي لا يُسجَّل — والسبب يحدّد الاستحقاق."""
    with account_scope(env["account_id"]):
        with pytest.raises(JobChangeError) as e:
            create_change(employment=env["emp"],
                          change_type=ChangeType.DISMISSAL,
                          effective_from=date.today())
        assert "سبب" in str(e.value)


@pytest.mark.django_db(transaction=True)
def test_transfer_needs_department(env):
    """النقل بلا إدارة جديدة لا معنى له."""
    with account_scope(env["account_id"]):
        with pytest.raises(JobChangeError):
            create_change(employment=env["emp"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today())


@pytest.mark.django_db(transaction=True)
def test_successor_appointed_on_approval(env):
    """
    ⚠️ الخليفة يُعيَّن بالاعتماد — فيرث الموقع من تاريخ السريان.
    """
    from apps.leaves.services.delegation import successor_of

    with account_scope(env["account_id"]):
        c = create_change(employment=env["sup"],
                          change_type=ChangeType.TRANSFER,
                          effective_from=date.today(),
                          new_department=env["d2"],
                          successor=env["peer"])
        assert successor_of(env["sup"]) is None, "عُيّن قبل الاعتماد"

        decide_change(change=c, approve=True)
        s = successor_of(env["sup"])

    assert s is not None, "لم يُعيَّن الخليفة بعد الاعتماد"
    assert s.deputy_id == env["peer"].id
    assert s.is_permanent, "الخلافة مؤقتة — والمغادر لا يُنتظر رجوعه"
