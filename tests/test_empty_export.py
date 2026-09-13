"""
حرّاس الملفّ الفارغ (ق-145).

⚠️⚠️ **ملفٌّ بلا صفوف لا يُنزَّل**: فيُرفع للبنك بعناوينه وحدها،
**ويُظنّ أن الرواتب أُرسلت** — والسكوت هنا أخطر من الخطأ.
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
from apps.payroll.models import (
    PayComponent, PayrollRunStatus, PayrollRunType)
from apps.payroll.services import engine
from apps.payroll.services.outputs.wps import build_wps_file


@pytest.fixture
def env(db, client):
    r = provision_account(slug="exp-e", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="عمر", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1055566677", mobile="0505556667")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="E-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("8000"))])

        u = User.objects.create_user(username="exp.hr", password="x")
        p.user = u
        p.save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, employment=emp,
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)

        run = engine.create_run(company=comp,
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        run.status = PayrollRunStatus.SUBMITTED
        run.save(update_fields=["status"])
        engine.approve_run(run, None)

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "run": run, "user": u}


def test_wps_excludes_leave_no_rows(env):
    """
    ⚠️ **ومستبعَدٌ بلا صفوف ملفٌّ فارغ**.

    فمن استُبعد من حماية الأجور لا يظهر — والملفّ يصير عناوينَ
    وحدها.
    """
    with account_scope(env["account_id"]):
        for slip in env["run"].payslips.all():
            slip.include_in_wps = False
            slip.save(update_fields=["include_in_wps"])

        wps = build_wps_file(env["run"])
        assert wps.record_count == 0
        assert len(wps.excluded) >= 1
        assert not wps.errors, "استُبعدوا بخطأ لا بعلم الاستبعاد"


def test_empty_wps_is_not_downloadable(env, client):
    """
    ⚠️⚠️ الأهمّ: **الملفّ الفارغ يُمنع لا يُنزَّل**.

    فبلا هذا يُرفع للبنك ملفٌّ بعناوينه وحدها، ويُظنّ أن الرواتب
    أُرسلت.
    """
    with account_scope(env["account_id"]):
        for slip in env["run"].payslips.all():
            slip.include_in_wps = False
            slip.save(update_fields=["include_in_wps"])

    client.force_login(env["user"])
    res = client.get(
        f"/api/payroll/runs/{env['run'].id}/wps/download/")
    assert res.status_code == 409, res.status_code
    body = res.json()
    assert body.get("code") == "empty_file", body
    assert body.get("excluded"), "لم يُبيَّن من استُبعد"


def test_wps_with_rows_downloads(env, client):
    """وبصفوفٍ صحيحة يُنزَّل."""
    with account_scope(env["account_id"]):
        for slip in env["run"].payslips.all():
            slip.include_in_wps = True
            slip.iban = "SA0380000000608010167519"
            slip.save(update_fields=["include_in_wps", "iban"])

    client.force_login(env["user"])
    res = client.get(
        f"/api/payroll/runs/{env['run'].id}/wps/download/")
    assert res.status_code == 200, res.content[:200]
    text = res.content.decode("utf-8")
    assert len(text.strip().splitlines()) >= 2, "عناوين بلا صفوف"


def test_bad_iban_is_an_error_not_silence(env, client):
    """
    **وآيبانٌ خاطئ خطأٌ لا صمت** — فيُمنع الملفّ ويُسمّى صاحبه.
    """
    with account_scope(env["account_id"]):
        for slip in env["run"].payslips.all():
            slip.include_in_wps = True
            slip.iban = "SA00"
            slip.save(update_fields=["include_in_wps", "iban"])

        wps = build_wps_file(env["run"])
        assert wps.errors, "مرّ آيبانٌ خاطئ بلا خطأ"
        assert wps.record_count == 0
