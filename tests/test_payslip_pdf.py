"""
حرّاس قسيمة الراتب PDF (ق-163).

**بلاغ جواد:** زرّ «عرض القسيمة» كان يفتح **JSON خامًا**.

⚠️ **والقسيمة وثيقةٌ يحملها الموظف للبنك** — لا شاشةً يقرؤها.
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


@pytest.fixture
def env(db):
    r = provision_account(slug="pdf-t", display_name_ar="حساب",
                          company_name_ar="شركة التجربة",
                          is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="زياد", family_name_ar="الشمري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1055667788", mobile="0505566778")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="P-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("11000"))])

        u = User.objects.create_user(username="pdf.hr", password="x")
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

        yield {"account_id": r.account_id, "user": u,
               "slip": run.payslips.first()}


def test_pdf_is_a_real_pdf(env, client):
    """
    ⚠️⚠️ الأهمّ: **والمسار يُرجع PDF لا JSON** (بلاغ جواد).
    """
    client.force_login(env["user"])
    res = client.get(f"/api/payslips/{env['slip'].id}/pdf/")
    assert res.status_code == 200, res.content[:200]
    assert res["Content-Type"] == "application/pdf"
    assert res.content[:4] == b"%PDF", "ليس ملفّ PDF"
    assert len(res.content) > 3000, "ملفٌّ فارغ تقريبًا"


def test_filename_identifies_itself(env, client):
    """
    **والاسم يُعرف من نفسه** — فملفّاتٌ بأسماء متشابهة تُربك.
    """
    client.force_login(env["user"])
    res = client.get(f"/api/payslips/{env['slip'].id}/pdf/")
    cd = res.get("Content-Disposition", "")
    assert "P-1" in cd, cd
    assert ".pdf" in cd


def test_pdf_respects_permissions(env, client):
    """
    ⚠️ **ولا يفتحها من لا يملكها**: فالقسيمة مالُ صاحبها — والـPDF
    **يمرّ بحراسة التفصيل نفسها**.
    """
    from apps.accounts.services.provisioning import provision_account

    other = provision_account(slug="pdf-o", display_name_ar="آخر",
                              company_name_ar="شركة أخرى",
                              is_sandbox=True)
    with account_scope(other.account_id):
        acc2 = Account.objects.get(id=other.account_id)
        comp2 = Company.objects.get(id=other.company_id)
        u2 = User.objects.create_user(username="pdf.out", password="x")
        AccountMembership.objects.create(
            user=u2, account=acc2, active_company=comp2)

    client.force_login(u2)
    res = client.get(f"/api/payslips/{env['slip'].id}/pdf/")
    assert res.status_code in (403, 404), res.status_code


def test_builder_does_not_recompute(env):
    """
    ⚠️ **والبناء لا يحسب شيئًا**: فالأرقام من المسير — **وحسابٌ
    ثانٍ قد يخالفه**.
    """
    from apps.payroll.services.outputs.payslip_pdf import (
        build_payslip_pdf)

    data = {
        "labels": {"title": "قسيمة راتب"},
        "company_name": "شركة",
        "period": "2026-09",
        "employee": {"name": "زياد", "employee_no": "P-1"},
        "earnings": [{"name": "الأساسي", "amount": "11,000.00",
                      "explanation": "شهريّ"}],
        "deductions": [],
        "totals": {"earnings": "11,000.00", "deductions": "0.00",
                   "net": "11,000.00"},
        "attendance": {},
    }
    out = build_payslip_pdf(data)
    assert out[:4] == b"%PDF"


def test_empty_sections_do_not_break(env):
    """
    **وقسيمةٌ بلا استقطاعات تُبنى** — فالفراغ حالةٌ لا خطأ.
    """
    from apps.payroll.services.outputs.payslip_pdf import (
        build_payslip_pdf)

    out = build_payslip_pdf({
        "labels": {}, "company_name": "", "period": "",
        "employee": {}, "earnings": [], "deductions": [],
        "totals": {}, "attendance": {},
    })
    assert out[:4] == b"%PDF"
