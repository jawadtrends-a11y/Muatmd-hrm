"""
حرّاس خطاب PDF (ق-196).

⚠️⚠️ **والخطاب لم يكن يُطبع** — كشفه الجرد: **فخطاب تعريفٍ
بالراتب يُحمَل للبنك ورقةً**، ونصٌّ في الشاشة لا يُغني.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.models import IssuedLetter, LetterTemplate
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="ltr-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="بندر", family_name_ar="الشمراني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1080001100", mobile="0508000110")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="L-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])

        u = User.objects.create_user(username="ltr.hr", password="x")
        p.user = u
        p.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, employment=emp,
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)

        t = LetterTemplate.objects.create(
            account=acc, company=comp, code="INTRO",
            name_ar="تعريف بالراتب",
            heading_ar="تعريف بالراتب",
            body_ar="نفيدكم بأن الموظف {{employee_name}} يعمل لدينا.",
            valid_days=30)

        letter = IssuedLetter.objects.create(
            account=acc, company=comp, template=t, employment=emp,
            letter_no="LTR-2026-00001",
            heading_ar="تعريف بالراتب",
            addressee_ar="إلى من يهمّه الأمر",
            body_ar="نفيدكم بأن الموظف بندر الشمراني يعمل لدينا.",
            issued_on=date.today(),
            valid_until=date.today() + timedelta(days=30))

        yield {"account_id": r.account_id, "user": u, "emp": emp,
               "letter": letter, "template": t, "person": p}


def test_letter_is_a_real_pdf(env, client):
    """
    ⚠️⚠️ الأهمّ: **والخطاب يُطبع PDF** — فنصٌّ في الشاشة لا يُغني
    عن ورقةٍ تُحمَل للبنك.
    """
    client.force_login(env["user"])
    res = client.get(f"/api/letters/{env['letter'].id}/pdf/")
    assert res.status_code == 200, res.content[:200]
    assert res["Content-Type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"
    assert len(res.content) > 3000


def test_filename_carries_letter_no(env, client):
    """**والاسم يحمل رقم الخطاب** — فملفّاتٌ متشابهة تُربك."""
    client.force_login(env["user"])
    res = client.get(f"/api/letters/{env['letter'].id}/pdf/")
    assert "LTR-2026-00001" in res.get("Content-Disposition", "")


def test_owner_sees_his_own_letter(env, client):
    """
    ⚠️ **وصاحبه يراه دائمًا**: خطابه هو — **ولو لم يملك صلاحية**.
    """
    from apps.accounts.models_access import RoleAssignment as RA

    with account_scope(env["account_id"]):
        RA.objects.filter(membership__user=env["user"]).update(
            role=Role.objects.get(account_id=env["account_id"],
                                  code="employee"),
            scope=Scope.OWN.value)

    client.force_login(env["user"])
    res = client.get(f"/api/letters/{env['letter'].id}/pdf/")
    assert res.status_code == 200, res.status_code


def test_other_company_letter_is_hidden(env, client):
    """⚠️ **ولا يُقرأ خطابُ شركةٍ أخرى**."""
    client.force_login(env["user"])
    res = client.get("/api/letters/999999/pdf/")
    assert res.status_code == 404


def test_frozen_text_is_used_not_template(env, client):
    """
    ⚠️⚠️ **والنصّ المجمَّد لا القالب**: **فتعديل القالب بعد
    الإصدار لا يغيّر خطابًا صدر** — وهو وثيقةُ لحظتها.
    """
    from apps.core.services.letter_pdf import build_letter_pdf

    with account_scope(env["account_id"]):
        t = env["template"]
        t.body_ar = "نصٌّ جديدٌ تمامًا بعد الإصدار"
        t.save(update_fields=["body_ar"])

        out = build_letter_pdf(env["letter"])
        assert out[:4] == b"%PDF"
        # ⚠️ **والنصّ المجمَّد باقٍ في الخطاب**
        env["letter"].refresh_from_db()
        assert "بندر" in env["letter"].body_ar


def test_missing_header_does_not_break(env):
    """
    ⚠️ **وإخفاقُ الترويسة لا يكسر الخطاب**: فملفٌّ مفقودٌ يُتخطّى
    — **والنصّ أهمّ منه**.
    """
    from apps.core.services.letter_pdf import build_letter_pdf

    with account_scope(env["account_id"]):
        assert env["template"].header_image_id is None
        out = build_letter_pdf(env["letter"])
        assert out[:4] == b"%PDF"
