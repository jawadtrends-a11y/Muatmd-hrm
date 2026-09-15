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


def test_no_one_is_excluded(env):
    """
    ⚠️⚠️ **ولا استبعادَ أحد** (قرار جواد ق-179): فعدمُ التسجيل في
    حماية الأجور **ليس سببًا لحجب الموظف** — والملفّ يُصدَّر
    بالجميع، **والبنك يقرّر**.
    """
    with account_scope(env["account_id"]):
        for slip in env["run"].payslips.all():
            slip.include_in_wps = False
            slip.iban = "SA0380000000608010167519"
            slip.save(update_fields=["include_in_wps", "iban"])

        wps = build_wps_file(env["run"])
        assert wps.record_count >= 1, "استُبعد موظفٌ بلا داعٍ"
        assert not wps.excluded, "بقي الاستبعاد"


def test_missing_iban_names_its_owners(env, client):
    """
    ⚠️⚠️ **والآيبان وحده يمنع** (قرار جواد ق-179): فصفٌّ بلا
    آيبان **لا يُنفَّذ**.

    ⚠️ **والرسالة تُسمّي العدد والأسماء**: فـ«يحوي أخطاء» **لا
    يقول لمن يعود**.
    """
    with account_scope(env["account_id"]):
        env["emp"].iban = ""
        env["emp"].save(update_fields=["iban"])
        for slip in env["run"].payslips.all():
            slip.iban = ""
            slip.save(update_fields=["iban"])

    client.force_login(env["user"])
    res = client.get(
        f"/api/payroll/runs/{env['run'].id}/wps/download/")
    assert res.status_code == 409, res.status_code
    body = res.json()
    assert body.get("code") == "missing_iban", body
    # ⚠️ **والاسم في الرسالة** — فمن يقرأ يعرف لمن يعود
    assert "E-1" in body["detail"], body["detail"]


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


# ══════════ القراءة الحيّة (ق-179) ══════════

def test_iban_is_read_live_not_frozen(env, client):
    """
    ⚠️⚠️ **والآيبان يُقرأ من الملفّ حيًّا** (قرار جواد): فهو
    **بيانٌ ناقصٌ يُستكمَل** — لا مبلغٌ احتُسب.

    **فمن أُضيف آيبانه بعد الاعتماد يُصدَّر به** — ولا يُعاد حساب
    المسير.
    """
    from apps.payroll.services.outputs.wps import build_wps_file

    with account_scope(env["account_id"]):
        # القسيمة بلا آيبان، والملفّ به
        for slip in env["run"].payslips.all():
            slip.iban = ""
            slip.include_in_wps = True
            slip.save(update_fields=["iban", "include_in_wps"])
        env["emp"].iban = "SA0380000000608010167519"
        env["emp"].save(update_fields=["iban"])

        wps = build_wps_file(env["run"])
        assert not wps.errors, wps.errors
        assert wps.record_count >= 1
        assert wps.rows[0].iban.startswith("SA03")


def test_amounts_stay_frozen(env):
    """
    ⚠️ **والمبالغ تبقى من القسيمة**: فما اعتُمد دُفع — **وتغييرُ
    الراتب بعده لا يُغيّر ما صُرف**.

    والفرق بأثرٍ رجعيّ **يدخل المسير التالي** (ق-١٥٨).
    """
    from decimal import Decimal

    from apps.payroll.services.outputs.wps import build_wps_file

    with account_scope(env["account_id"]):
        for slip in env["run"].payslips.all():
            slip.iban = "SA0380000000608010167519"
            slip.include_in_wps = True
            slip.save(update_fields=["iban", "include_in_wps"])

        wps = build_wps_file(env["run"])
        before = wps.total_net

        # ⚠️ **نغيّر بنود الراتب على الملفّ** — والمسير لا يتأثّر
        from apps.employees.models import SalaryLine

        SalaryLine.objects.filter(
            structure__employment=env["emp"]).update(
            amount=Decimal("99999"))

        after = build_wps_file(env["run"]).total_net
        assert after == before, "تغيّر المبلغ بعد الاعتماد"
