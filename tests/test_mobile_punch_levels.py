"""
حرّاس بصمة الجوال بمستوياتها الثلاثة (ق-96).

ما تمنعه:
  • قلب الأولوية — فالاستثناء الفردي هو الغرض من وجوده
  • خلط «يتبع الأعمّ» بـ«مسموح صراحةً»
  • فتح البصمة لمن أُقفلت عليه
"""
from datetime import date

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import Shift, ShiftAssignment
from apps.attendance.services.geofence import _mobile_punch_allowed
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayrollSettings


@pytest.fixture
def ctx(db):
    r = provision_account(slug="mp-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        p, _ = create_person(
            account=acc, first_name_ar="فهد", family_name_ar="الحربي",
            gender="male", nationality_code="SA",
            id_type="national_id", id_number="1055544433",
            mobile="0505554443")
        emp = create_employment(person=p, company=comp, employee_no="M1",
                                join_date=date(2023, 1, 1))
        if isinstance(emp, tuple):
            emp = emp[0]

        shift = Shift.objects.create(
            account=acc, company=comp, code="D1", name_ar="صباحية",
            start_time="08:00", end_time="16:00")

        st, _ = PayrollSettings.objects.get_or_create(
            account=acc, company=comp)

        yield {"emp": emp, "shift": shift, "settings": st,
               "account_id": r.account_id}


def _set(ctx, company=None, shift=None, emp=None, assign=False):
    with account_scope(ctx["account_id"]):
        ctx["settings"].allow_mobile_punch = company
        ctx["settings"].save(update_fields=["allow_mobile_punch"])

        ctx["shift"].allow_mobile_punch = shift
        ctx["shift"].save(update_fields=["allow_mobile_punch"])

        if assign:
            ShiftAssignment.objects.get_or_create(
                account_id=ctx["emp"].account_id,
                company_id=ctx["emp"].company_id,
                employment=ctx["emp"], shift=ctx["shift"],
                defaults={"effective_from": date(2023, 1, 1)})

        ctx["emp"].allow_mobile_punch = emp
        ctx["emp"].save(update_fields=["allow_mobile_punch"])


@pytest.mark.django_db(transaction=True)
def test_company_default_applies(ctx):
    """الشركة تقرّر حين لا يقرّر أحد دونها."""
    _set(ctx, company=True)
    assert _mobile_punch_allowed(ctx["emp"]) is True

    _set(ctx, company=False)
    assert _mobile_punch_allowed(ctx["emp"]) is False


@pytest.mark.django_db(transaction=True)
def test_employee_overrides_company(ctx):
    """
    ⚠️ الموظف يغلب الشركة.

    فمن فُتحت بصمته في ملفه يبصم ولو أُقفلت على الشركة كلها —
    والاستثناء الفردي هو الغرض من وجوده.
    """
    _set(ctx, company=False, emp=True)
    assert _mobile_punch_allowed(ctx["emp"]) is True

    _set(ctx, company=True, emp=False)
    assert _mobile_punch_allowed(ctx["emp"]) is False


@pytest.mark.django_db(transaction=True)
def test_shift_between_company_and_employee(ctx):
    """
    ⚠️ فترة العمل تغلب الشركة، والموظف يغلبها.

    فالترتيب: الموظف ← فترته ← شركته.
    """
    _set(ctx, company=True, shift=False, assign=True)
    assert _mobile_punch_allowed(ctx["emp"]) is False

    _set(ctx, company=True, shift=False, emp=True, assign=True)
    assert _mobile_punch_allowed(ctx["emp"]) is True


@pytest.mark.django_db(transaction=True)
def test_null_means_follow_not_allow(ctx):
    """
    ⚠️ الفارغ يعني «اتبع الأعمّ» لا «مسموح».

    فرقٌ بين من لم يُقرَّر له ومن قُرِّر له صراحةً — وخلطهما
    يفتح البصمة لمن أُقفلت على شركته.
    """
    _set(ctx, company=False, shift=None, emp=None)
    assert _mobile_punch_allowed(ctx["emp"]) is False
