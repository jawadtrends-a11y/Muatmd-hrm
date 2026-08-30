"""حرّاس ملف الموظف: الشخص، الارتباط، وهيكل الراتب."""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models import Employment, EmploymentStatus, Person, SalaryChangeReason
from apps.employees.services.duplicates import check_person_duplicates
from apps.employees.services.hiring import (
    DuplicatePersonError, HiringError, create_employment, create_person,
    current_salary_structure, gosi_borne_by_company, set_salary_structure,
)
from apps.employees.services.validators import (
    normalize_mobile, validate_saudi_iban, validate_saudi_id,
)
from apps.payroll.models import PayComponent, PayrollSettings
from apps.payroll.services.components import (
    eosb_wage, gosi_subject_wage, overtime_base_wage, provision_default_components,
)

VALID_IBAN = "SA0380000000608010167519"


@pytest.fixture
def ctx(db):
    r = provision_account(slug="emp-test", display_name_ar="حساب موظفين",
                          company_name_ar="شركة أولى", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        c1 = Company.objects.get(id=r.company_id)
        c2 = Company.objects.create(account=acc, code="C2",
                                    legal_name_ar="شركة ثانية")
        provision_default_components(c2)
        PayrollSettings.objects.get_or_create(company=c2,
                                              defaults={"account": acc})
        comps = {c.code: c for c in PayComponent.objects.filter(company=c1)}
        yield {"account": acc, "c1": c1, "c2": c2, "comps": comps,
               "account_id": r.account_id}


def _person(ctx, **kw):
    defaults = dict(
        account=ctx["account"], first_name_ar="محمد", family_name_ar="السالم",
        gender="male", nationality_code="SA", id_type="national_id",
        id_number="1012345678", mobile="0501234567")
    defaults.update(kw)
    p, _ = create_person(**defaults)
    return p


# ══════════ التحقق من البيانات ══════════

def test_valid_saudi_iban():
    ok, err = validate_saudi_iban(VALID_IBAN)
    assert ok and not err


@pytest.mark.parametrize("bad", [
    "", "SA123", "SA0000000000000000000000", "GB29NWBK60161331926819",
])
def test_invalid_ibans_rejected(bad):
    ok, _ = validate_saudi_iban(bad)
    assert not ok


def test_national_id_starts_with_one():
    assert validate_saudi_id("1012345678", "national_id")[0]
    assert not validate_saudi_id("2012345678", "national_id")[0]


def test_iqama_starts_with_two():
    assert validate_saudi_id("2012345678", "iqama")[0]
    assert not validate_saudi_id("1012345678", "iqama")[0]


@pytest.mark.parametrize("raw,expected", [
    ("0501234567", "+966501234567"),
    ("501234567", "+966501234567"),
    ("+966501234567", "+966501234567"),
    ("00966501234567", "+966501234567"),
    ("05 0123 4567", "+966501234567"),
])
def test_mobile_normalized_to_e164(raw, expected):
    """الجوال مفتاح واتساب — التوحيد يمنع ازدواج الشخص."""
    assert normalize_mobile(raw)[0] == expected


# ══════════ كشف التشابه (ق-5) ══════════

@pytest.mark.django_db(transaction=True)
def test_duplicate_id_blocks(ctx):
    with account_scope(ctx["account_id"]):
        _person(ctx)
        with pytest.raises(DuplicatePersonError):
            _person(ctx, first_name_ar="خالد", family_name_ar="العتيبي",
                    mobile="0509999999")


@pytest.mark.django_db(transaction=True)
def test_duplicate_mobile_blocks(ctx):
    """الجوال منع صارم — ازدواجه يوصل القسيمة للشخص الخطأ."""
    with account_scope(ctx["account_id"]):
        _person(ctx)
        with pytest.raises(DuplicatePersonError):
            _person(ctx, id_number="1099999999", first_name_ar="خالد")


@pytest.mark.django_db(transaction=True)
def test_same_name_different_id_allowed_with_force(ctx):
    """ق-5: الاسم تحذير لا منع — شخصان قد يحملان نفس الاسم."""
    with account_scope(ctx["account_id"]):
        _person(ctx)
        with pytest.raises(HiringError):     # تحذير بلا force
            _person(ctx, id_number="1099999999", mobile="0509999999")
        p2 = _person(ctx, id_number="1099999999", mobile="0509999999",
                     force=True)
        assert p2.id_number == "1099999999"


# ══════════ الشخص والارتباط (ق-4) ══════════

@pytest.mark.django_db(transaction=True)
def test_person_can_work_in_two_companies(ctx):
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        create_employment(person=p, company=ctx["c1"], employee_no="E1",
                          join_date=date(2019, 1, 1))
        create_employment(person=p, company=ctx["c2"], employee_no="X9",
                          join_date=date(2023, 6, 1),
                          employment_type="secondary")
        assert p.employments.count() == 2


@pytest.mark.django_db(transaction=True)
def test_duplicate_employee_no_per_company_blocked(ctx):
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        create_employment(person=p, company=ctx["c1"], employee_no="E1",
                          join_date=date(2019, 1, 1))
        p2 = _person(ctx, id_number="1099999999", mobile="0509999999",
                     force=True)
        with pytest.raises(HiringError):
            create_employment(person=p2, company=ctx["c1"], employee_no="E1",
                              join_date=date(2020, 1, 1))


@pytest.mark.django_db(transaction=True)
def test_two_active_employments_same_company_blocked(ctx):
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        create_employment(person=p, company=ctx["c1"], employee_no="E1",
                          join_date=date(2019, 1, 1))
        with pytest.raises(HiringError):
            create_employment(person=p, company=ctx["c1"], employee_no="E2",
                              join_date=date(2020, 1, 1))


@pytest.mark.django_db(transaction=True)
def test_registration_flags_start_false(ctx):
    """ق-15: التوظيف مستقل عن التسجيل النظامي."""
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        e, _, _ = create_employment(person=p, company=ctx["c1"],
                                    employee_no="E1",
                                    join_date=date(2019, 1, 1))
        assert not e.is_gosi_registered
        assert not e.is_mol_registered
        assert not e.include_in_wps
        assert not e.counts_in_nitaqat, "غير مسجّل بقوى يُحتسب في نطاقات"


@pytest.mark.django_db(transaction=True)
def test_nitaqat_counts_only_mol_registered(ctx):
    """ق-15: سعودي غير مسجّل لا يرفع نسبة التوطين."""
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        e, _, _ = create_employment(person=p, company=ctx["c1"],
                                    employee_no="E1",
                                    join_date=date(2019, 1, 1))
        e.is_mol_registered = True
        e.save()
        assert e.counts_in_nitaqat


@pytest.mark.django_db(transaction=True)
def test_gosi_scheme_lives_on_person(ctx):
    """ق-16: النظام التأميني صفة في الفرد لا الوظيفة."""
    with account_scope(ctx["account_id"]):
        p = _person(ctx, gosi_scheme_code="traditional")
        assert not hasattr(Employment, "gosi_scheme_code") or True
        assert p.gosi_scheme_code == "traditional"
        assert "gosi_scheme_code" not in [
            f.name for f in Employment._meta.fields]


# ══════════ هيكل الراتب التاريخي ══════════

@pytest.mark.django_db(transaction=True)
def test_salary_history_never_edited_in_place(ctx):
    """القاعدة الذهبية: كل تغيير سجل جديد بتاريخ سريان."""
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        comps = ctx["comps"]
        e, st1, _ = create_employment(
            person=p, company=ctx["c1"], employee_no="E1",
            join_date=date(2019, 1, 1),
            salary_lines=[(comps["BASIC"], D("8000")),
                          (comps["HOUSING"], D("2000"))])
        set_salary_structure(
            employment=e, effective_from=date(2024, 1, 1),
            reason=SalaryChangeReason.ANNUAL_RAISE,
            lines=[(comps["BASIC"], D("9000")),
                   (comps["HOUSING"], D("2250"))])

        st1.refresh_from_db()
        assert st1.effective_to == date(2023, 12, 31), "الهيكل السابق لم يُغلق"
        assert current_salary_structure(e, date(2020, 6, 1)).gross_monthly == D("10000")
        assert current_salary_structure(e, date(2025, 6, 1)).gross_monthly == D("11250")


@pytest.mark.django_db(transaction=True)
def test_backdated_structure_rejected(ctx):
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        comps = ctx["comps"]
        e, _, _ = create_employment(
            person=p, company=ctx["c1"], employee_no="E1",
            join_date=date(2020, 1, 1),
            salary_lines=[(comps["BASIC"], D("8000"))])
        with pytest.raises(HiringError):
            set_salary_structure(employment=e, effective_from=date(2019, 1, 1),
                                 lines=[(comps["BASIC"], D("9000"))])


@pytest.mark.django_db(transaction=True)
def test_derived_wages_from_flags(ctx):
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        comps = ctx["comps"]
        _, st, _ = create_employment(
            person=p, company=ctx["c1"], employee_no="E1",
            join_date=date(2019, 1, 1),
            salary_lines=[(comps["BASIC"], D("8000")),
                          (comps["HOUSING"], D("2000")),
                          (comps["TRANSPORT"], D("1000"))])
        lines = st.as_lines()
        assert st.gross_monthly == D("11000")
        assert gosi_subject_wage(lines) == D("10000")
        assert overtime_base_wage(lines) == D("8000")
        assert eosb_wage(lines, "flagged") == D("8000")


# ══════════ تحمّل التأمينات (ق-29) ══════════

@pytest.mark.django_db(transaction=True)
def test_employee_override_beats_company_setting(ctx):
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        e, _, _ = create_employment(person=p, company=ctx["c1"],
                                    employee_no="E1",
                                    join_date=date(2019, 1, 1))
        s = PayrollSettings.objects.get(company=ctx["c1"])
        assert gosi_borne_by_company(e, s) is False

        e.gosi_borne_by_company = True
        e.save()
        assert gosi_borne_by_company(e, s) is True

        s.company_bears_employee_gosi = True
        e.gosi_borne_by_company = False
        e.save()
        assert gosi_borne_by_company(e, s) is False, "الاستثناء لم يسبق الإعداد"


# ══════════ العزل ══════════

@pytest.mark.django_db(transaction=True)
def test_employees_isolated_between_accounts(ctx, rls_enforced_late):
    other = provision_account(slug="emp-other", display_name_ar="آخر",
                              company_name_ar="شركة أخرى", is_sandbox=True)
    with account_scope(ctx["account_id"]):
        p = _person(ctx)
        create_employment(person=p, company=ctx["c1"], employee_no="E1",
                          join_date=date(2019, 1, 1))

    rls_enforced_late()
    with account_scope(other.account_id):
        assert Person.objects.count() == 0
        assert Employment.objects.count() == 0
