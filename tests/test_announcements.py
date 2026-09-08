"""
حرّاس الإعلانات (ق-102).

وأهمّها اثنان: المرسِل لا يتجاوز نطاقه، وكل مستقبل يقرأ بلغته.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import PERMISSIONS, Scope
from apps.core.tenancy.context import account_scope
from apps.employees.models import Person
from apps.employees.services.hiring import create_employment, create_person
from apps.notifications.models import Notification
from apps.organization.services.structure import create_department


def _mk(acc, comp, username, role_code, scope, first, family, idn, mob,
        dept=None, locale="ar", email=""):
    u = User.objects.create_user(username=username, password="Pw@2026xx")
    m = AccountMembership.objects.create(user=u, account=acc,
                                         active_company=comp)
    RoleAssignment.objects.create(
        membership=m, role=Role.objects.get(account=acc, code=role_code),
        company=comp, scope=scope)
    p, _ = create_person(account=acc, first_name_ar=first,
                         family_name_ar=family, gender="male",
                         nationality_code="SA", id_type="national_id",
                         id_number=idn, mobile=mob, user=u)
    Person.objects.filter(id=p.id).update(preferred_locale=locale,
                                          email=email)
    e, _, _ = create_employment(person=p, company=comp,
                                employee_no=username[:8],
                                join_date=date(2021, 1, 1),
                                department=dept)
    return p, e


@pytest.fixture
def env(db):
    r = provision_account(slug="ann-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    out = {"account_id": r.account_id, "company_id": r.company_id}
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        d1 = create_department(company=comp, code="D1", name_ar="العمليات")
        d2 = create_department(company=comp, code="D2", name_ar="المالية")
        out["d1"], out["d2"] = d1.id, d2.id

        _mk(acc, comp, "ann.hr", "hr_manager", Scope.COMPANY.value,
            "دانة", "المطيري", "1081112223", "0501112223")
        _mk(acc, comp, "ann.dm", "dept_manager", Scope.DEPARTMENT.value,
            "نايف", "الحربي", "1082223334", "0502223334", dept=d1)
        p_ar, _ = _mk(acc, comp, "ann.e1", "employee", Scope.OWN.value,
                      "وليد", "العنزي", "1083334445", "0503334445", dept=d1)
        p_en, _ = _mk(acc, comp, "ann.e2", "employee", Scope.OWN.value,
                      "سامي", "القحطاني", "1084445556", "0504445556",
                      dept=d2, locale="en")
        out["p_ar"], out["p_en"] = p_ar.id, p_en.id

    c = Client()
    for k, u in (("hr", "ann.hr"), ("dm", "ann.dm"), ("emp", "ann.e1")):
        rr = c.post("/api/auth/login/",
                    data={"identifier": u, "password": "Pw@2026xx"},
                    content_type="application/json")
        assert rr.status_code == 200, rr.content
        out[k] = {"HTTP_AUTHORIZATION": "Bearer " + rr.json()["token"]}
    out["client"] = c
    return out


def _send(env, who, **kw):
    body = {"kind": "general", "audience_type": "company",
            "title_ar": "عنوان", "body_ar": "نصّ"}
    body.update(kw)
    return env["client"].post("/api/announcements/", data=body,
                              content_type="application/json", **env[who])


def test_employee_cannot_send(env):
    assert _send(env, "emp").status_code == 403


def test_dept_manager_cannot_send_company_wide(env):
    """يُرفض صراحةً ولا يُحوَّل بصمت لإدارته — فقد ظنّ أنه خاطب الجميع."""
    r = _send(env, "dm")
    assert r.status_code == 403
    assert r.json()["code"] == "company_wide_not_allowed"


def test_dept_manager_cannot_reach_another_department(env):
    r = _send(env, "dm", audience_type="departments",
              audience_ids=[env["d2"]])
    assert r.status_code == 403
    assert r.json()["code"] == "department_not_allowed"


def test_dept_manager_reaches_own_department(env):
    r = _send(env, "dm", audience_type="departments",
              audience_ids=[env["d1"]])
    assert r.status_code == 201
    assert r.json()["recipient_count"] >= 1


def test_hr_reaches_whole_company(env):
    r = _send(env, "hr")
    assert r.status_code == 201
    assert r.json()["recipient_count"] == 4


def test_each_recipient_reads_in_own_language(env, settings):
    """
    ⚠️ الأهمّ: رسالة واحدة، وكل مستقبل بلغته.

    وليست اللغة غلافًا: من لغته إنجليزية يقرأ النصّ الإنجليزيّ
    نفسه لا عنوانًا مترجمًا ومضمونًا عربيًّا.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    r = _send(env, "hr", title_ar="اجتماع", title_en="Meeting",
              body_ar="الاجتماع غدًا.", body_en="The meeting is tomorrow.")
    assert r.status_code == 201

    ar = Notification.objects.get(recipient_person_id=env["p_ar"],
                                  event_key="announcement.published")
    en = Notification.objects.get(recipient_person_id=env["p_en"],
                                  event_key="announcement.published")
    assert ar.locale == "ar" and "اجتماع" in ar.title
    assert en.locale == "en" and en.title == "Meeting"
    assert "tomorrow" in en.body, "الغلاف إنجليزيّ والمضمون عربيّ"


def test_unknown_kind_rejected(env):
    assert _send(env, "hr", kind="لا-نوع").status_code == 400


def test_empty_title_rejected(env):
    assert _send(env, "hr", title_ar="  ").status_code == 400


def test_permission_catalog_has_no_duplicates():
    """
    ⚠️ سكربتٌ يُعاد تنفيذه يضاعف الصلاحية بصمت — ولا شيء يشتكي.
    وقد وقع فعلًا عند إضافة صلاحيات الإعلانات.
    """
    keys = [p.key for p in PERMISSIONS]
    dups = sorted({k for k in keys if keys.count(k) > 1})
    assert not dups, f"صلاحيات مكرّرة في الكتالوج: {dups}"
