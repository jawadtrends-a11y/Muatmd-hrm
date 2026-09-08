"""
حرّاس الدعوة للانضمام (ق-94).

عبر HTTP لا بالاستدعاء المباشر: manage.py shell يتجاوز العزل
والطلب الحقيقيّ لا يتجاوزه.

وأخطرها الأخير: قبولٌ فاشل يترك مستخدمًا يتيمًا — حساب يدخل
النظام بلا ملفّ موظف، فيرى شاشة فارغة ولا يعرف لماذا.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.models_invite import JoinInvite
from apps.accounts.services.invites import create_invite
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.models import Person
from apps.employees.services.hiring import create_employment, create_person


@pytest.fixture
def env(db):
    """مدير موارد بحساب، وثلاثة أشخاص: بحساب، وبمعرّف، وبلا معرّف."""
    r = provision_account(slug="invite-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    out = {"account_id": r.account_id, "company_id": r.company_id}
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        # مدير الموارد — يملك employees.invite افتراضيًّا
        hr_u = User.objects.create_user(username="inv.hr", password="Pw@2026xx")
        m = AccountMembership.objects.create(user=hr_u, account=acc,
                                             active_company=comp)
        RoleAssignment.objects.create(
            membership=m, role=Role.objects.get(account=acc, code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)
        hr_p, _ = create_person(
            account=acc, first_name_ar="دانة", family_name_ar="المطيري",
            gender="female", nationality_code="SA", id_type="national_id",
            id_number="1091112223", mobile="0509991112", user=hr_u)
        create_employment(person=hr_p, company=comp, employee_no="HR-1",
                          join_date=date(2020, 1, 1))
        out["with_login"] = hr_p.id

        # موظف عاديّ بحساب — لاختبار المنع بالصلاحية
        emp_u = User.objects.create_user(username="inv.emp", password="Pw@2026xx")
        m2 = AccountMembership.objects.create(user=emp_u, account=acc,
                                              active_company=comp)
        RoleAssignment.objects.create(
            membership=m2, role=Role.objects.get(account=acc, code="employee"),
            company=comp, scope=Scope.OWN.value)
        emp_p, _ = create_person(
            account=acc, first_name_ar="وليد", family_name_ar="العنزي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1092223334", mobile="0508882223", user=emp_u)
        create_employment(person=emp_p, company=comp, employee_no="E-1",
                          join_date=date(2021, 1, 1))

        # مدعوّ: بلا حساب وله معرّفات
        p_ok, _ = create_person(
            account=acc, first_name_ar="فهد", family_name_ar="السبيعي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1093334445", mobile="0507773334")
        create_employment(person=p_ok, company=comp, employee_no="N-1",
                          join_date=date(2022, 1, 1))
        out["invitable"] = p_ok.id

        # بلا معرّف إطلاقًا — تُنزع بعد الإنشاء (الإنشاء يشترطها)
        p_bad, _ = create_person(
            account=acc, first_name_ar="ماجد", family_name_ar="الدوسري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1094445556", mobile="0506664445")
        create_employment(person=p_bad, company=comp, employee_no="N-2",
                          join_date=date(2022, 6, 1))
        Person.objects.filter(id=p_bad.id).update(
            email="", id_number="", mobile_e164="")
        out["no_identifier"] = p_bad.id

        # دعوة جاهزة برمزها الخام
        inv, raw = create_invite(p_ok, account_id=r.account_id,
                                 company_id=r.company_id)
        out["raw_token"] = raw
        out["invite_id"] = inv.id

    c = Client()
    out["hr"] = {"HTTP_AUTHORIZATION": "Bearer " + _login(c, "inv.hr")}
    out["emp"] = {"HTTP_AUTHORIZATION": "Bearer " + _login(c, "inv.emp")}
    out["client"] = c
    return out


def _login(c, username):
    r = c.post("/api/auth/login/",
               data={"identifier": username, "password": "Pw@2026xx"},
               content_type="application/json")
    assert r.status_code == 200, r.content
    return r.json()["token"]


def test_employee_cannot_invite(env):
    r = env["client"].post(f"/api/employees/{env['invitable']}/invite/",
                           **env["emp"])
    assert r.status_code == 403


def test_blocked_without_identifier(env):
    """رسالة تطلب إكمال البيانات — لا صمت ولا حساب لا يُدخَل به."""
    r = env["client"].post(f"/api/employees/{env['no_identifier']}/invite/",
                           **env["hr"])
    assert r.status_code == 400
    assert r.json()["code"] == "no_identifier"


def test_blocked_when_account_exists(env):
    r = env["client"].post(f"/api/employees/{env['with_login']}/invite/",
                           **env["hr"])
    assert r.status_code == 400
    assert r.json()["code"] == "already_has_account"


def test_preview_returns_name_only(env):
    """لا تسريب: الاسم والشركة فقط، لا هوية ولا جوال ولا راتب."""
    r = env["client"].get(f"/api/join/{env['raw_token']}/")
    assert r.status_code == 200
    assert set(r.json()) == {"valid", "name", "company_ar", "company_en",
                             "default_locale"}


def test_token_is_single_use(env):
    t = env["raw_token"]
    assert env["client"].post(
        f"/api/join/{t}/accept/", data={"password": "Strong@2026x"},
        content_type="application/json").status_code == 200
    assert env["client"].post(
        f"/api/join/{t}/accept/", data={"password": "Other@2026xy"},
        content_type="application/json").status_code == 409


def test_failed_accept_leaves_no_orphan_user(env):
    """
    ⚠️ الأهمّ: قبولٌ فاشل لا يُخلّف حسابًا بلا ملفّ موظف.

    فالحساب اليتيم يدخل النظام ويرى شاشة فارغة، ويبقى مسار دخول
    بلا صاحب.
    """
    before = User.objects.filter(username__startswith="u-").count()
    r = env["client"].post("/api/join/no-such-token/accept/",
                           data={"password": "Strong@2026x"},
                           content_type="application/json")
    assert r.status_code == 404
    assert User.objects.filter(username__startswith="u-").count() == before


def test_accepted_user_is_linked_to_person(env):
    env["client"].post(f"/api/join/{env['raw_token']}/accept/",
                       data={"password": "Strong@2026x"},
                       content_type="application/json")
    for u in User.objects.filter(username__startswith="u-"):
        assert Person.objects.filter(user_id=u.id).exists(), \
            f"مستخدم يتيم: {u.username}"


def test_reinvite_revokes_previous(env):
    """إعادة الدعوة تُلغي القديمة — فلا رابطان حيّان لشخص واحد."""
    old = env["raw_token"]
    r = env["client"].post(f"/api/employees/{env['invitable']}/invite/",
                           **env["hr"])
    assert r.status_code == 200
    assert env["client"].get(f"/api/join/{old}/").status_code == 410
