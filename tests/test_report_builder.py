"""
حرّاس باني التقارير المخصّصة (ق-126).

⚠️ **التقرير المخصّص لا يفتح ما يغلقه النظام**: يمرّ بالبوابة
والعزل كأي تقرير، ومن نطاقه إدارته لا يرى غيرها ولو اختار حقولها.
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
from apps.core.models import CustomReport
from apps.core.reports.base import ReportError
from apps.core.reports.builder import available_fields, run_custom_report
from apps.core.reports.builder_fields import FIELDS_BY_SOURCE
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="rb-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        def hire(first, nid, mob, no, role_code, scope):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar="القحطاني",
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=TODAY - timedelta(days=300),
                salary_lines=[(basic, Decimal("7000"))])
            u = User.objects.create_user(username=f"rb.{no}", password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, employment=e,
                role=Role.objects.get(account=acc, code=role_code),
                company=comp, scope=scope)
            return u, e

        hr, _ = hire("ماجد", "1011122234", "0501112223", "RB-1",
                     "hr_manager", Scope.COMPANY.value)
        emp_u, emp_e = hire("سالم", "1022233345", "0502223334", "RB-2",
                            "employee", Scope.OWN.value)

        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "hr": hr, "emp_user": emp_u, "emp": emp_e}


def _report(env, source, fields, **kw):
    return CustomReport(
        account=env["acc"], company=env["comp"], name_ar="تجربة",
        source=source, fields=fields, **kw)


def test_builder_returns_chosen_columns(env):
    """التقرير يُرجع ما اختاره — بترتيبه."""
    with account_scope(env["account_id"]):
        r = _report(env, "employees",
                    ["employee_no", "name_ar", "join_date"])
        cols, rows = run_custom_report(
            report=r, user=env["hr"], company=env["comp"])
        assert [c.key for c in cols] == ["employee_no", "name_ar",
                                         "join_date"]
        assert len(rows) == 2


def test_scope_limits_rows(env):
    """
    ⚠️ الأهمّ: **النطاق يحدّ الصفوف**.

    فمن نطاقه نفسه يرى نفسه وحده — ولو اختار كل الحقول.
    """
    with account_scope(env["account_id"]):
        r = _report(env, "employees", ["employee_no", "name_ar"])
        _, mine = run_custom_report(
            report=r, user=env["emp_user"], company=env["comp"])
        _, all_rows = run_custom_report(
            report=r, user=env["hr"], company=env["comp"])
        assert len(mine) == 1, f"رأى {len(mine)} صفًّا وهو بنطاق own"
        assert len(all_rows) == 2


def test_payroll_fields_need_payroll_permission(env):
    """
    ⚠️ وحقول الرواتب **تُصفّى بالصلاحية** لا بالإخفاء.

    فتقريرٌ يُشارَك بين موظفين نطاقاتهم مختلفة: من لا يملك
    `payroll.view` لا يرى عمود الراتب ولو كان محفوظًا فيه.
    """
    with account_scope(env["account_id"]):
        fields = available_fields("payroll", env["emp_user"])
        assert fields == [], "موظفٌ عاديّ رأى حقول الرواتب"

        r = _report(env, "payroll", ["net", "gross"])
        with pytest.raises(Exception):
            run_custom_report(report=r, user=env["emp_user"],
                              company=env["comp"])

        # ⚠️ والترشيح يقع على **الحقول** لا على المصدر وحده:
        # تقريرُ موظفين فيه عمود راتبٍ يُسقط العمود ولا يُسقط
        # التقرير — فالمشارَك بين نطاقين يعمل لكلٍّ بما يستحقّ.
        mixed = _report(env, "employees",
                        ["employee_no", "name_ar", "iban"])
        cols, _ = run_custom_report(
            report=mixed, user=env["emp_user"], company=env["comp"])
        assert "iban" not in [c.key for c in cols], (
            "رأى حقلًا يحتاج صلاحية الرواتب")


def test_unknown_field_is_ignored_not_crashing(env):
    """وحقلٌ حُذف من الكتالوج يُتخطّى — فالتقرير القديم لا ينكسر."""
    with account_scope(env["account_id"]):
        r = _report(env, "employees",
                    ["employee_no", "field_that_was_removed", "name_ar"])
        cols, _ = run_custom_report(
            report=r, user=env["hr"], company=env["comp"])
        assert [c.key for c in cols] == ["employee_no", "name_ar"]


def test_no_usable_field_is_refused(env):
    """ومن لا حقل له فيه يُردّ برسالةٍ لا بتقريرٍ فارغ."""
    with account_scope(env["account_id"]):
        r = _report(env, "employees", ["nothing_at_all"])
        with pytest.raises(ReportError):
            run_custom_report(report=r, user=env["hr"],
                              company=env["comp"])


def test_all_declared_paths_resolve(env):
    """
    ⚠️ **كل مسارٍ معلَن يعمل** — فمسارٌ خاطئ يسقط التقرير عند
    التشغيل لا عند الكتابة.
    """
    from apps.attendance.models import AttendanceDay
    from apps.employees.models import Employment
    from apps.leaves.models import Request
    from apps.payroll.models import Payslip

    models = {"employees": Employment, "attendance": AttendanceDay,
              "requests": Request, "payroll": Payslip}
    for source, fields in FIELDS_BY_SOURCE.items():
        model = models[source]
        for f in fields:
            list(model.objects.values(f.path)[:1])


def test_row_cap_is_enforced(env):
    """وسقف الصفوف مفروض — فتقريرٌ بلا حدّ يُسقط الخادم."""
    import inspect

    from apps.core.reports import builder

    src = inspect.getsource(builder.run_custom_report)
    assert "[:5000]" in src, "سقف الصفوف نُزع"
