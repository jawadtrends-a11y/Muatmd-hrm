"""
حرّاس السياسات وإقراراتها (ق-129).

⚠️ **سياسةٌ بلا إقرارٍ موثَّق لا يُحتجّ بها**: المنشأة تقول
«نبّهنا» والموظف يقول «لم أعلم» — والإقرار بختم وقته هو الحجّة.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.models import Policy, PolicyAcknowledgement, PolicyAudience
from apps.core.services import policies as svc
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="pol-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        emps = []
        for i, (first, nid, mob) in enumerate((
                ("سعد", "1088899911", "0508889991"),
                ("طلال", "1099900022", "0509990002"),
                ("منى", "1010011133", "0501001113")), start=1):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar="الشمري",
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=f"P-{i}",
                join_date=TODAY - timedelta(days=100),
                salary_lines=[(basic, Decimal("5000"))])
            emps.append(e)

        pol = Policy.objects.create(
            account=acc, company=comp, code="CONDUCT",
            title_ar="سياسة السلوك",
            body_ar="يلتزم الموظف بآداب المهنة.",
            effective_from=TODAY)

        yield {"account_id": r.account_id, "comp": comp,
               "emps": emps, "policy": pol}


def test_unpublished_policy_cannot_be_acknowledged(env):
    """غير المنشورة لا يُقرّ بها — فلم تُعرض بعد."""
    with account_scope(env["account_id"]):
        with pytest.raises(svc.PolicyError):
            svc.acknowledge(policy=env["policy"],
                            employment=env["emps"][0])


def test_empty_policy_cannot_be_published(env):
    """
    ⚠️ ولا تُنشر بلا نصّ.

    فسياسةٌ فارغة يُطالَب الموظف بالإقرار بها.
    """
    with account_scope(env["account_id"]):
        env["policy"].body_ar = "   "
        env["policy"].save(update_fields=["body_ar"])
        with pytest.raises(svc.PolicyError):
            svc.publish(policy=env["policy"])


def test_compliance_counts_audience(env):
    """والامتثال يُحسب على من تخصّهم — لا على الجميع."""
    with account_scope(env["account_id"]):
        svc.publish(policy=env["policy"])
        c = svc.compliance(env["policy"])
        assert c["total"] == 3
        assert c["acknowledged"] == 0

        svc.acknowledge(policy=env["policy"], employment=env["emps"][0])
        c2 = svc.compliance(env["policy"])
        assert c2["acknowledged"] == 1
        assert c2["rate"] == 33


def test_new_version_resets_acknowledgements(env):
    """
    ⚠️⚠️ الأهمّ: **النسخة الجديدة تُبطل الإقرارات**.

    فمن أقرّ بنسخةٍ لا يُعدّ مُقرًّا بما عُدّل بعدها — وإلا
    احتجّت المنشأة بتوقيعٍ على نصٍّ لم يره.
    """
    with account_scope(env["account_id"]):
        svc.publish(policy=env["policy"])
        for e in env["emps"]:
            svc.acknowledge(policy=env["policy"], employment=e)
        assert svc.compliance(env["policy"])["rate"] == 100

        svc.bump_version(policy=env["policy"], body_ar="نصٌّ معدَّل")
        c = svc.compliance(env["policy"])
        assert c["version"] == 2
        assert c["acknowledged"] == 0, "نسخةٌ جديدة ومع ذلك أُقرّ بها"


def test_old_acknowledgements_are_kept(env):
    """
    والإقرارات القديمة **لا تُحذف** — سجلٌّ يُراجَع، ومحوُه يُخفي
    ما جرى.
    """
    with account_scope(env["account_id"]):
        svc.publish(policy=env["policy"])
        svc.acknowledge(policy=env["policy"], employment=env["emps"][0])
        svc.bump_version(policy=env["policy"], body_ar="معدَّل")

        assert PolicyAcknowledgement.objects.filter(
            policy=env["policy"], version=1).exists()


def test_acknowledging_twice_is_idempotent(env):
    """والتكرار لا يُنشئ إقرارًا ثانيًا."""
    with account_scope(env["account_id"]):
        svc.publish(policy=env["policy"])
        _, first = svc.acknowledge(policy=env["policy"],
                                   employment=env["emps"][0])
        _, second = svc.acknowledge(policy=env["policy"],
                                    employment=env["emps"][0])
        assert first is True and second is False
        assert PolicyAcknowledgement.objects.filter(
            policy=env["policy"], employment=env["emps"][0]).count() == 1


def test_terminated_employees_are_not_counted(env):
    """
    ⚠️ ومن أُنهيت خدمته لا يُطالَب بإقرار.

    فعدُّه في «لم يُقرّوا» يجعل اللوحة لا تخلو أبدًا.
    """
    from apps.employees.models import Employment, EmploymentStatus

    with account_scope(env["account_id"]):
        svc.publish(policy=env["policy"])
        Employment.objects.filter(id=env["emps"][2].id).update(
            status=EmploymentStatus.TERMINATED)
        assert svc.compliance(env["policy"])["total"] == 2


def test_view_only_policy_needs_no_ack(env):
    """وسياسةٌ للاطّلاع لا تحتاج توقيعًا."""
    with account_scope(env["account_id"]):
        env["policy"].requires_ack = False
        env["policy"].save(update_fields=["requires_ack"])
        svc.publish(policy=env["policy"])

        with pytest.raises(svc.PolicyError):
            svc.acknowledge(policy=env["policy"],
                            employment=env["emps"][0])

        rows = svc.my_policies(env["emps"][0])
        assert rows and rows[0]["acknowledged"] is True


def test_my_policies_lists_unacked_first(env):
    """وما لم يُقرّ به يُصدَّر — فالترتيب تنبيهٌ لا عرض."""
    with account_scope(env["account_id"]):
        svc.publish(policy=env["policy"])
        second = Policy.objects.create(
            account_id=env["account_id"], company=env["comp"],
            code="SAFETY", title_ar="أ سياسة السلامة",
            body_ar="نصّ", effective_from=TODAY)
        svc.publish(policy=second)
        svc.acknowledge(policy=second, employment=env["emps"][0])

        rows = svc.my_policies(env["emps"][0])
        assert rows[0]["needs_ack"] is True, [r["title_ar"] for r in rows]
