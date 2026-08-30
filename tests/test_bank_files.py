"""
حرّاس ملفات البنوك وحماية الأجور.

أهمها test_ncb_output_matches_reference — يقارن ناتج النظام بملف
مرجعي مستخرج من تصدير بنك فعلي. أي تغيير في ترتيب الأعمدة أو
تنسيق الأرقام أو نهايات الأسطر يفشل البناء.
"""
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.organization.services.structure import create_department
from apps.payroll.models import (
    BankTemplate, PayComponent, PayrollRunStatus, PayrollRunType,
)
from apps.payroll.services.engine import (
    approve_run, calculate_run, create_run, submit_run,
)
from apps.payroll.services.gosi_seed import sync_gosi_rates
from apps.payroll.services.outputs.bank_file import (
    BankFileError, build_bank_file, swift_from_iban,
)
from apps.payroll.services.outputs.wps import (
    WPSError, build_wps_file, to_csv, validation_report,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ncb_expected.csv"
IBAN = "SA6080000247608010330101"


@pytest.fixture
def env(db):
    sync_gosi_rates()
    r = provision_account(slug="bnk-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}
        dept = create_department(company=comp, code="ADM", name_ar="الإدارة")
        dept.name_en = "Administration"
        dept.save()

        p, _ = create_person(
            account=acc, first_name_ar="موظف", family_name_ar="تجريبي",
            full_name_en="TEST EMPLOYEE ONE", gender="male",
            nationality_code="PK", id_type="iqama",
            id_number="2154967927", mobile="0504445556")
        e, _, _ = create_employment(
            person=p, company=comp, employee_no="118",
            join_date=date(2020, 1, 1), department=dept, iban=IBAN,
            salary_lines=[(comps["BASIC"], D("2497")),
                          (comps["HOUSING"], D("633")),
                          (comps["TRANSPORT"], D("257"))])
        e.include_in_wps = True
        e.save()
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": e, "person": p, "comps": comps, "dept": dept}


def _approved_run(env, month=8):
    run = create_run(company=env["comp"], run_type=PayrollRunType.REGULAR,
                     year=2026, month=month)
    calculate_run(run)
    run.refresh_from_db()
    submit_run(run)
    run.refresh_from_db()
    approve_run(run, env["person"])
    run.refresh_from_db()
    run.payment_date = date(2026, 8, 22)
    run.save()
    return run


# ══════════ المطابقة المرجعية ══════════

@pytest.mark.django_db(transaction=True)
def test_ncb_output_matches_reference(env):
    """
    الناتج يطابق ملف تصدير بنك فعلي حرفًا بحرف.

    ⚠️ فشل هذا الاختبار يعني أن الملف قد يُرفض من البنك — راجع
    التغيير قبل النشر.
    """
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        res = build_bank_file(run, tpl)

        expected = FIXTURE.read_text(encoding="utf-8").strip().splitlines()
        actual = res.content.replace("\r\n", "\n").strip().splitlines()
        assert actual == expected, "الناتج لا يطابق ملف البنك المرجعي"


@pytest.mark.django_db(transaction=True)
def test_ncb_filename_pattern(env):
    """اسم الملف كما يتوقعه البنك: NCB_For_DD-MM-YYYY.csv"""
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        assert build_bank_file(run, tpl).filename == "NCB_For_22-08-2026.csv"


@pytest.mark.django_db(transaction=True)
def test_line_endings_are_crlf(env):
    """البنوك ترفض نهايات يونكس أحيانًا."""
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        assert "\r\n" in build_bank_file(run, tpl).content


@pytest.mark.django_db(transaction=True)
def test_total_salary_is_net_not_gross(env):
    """
    مؤكد من ملف فعلي: Total Salary = الأساسي + السكن + أخرى − الخصومات.
    """
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        row = build_bank_file(run, tpl).content.strip().splitlines()[1]
        cells = row.split(",")
        total = D(cells[2])
        basic, housing, other, ded = (D(cells[7]), D(cells[8]),
                                      D(cells[9]), D(cells[10]))
        assert total == basic + housing + other - ded


# ══════════ رموز البنوك ══════════

@pytest.mark.parametrize("iban_prefix,swift", [
    ("SA10", "NCBK"), ("SA15", "ALBI"), ("SA20", "RIBL"),
    ("SA45", "SABB"), ("SA60", "BJAZ"), ("SA80", "RJHI"),
])
def test_swift_from_iban(iban_prefix, swift):
    """الخريطة مؤكدة من ملف بنك فعلي."""
    iban = iban_prefix[:2] + "60" + iban_prefix[2:] + "0" * 18
    assert swift_from_iban(iban) == swift


def test_unknown_iban_prefix_returns_empty():
    assert swift_from_iban("SA6099000000000000000000") == ""


# ══════════ الاستبعادات ══════════

@pytest.mark.django_db(transaction=True)
def test_zero_net_excluded_with_reason(env):
    """الاستبعاد الصامت ممنوع — كل مستبعَد يُسجَّل بسببه."""
    with account_scope(env["account_id"]):
        from apps.attendance.models import AttendanceMonthlySummary
        AttendanceMonthlySummary.objects.create(
            account=env["acc"], company=env["comp"], employment=env["emp"],
            period_year=2026, period_month=8, unpaid_absent_days=D("40"))
        run = _approved_run(env)
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        res = build_bank_file(run, tpl)
        assert res.row_count == 0
        assert len(res.excluded) == 1
        assert "صافي صفري" in res.excluded[0]["reason"]


@pytest.mark.django_db(transaction=True)
def test_cash_payment_excluded(env):
    with account_scope(env["account_id"]):
        env["emp"].payment_method = "cash"
        env["emp"].save()
        run = _approved_run(env)
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        res = build_bank_file(run, tpl)
        assert res.row_count == 0
        assert "نقدًا" in res.excluded[0]["reason"]


@pytest.mark.django_db(transaction=True)
def test_invalid_iban_is_error_not_silent_skip(env):
    """الآيبان الخاطئ خطأ يمنع الإرسال — لا استبعاد صامت."""
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        for slip in run.payslips.all():
            slip.iban = "SA0000000000000000000000"
            slip.save()
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        res = build_bank_file(run, tpl)
        assert len(res.errors) == 1
        assert res.ready is False


# ══════════ حماية الاعتماد ══════════

@pytest.mark.django_db(transaction=True)
def test_unapproved_run_cannot_export(env):
    """لا تصدير قبل الاعتماد — سجل مالي نهائي."""
    with account_scope(env["account_id"]):
        run = create_run(company=env["comp"],
                         run_type=PayrollRunType.REGULAR, year=2026, month=9)
        calculate_run(run)
        run.refresh_from_db()
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        with pytest.raises(BankFileError):
            build_bank_file(run, tpl)
        with pytest.raises(WPSError):
            build_wps_file(run)


# ══════════ ملف حماية الأجور ══════════

@pytest.mark.django_db(transaction=True)
def test_wps_file_built(env):
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        wps = build_wps_file(run)
        assert wps.record_count == 1
        assert wps.total_net == D("3387.00")


@pytest.mark.django_db(transaction=True)
def test_wps_validation_report(env):
    """تقرير ما قبل الإرسال — يعرض من خرج ولماذا."""
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        report = validation_report(build_wps_file(run))
        assert report["ready"] is True
        assert report["record_count"] == 1
        assert report["error_count"] == 0


@pytest.mark.django_db(transaction=True)
def test_wps_csv_has_two_decimals(env):
    with account_scope(env["account_id"]):
        run = _approved_run(env)
        csv_text = to_csv(build_wps_file(run))
        row = csv_text.strip().splitlines()[1]
        assert row.split(",")[-1] == "3387.00"


# ══════════ القوالب ══════════

@pytest.mark.django_db(transaction=True)
def test_builtin_template_provisioned(env):
    with account_scope(env["account_id"]):
        tpl = BankTemplate.objects.get(company=env["comp"], code="NCB")
        assert tpl.is_builtin is True
        assert tpl.columns.count() == 11
        assert tpl.line_ending == "crlf"


@pytest.mark.django_db(transaction=True)
def test_company_can_create_own_template(env):
    """ق-9: بنك بلا قالب جاهز — الشركة تبنيه."""
    from apps.payroll.models import BankColumn, BankColumnSource
    with account_scope(env["account_id"]):
        tpl = BankTemplate.objects.create(
            account=env["acc"], company=env["comp"], code="CUSTOM",
            name_ar="قالب مخصص", bank_name_ar="بنك آخر",
            filename_pattern="CUSTOM_{period}.csv", include_header=False)
        BankColumn.objects.create(template=tpl, position=1, header="IBAN",
                                  source=BankColumnSource.IBAN)
        BankColumn.objects.create(template=tpl, position=2, header="AMOUNT",
                                  source=BankColumnSource.NET_PAY,
                                  number_format="0.00")
        run = _approved_run(env)
        res = build_bank_file(run, tpl)
        assert res.content.strip() == f"{IBAN},3387.00"
        assert res.filename == "CUSTOM_202608.csv"


@pytest.mark.django_db(transaction=True)
def test_empty_template_rejected(env):
    with account_scope(env["account_id"]):
        tpl = BankTemplate.objects.create(
            account=env["acc"], company=env["comp"], code="EMPTY",
            name_ar="فارغ", bank_name_ar="بنك")
        run = _approved_run(env)
        with pytest.raises(BankFileError):
            build_bank_file(run, tpl)
