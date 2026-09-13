"""
حرّاس التدريب والدورات (ق-149).

**الموارد تعرّف، والمدير يرشّح، والموارد تعتمد** — والموظف يطلب
**غير المتوفّر**.

⚠️⚠️ **والميزانية ثلاثية المصدر**: الموظف، فمرتبته، فبلا سقف —
**والفارغ لا يعني صفرًا**.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models import (
    JobGrade, NominationState, TrainingCourse, TrainingNomination)
from apps.employees.services import training as svc
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent

YEAR = date.today().year


@pytest.fixture
def env(db):
    r = provision_account(slug="trn-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="بدر", family_name_ar="العنزي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1099911122", mobile="0509991112")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="T-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])

        grade = JobGrade.objects.create(
            account=acc, company=comp, code="G5",
            name_ar="الخامسة", level=5,
            training_budget=Decimal("5000"))

        course = TrainingCourse.objects.create(
            account=acc, company=comp, code="PMP",
            name_ar="إدارة المشاريع", provider="معهد",
            duration_hours=40, cost=Decimal("3000"))

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "grade": grade, "course": course}


def test_budget_falls_back_through_three_levels(env):
    """
    ⚠️⚠️ الأهمّ: **الميزانية ثلاثية المصدر**.

    الموظف، فمرتبته، فبلا سقف — **والفارغ لا يعني صفرًا** (قرار
    جواد).
    """
    with account_scope(env["account_id"]):
        emp = env["emp"]

        # ١) بلا شيء → بلا سقف
        assert svc.budget_for(emp) is None

        # ٢) بمرتبة → ميزانيتها
        emp.job_grade = env["grade"]
        emp.save(update_fields=["job_grade"])
        assert svc.budget_for(emp) == Decimal("5000")

        # ٣) وبميزانيةٍ يدوية → تغلب المرتبة
        emp.training_budget_override = Decimal("8000")
        emp.save(update_fields=["training_budget_override"])
        assert svc.budget_for(emp) == Decimal("8000")


def test_no_budget_is_not_zero(env):
    """
    ⚠️ **وبلا سقفٍ ليس صفرًا**: فمن لا ميزانية له لا يُمنع — بل
    الاعتماد هو الضابط.
    """
    with account_scope(env["account_id"]):
        n = svc.nominate(course=env["course"], employment=env["emp"])
        out = svc.check_budget(n)
        assert out["exceeds"] is False, "مُنع من لا سقف له"


def test_cost_is_frozen_at_nomination(env):
    """
    ⚠️ **والتكلفة تُجمَّد عند الترشيح**: فتغيّر السعر بعدها لا
    يغيّر ما احتُسب.
    """
    with account_scope(env["account_id"]):
        n = svc.nominate(course=env["course"], employment=env["emp"])
        assert n.cost == Decimal("3000")

        env["course"].cost = Decimal("9000")
        env["course"].save(update_fields=["cost"])
        n.refresh_from_db()
        assert n.cost == Decimal("3000"), "تغيّرت التكلفة المحتسَبة"


def test_over_budget_warns_not_blocks(env):
    """
    ⚠️ **والتجاوز يُنبَّه لا يُمنع**: فحالاتٌ تستحقّه، والموارد
    تقرّر.
    """
    with account_scope(env["account_id"]):
        emp = env["emp"]
        emp.job_grade = env["grade"]          # 5000
        emp.save(update_fields=["job_grade"])

        n1 = svc.nominate(course=env["course"], employment=emp)
        svc.decide_nomination(nomination=n1, approve=True)

        c2 = TrainingCourse.objects.create(
            account_id=env["account_id"], company=env["comp"],
            code="CIA", name_ar="تدقيق داخليّ",
            cost=Decimal("4000"))
        n2 = svc.nominate(course=c2, employment=emp)

        out = svc.check_budget(n2)
        assert out["exceeds"] is True
        assert "يتجاوز" in out["warning"]

        # ⚠️ ومع ذلك يُعتمد — فالقرار للموارد
        svc.decide_nomination(nomination=n2, approve=True)
        n2.refresh_from_db()
        assert n2.state == NominationState.APPROVED


def test_approved_counts_even_if_absent(env):
    """
    ⚠️ **والمعتمَد يُحسب ولو لم يحضر** — فالمقعد حُجز ودُفع.
    """
    with account_scope(env["account_id"]):
        n = svc.nominate(course=env["course"], employment=env["emp"])
        svc.decide_nomination(nomination=n, approve=True)
        svc.record_result(nomination=n, attended=False,
                          note="لم يحضر")

        n.refresh_from_db()
        assert n.state == NominationState.NO_SHOW
        assert n.counts_against_budget is True
        assert svc.spent_this_year(env["emp"]) == Decimal("3000")


def test_rejected_does_not_count(env):
    """والمرفوض لا يُنقص شيئًا."""
    with account_scope(env["account_id"]):
        n = svc.nominate(course=env["course"], employment=env["emp"])
        svc.decide_nomination(nomination=n, approve=False,
                              note="غير ذي صلة")
        assert svc.spent_this_year(env["emp"]) == Decimal("0")


def test_no_result_before_approval(env):
    """
    ⚠️ **ولا نتيجة لغير المعتمَد**: فمن لم يُعتمد ترشيحه لم يحضر.
    """
    with account_scope(env["account_id"]):
        n = svc.nominate(course=env["course"], employment=env["emp"])
        with pytest.raises(svc.TrainingError):
            svc.record_result(nomination=n, attended=True, score=90)


def test_duplicate_live_nomination_refused(env):
    """ولا يُرشَّح لدورةٍ هو مرشَّحٌ لها."""
    with account_scope(env["account_id"]):
        svc.nominate(course=env["course"], employment=env["emp"])
        with pytest.raises(svc.TrainingError):
            svc.nominate(course=env["course"], employment=env["emp"])


def test_request_needs_justification(env):
    """
    ⚠️ **والمبرّر إلزاميّ** — فطلبٌ بلا مبرّر لا يُدرَس.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.TrainingError):
            svc.request_course(employment=env["emp"],
                               course_name="دورةٌ ما", justification="")


def test_available_course_cannot_be_requested(env):
    """
    ⚠️ **والمتوفّر يُرشَّح له لا يُطلَب** (قرار جواد).
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.TrainingError) as e:
            svc.request_course(employment=env["emp"],
                               course_name="إدارة المشاريع",
                               justification="أحتاجها")
        assert "متوفّرة" in str(e.value)


def test_request_can_become_a_course(env):
    """وطلبٌ يُقبل قد يُضاف للكتالوج."""
    with account_scope(env["account_id"]):
        r = svc.request_course(
            employment=env["emp"], course_name="تحليل البيانات",
            justification="لتطوير التقارير",
            estimated_cost=Decimal("2500"))
        svc.decide_request(request_obj=r, approve=True,
                           create_course=True, code="DATA")
        r.refresh_from_db()
        assert r.created_course is not None
        assert r.created_course.name_ar == "تحليل البيانات"


def test_decision_is_final(env):
    """والقرار لا يُعاد."""
    with account_scope(env["account_id"]):
        n = svc.nominate(course=env["course"], employment=env["emp"])
        svc.decide_nomination(nomination=n, approve=True)
        with pytest.raises(svc.TrainingError):
            svc.decide_nomination(nomination=n, approve=False)
