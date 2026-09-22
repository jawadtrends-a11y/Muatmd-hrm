"""
حرّاس القيد المحاسبيّ (ق-152).

⚠️⚠️ **ولا يُصدَّر قيدٌ غير متوازن** — فمدينٌ لا يساوي دائنًا
يُرفض في أيّ نظام، **وتصديرُه يُضيّع وقت المحاسب في البحث عن
خطئنا**.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    GLAccountMap, GLGrouping, GLTemplate, PayComponent,
    PayrollRunStatus, PayrollRunType, PayslipLine)
from apps.payroll.services import engine
from apps.payroll.services.outputs import gl_export as gl


@pytest.fixture
def env(db):
    r = provision_account(slug="gl-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        # ق-235: الحضور هنا يُدخَل يدويًّا — فأرقامها المرجعية بلا غياب
        from apps.payroll.models import PayrollSettings as _PS
        _PS.objects.filter(company_id=r.company_id).update(auto_attendance=False)
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        for i, (fn, ln, nid, mob) in enumerate((
                ("فهد", "المطيري", "1012233344", "0501223334"),
                ("نورة", "العتيبي", "1023344455", "0502334445"))):
            p, _ = create_person(
                account=acc, first_name_ar=fn, family_name_ar=ln,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            create_employment(
                person=p, company=comp, employee_no=f"G-{i}",
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("10000"))])

        run = engine.create_run(company=comp,
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        run.status = PayrollRunStatus.SUBMITTED
        run.save(update_fields=["status"])
        engine.approve_run(run, None)

        tpl = GLTemplate.objects.create(
            account=acc, company=comp, code="GEN",
            name_ar="عامّ", grouping=GLGrouping.COMPANY,
            columns=gl.default_columns())

        yield {"account_id": r.account_id, "comp": comp, "run": run,
               "tpl": tpl}


def _map_all(env, debit="5199", credit="2101"):
    codes = set(PayslipLine.objects.filter(
        payslip__run=env["run"]).values_list("component_code",
                                             flat=True))
    for c in codes:
        GLAccountMap.objects.get_or_create(
            company=env["comp"], component_code=c,
            defaults={"account_id": env["account_id"], "name_ar": c,
                      "debit_account": debit,
                      "credit_account": credit})
    GLAccountMap.objects.get_or_create(
        company=env["comp"], component_code="NET_PAYABLE",
        defaults={"account_id": env["account_id"],
                  "name_ar": "رواتب مستحقّة",
                  "debit_account": credit, "credit_account": credit})


def test_unmapped_components_block_export(env):
    """
    ⚠️ **وبندٌ بلا ربطٍ يمنع التصدير**: فقيدٌ ناقصٌ أسوأ من قيدٍ
    لا يُصدَّر — والمحاسب يكتشفه بعد الترحيل.
    """
    with account_scope(env["account_id"]):
        e = gl.build_entry(env["run"], env["tpl"])
        assert e.unmapped, "مرّ قيدٌ ببنودٍ غير مربوطة"
        assert e.ready is False
        with pytest.raises(gl.GLError):
            gl.to_csv(e, env["tpl"])


def test_missing_payable_is_an_error(env):
    """
    ⚠️⚠️ **وبلا الطرف الدائن نصفُ قيد**: فالمصروف بلا التزامٍ
    مقابل لا يتوازن.
    """
    with account_scope(env["account_id"]):
        codes = set(PayslipLine.objects.filter(
            payslip__run=env["run"]).values_list("component_code",
                                                 flat=True))
        for c in codes:
            GLAccountMap.objects.create(
                account_id=env["account_id"], company=env["comp"],
                component_code=c, name_ar=c,
                debit_account="5199", credit_account="2101")

        e = gl.build_entry(env["run"], env["tpl"])
        assert e.errors, "مرّ قيدٌ بلا طرفٍ دائن"
        assert "NET_PAYABLE" in e.errors[0]


def test_balanced_entry_is_ready(env):
    """
    ⚠️⚠️ الأهمّ: **والمتوازن وحده يُصدَّر**.
    """
    with account_scope(env["account_id"]):
        _map_all(env)
        e = gl.build_entry(env["run"], env["tpl"])
        assert not e.unmapped, e.unmapped
        assert not e.errors, e.errors
        assert e.is_balanced is True, (e.total_debit, e.total_credit)
        assert e.ready is True
        assert e.total_debit == e.total_credit


def test_unbalanced_is_refused(env):
    """وغير المتوازن يُرفض ولا يُكتب."""
    with account_scope(env["account_id"]):
        _map_all(env)
        e = gl.build_entry(env["run"], env["tpl"])
        # نكسر التوازن يدويًّا
        e.lines.append(gl.GLLine(account="9999",
                                 debit=Decimal("100")))
        assert e.is_balanced is False
        assert e.ready is False
        with pytest.raises(gl.GLError):
            gl.to_csv(e, env["tpl"])


def test_unapproved_run_has_no_entry(env):
    """
    ⚠️ **والمسير غير المعتمد لا قيدَ له**: فأرقامٌ غير نهائية
    تُرحَّل خطأً.
    """
    with account_scope(env["account_id"]):
        env["run"].status = PayrollRunStatus.CALCULATED
        env["run"].save(update_fields=["status"])
        with pytest.raises(gl.GLError) as e:
            gl.build_entry(env["run"], env["tpl"])
        assert "الاعتماد" in str(e.value)


def test_excluded_component_is_skipped(env):
    """
    **والمستثنى يُتخطّى بلا خطأ** — كتكلفةٍ تُرحَّل بقيدٍ آخر.
    """
    with account_scope(env["account_id"]):
        _map_all(env)
        m = GLAccountMap.objects.filter(
            company=env["comp"], component_code="BASIC").first()
        m.is_excluded = True
        m.save(update_fields=["is_excluded"])

        e = gl.build_entry(env["run"], env["tpl"])
        codes = {l.component_code for l in e.lines}
        assert "BASIC" not in codes
        assert not e.unmapped, "عُدّ المستثنى غير مربوط"


def test_employee_grouping_makes_more_lines(env):
    """
    ⚠️ **والتجميع بالموظف أدقّ وأثقل**: فسطرٌ لكل موظفٍ في كل بند.
    """
    with account_scope(env["account_id"]):
        _map_all(env)

        env["tpl"].grouping = GLGrouping.COMPANY
        env["tpl"].save(update_fields=["grouping"])
        company_lines = len(gl.build_entry(env["run"],
                                           env["tpl"]).lines)

        env["tpl"].grouping = GLGrouping.EMPLOYEE
        env["tpl"].save(update_fields=["grouping"])
        emp_entry = gl.build_entry(env["run"], env["tpl"])

        assert len(emp_entry.lines) > company_lines
        assert emp_entry.is_balanced is True, (
            "اختلّ التوازن بتغيّر التجميع")
        assert any(l.employee_no for l in emp_entry.lines)


def test_csv_follows_template_columns(env):
    """والملفّ يتبع أعمدة القالب — فلكل نظامٍ ترتيبُه."""
    with account_scope(env["account_id"]):
        _map_all(env)
        env["tpl"].columns = [
            {"field": "account", "header": "الحساب"},
            {"field": "debit", "header": "مدين"},
            {"field": "credit", "header": "دائن"},
        ]
        env["tpl"].save(update_fields=["columns"])

        text = gl.to_csv(gl.build_entry(env["run"], env["tpl"]),
                         env["tpl"])
        head = text.strip().split("\n")[0]
        assert head.startswith("الحساب"), head
        assert head.count(",") == 2, head


def test_totals_match_the_run(env):
    """
    ⚠️ **والدائن يساوي صافي المسير** — فقيدٌ لا يطابقه خطأ.
    """
    with account_scope(env["account_id"]):
        _map_all(env)
        e = gl.build_entry(env["run"], env["tpl"])
        payable = sum((l.credit for l in e.lines
                       if l.component_code == "NET_PAYABLE"),
                      Decimal("0"))
        assert payable == env["run"].total_net, (
            payable, env["run"].total_net)
