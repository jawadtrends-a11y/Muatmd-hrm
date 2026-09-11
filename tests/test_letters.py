"""
حرّاس قوالب الخطابات (ق-128).

⚠️ **الخطاب وثيقةٌ رسمية**: يخرج من المنشأة بختمها، فمتغيّرٌ
مجهول يبقى ظاهرًا فيه، وراتبٌ يُطبع بلا طلب صاحبه يفشي ما لا
يُفشى.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.models_billing import Plan
from apps.accounts.services.provisioning import provision_account
from apps.core.models import IssuedLetter, LetterTemplate
from apps.core.services import letters as svc
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="ltr-t", display_name_ar="حساب",
                          company_name_ar="شركة معتمد", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        housing = PayComponent.objects.filter(
            company=comp, code="HOUSING").first()

        p, _ = create_person(
            account=acc, first_name_ar="نايف", family_name_ar="العتيبي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077788899", mobile="0507778889")
        lines = [(basic, Decimal("6000"))]
        if housing:
            lines.append((housing, Decimal("1500")))
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="L-1",
            join_date=TODAY - timedelta(days=800), salary_lines=lines)

        tpl = LetterTemplate.objects.create(
            account=acc, company=comp, code="SALARY_CERT",
            name_ar="تعريف بالراتب",
            heading_ar="تعريف بالراتب",
            body_ar=("نفيدكم بأن {{employee_name}} يعمل لدينا منذ "
                     "{{join_date}} وراتبه {{total_salary}} "
                     "({{salary_words}}) — {{company_name}}"),
            includes_salary=True, valid_days=30)

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "tpl": tpl}


def test_unknown_variable_is_refused(env):
    """
    ⚠️ متغيّرٌ مجهول يُرفض عند الحفظ.

    فبلا ذلك يبقى «{{الراتب}}» ظاهرًا في خطابٍ بيد الموظف.
    """
    with pytest.raises(svc.LetterError):
        svc.validate_body("مرحبًا {{employee_name}} و{{not_a_variable}}")


def test_declared_variables_pass(env):
    """وما أُعلن يمرّ."""
    assert svc.validate_body("{{employee_name}} — {{today}}")


def test_salary_hidden_unless_requested(env):
    """
    ⚠️⚠️ الأهمّ: **الراتب لا يُطبع إلا بطلب صاحبه**.

    فنموذج الخطاب ينصّ عليه، وسهوٌ واحد يفشي راتب موظفٍ في خطابٍ
    لم يطلبه.
    """
    with account_scope(env["account_id"]):
        letter = svc.issue(template=env["tpl"], employment=env["emp"],
                           include_salary=False)
        assert "7,500" not in letter.body_ar
        assert "—" in letter.body_ar


def test_salary_printed_when_requested(env):
    """وبطلبه يُطبع رقمًا وكتابةً."""
    with account_scope(env["account_id"]):
        letter = svc.issue(template=env["tpl"], employment=env["emp"],
                           include_salary=True)
        assert "7,500.00" in letter.body_ar
        assert "ريالًا سعوديًّا" in letter.body_ar


def test_template_without_salary_never_prints_it(env):
    """
    وقالبٌ لا يأذن بالراتب لا يطبعه **ولو طُلب**.

    فالإذنان معًا: القالب وصاحب الشأن.
    """
    with account_scope(env["account_id"]):
        env["tpl"].includes_salary = False
        env["tpl"].save(update_fields=["includes_salary"])
        letter = svc.issue(template=env["tpl"], employment=env["emp"],
                           include_salary=True)
        assert "7,500" not in letter.body_ar


def test_body_is_frozen_at_issue(env):
    """
    ⚠️ النصّ يُجمَّد عند الإصدار.

    فتعديل القالب بعده لا يغيّر ما بيد الموظف — ومن راجع بعد سنة
    يرى ما صدر فعلًا.
    """
    with account_scope(env["account_id"]):
        letter = svc.issue(template=env["tpl"], employment=env["emp"])
        before = letter.body_ar

        env["tpl"].body_ar = "نصٌّ مختلف تمامًا"
        env["tpl"].save(update_fields=["body_ar"])

        letter.refresh_from_db()
        assert letter.body_ar == before, "تغيّر نصُّ خطابٍ صدر"


def test_letter_numbers_do_not_repeat(env):
    """والأرقام لا تتكرّر — فالرقم مرجعُ الوثيقة."""
    with account_scope(env["account_id"]):
        nums = {svc.issue(template=env["tpl"],
                          employment=env["emp"]).letter_no
                for _ in range(3)}
        assert len(nums) == 3, nums


def test_validity_follows_the_template(env):
    """والصلاحية من القالب — تعدّلها الشركة."""
    with account_scope(env["account_id"]):
        env["tpl"].valid_days = 7
        env["tpl"].save(update_fields=["valid_days"])
        letter = svc.issue(template=env["tpl"], employment=env["emp"])
        # ⚠️ **من تاريخ الإصدار نفسه** لا من TODAY المجمَّد عند
        # الاستيراد: تشغيلٌ يعبر منتصف الليل يجعلهما يومين.
        assert letter.valid_until == letter.issued_on + timedelta(days=7)


def test_salary_in_words_is_reasonable(env):
    """والمبلغ كتابةً صحيحٌ — فالخطاب الرسميّ يذكره بالوجهين."""
    assert svc._num_to_words_ar(7500) == "سبعة آلاف وخمسمئة"
    assert svc._num_to_words_ar(1000) == "ألف"
    assert svc._num_to_words_ar(2000) == "ألفان"
    assert svc._num_to_words_ar(0) == "صفر"
