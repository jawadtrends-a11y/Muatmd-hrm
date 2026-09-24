"""
حارس: المالك موظفٌ أيضًا — والملكية ليست دورًا (ق-٢٥٥).

⚠️⚠️ أُنشئ أول مالكٍ يدويًّا فلم يُربط بموظفه — وكانت `create_person` قد أنشأت
للشخص مستخدمًا تلقائيًّا، **فصار للشخص الواحد مستخدمان**: واحدٌ يدخل به ولا ملفّ
له، وواحدٌ له ملفٌّ ولا يدخل به. **فلا يرى المالك ملفَّه ولا قسائمه، ولا يعمل له
التطبيق** — وهي أول علّةٍ يصطدم بها كل عميلٍ جديد.

⚠️⚠️ **والملكية ليست دورًا**: المالك مَن سجّل ويملك الاشتراك (صفةُ حساب)،
**والدور ما يفعله في الشركة**. وصاحبُ أول حسابٍ حقيقيّ مالكٌ وموظفٌ ومدير موارد.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="owner-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="جواد", family_name_ar="الغامدي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1076807039", mobile="0541106263", force=True)
        e = create_employment(person=p, company=comp, employee_no="E-100",
                              join_date=date(2025, 1, 1),
                              salary_lines=[(basic, Decimal("10000"))])
        yield r.account_id, (e[0] if isinstance(e, tuple) else e), p


def test_owner_is_linked_to_his_employee_record(env):
    """⭐ **الربط هو بيت القصيد** — وبه يرى المالك ملفَّه ويعمل التطبيق."""
    account_id, emp, person = env
    call_command("create_owner", account=account_id, employee_no="E-100",
                 username="owner1", password="Pw@123456", email="o@x.com")
    with account_scope(account_id):
        person.refresh_from_db()
        u = get_user_model().objects.get(username="owner1")
        assert person.user_id == u.id, "⚠️ المالك غير مربوطٍ بموظفه"


def test_no_duplicate_user_for_the_same_person(env):
    """⚠️ المستخدم التلقائيّ السابق **يُعطَّل** — فلا يبقى للشخص مستخدمان يعملان."""
    account_id, emp, person = env
    before = person.user_id
    call_command("create_owner", account=account_id, employee_no="E-100",
                 username="owner2", password="Pw@123456")
    U = get_user_model()
    if before:
        old = U.objects.filter(id=before).first()
        if old and old.username != "owner2":
            assert not old.is_active, "⚠️ للشخص مستخدمان يعملان"


def test_ownership_is_not_a_role(env):
    """
    ⚠️⚠️ **الملكية صفةُ حساب، والدور ما يفعله في الشركة.**
    فلا يُفرض `owner` دورًا على من هو مدير موارد.
    """
    account_id, emp, person = env
    call_command("create_owner", account=account_id, employee_no="E-100",
                 username="owner3", password="Pw@123456", role="hr_manager")
    with account_scope(account_id):
        u = get_user_model().objects.get(username="owner3")
        m = AccountMembership.objects.get(user=u)
        assert m.is_account_owner, "⚠️ الملكية لم تُسجَّل"
        ra = RoleAssignment.objects.filter(membership=m).first()
        assert ra and ra.role.code == "hr_manager", (
            "⚠️ فُرض دور المالك بدل دوره الحقيقيّ")
        assert ra.employment_id == emp.id, "⚠️ الدور غير مربوطٍ بتوظيفه"
