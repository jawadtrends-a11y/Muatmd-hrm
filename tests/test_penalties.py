"""
حرّاس الجزاءات التأديبية (ق-119، ق-121).

⚠️ نظامية وماليّة: القيود من النموذج الموحّد للائحة تنظيم العمل
(وزارة الموارد البشرية) — تجاوزها يعرّض المنشأة للمساءلة.
"""
from datetime import date, timedelta

TODAY = date.today()
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models_penalties import (
    Penalty, PenaltyKind, PenaltyStatus, ViolationType)
from apps.employees.services import penalties as svc
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayrollSettings


@pytest.fixture
def env(db):
    from apps.employees.models import SalaryStructure
    from apps.payroll.models import PayComponent

    r = provision_account(slug="pen-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        svc.provision_default_violations(comp)

        p, _ = create_person(
            account=acc, first_name_ar="راشد", family_name_ar="العمري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1033344455", mobile="0503334445")
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="P-1",
            join_date=TODAY,
            salary_lines=[(basic, Decimal("6000"))])

        yield {"account_id": r.account_id, "company": comp,
               "employment": emp}


def _v(env, code):
    return ViolationType.objects.get(company=env["company"], code=code)


def test_repeat_escalates_the_degree(env):
    """التدرّج: الأولى إنذار أو ربع يوم، ثم تصعد بالتكرار."""
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        emp = env["employment"]
        seen = []
        for i in range(3):
            p = svc.preview(emp, v, TODAY)
            seen.append(Decimal(p["days"]))
            svc.issue(employment=emp, violation=v,
                      occurred_on=TODAY,
                      description="تأخر", employee_statement="أفاد")
        assert seen == [Decimal("0.10"), Decimal("0.25"), Decimal("0.50")], seen


def test_monthly_cap_is_five_days(env):
    """
    ⚠️ السقف: لا يُقتطع أكثر من **أجر خمسة أيام في الشهر**.

    نصٌّ في النموذج الموحّد — وتجاوزه مخالفة.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "ABSENT-1")
        emp = env["employment"]
        for i in range(4):
            try:
                svc.issue(employment=emp, violation=v,
                          occurred_on=TODAY - timedelta(days=i),
                          description="غياب", employee_statement="أفاد")
            except svc.PenaltyError:
                pass
        total = svc.deducted_days_in_month(emp, TODAY)
        assert total <= Decimal("5"), total


def test_statement_required_above_one_day(env):
    """
    ⚠️ ما تجاوز **أجر يوم واحد** يلزمه سماع أقوال الموظف ومحضر.

    فالنموذج يوجب إبلاغه كتابةً وتحقيق دفاعه قبل توقيعه.
    """
    with account_scope(env["account_id"]):
        # الغياب: ١ إنذار · ٢ نصف يوم · ٣ يوم · ٤ يومان
        v = _v(env, "ABSENT-1")
        emp = env["employment"]
        # ⚠️ **بالتصاعد**: التكرار يعدّ ما وقع قبل تاريخ
        # المخالفة — فالتنازل يُبقيه على واحد أبدًا.
        for i in (3, 2, 1):
            # الثلاثة الأولى لا تتجاوز أجر يوم — تمرّ بلا إفادة
            svc.issue(employment=emp, violation=v,
                      occurred_on=TODAY - timedelta(days=i),
                      description="غياب", employee_statement="")

        # والرابعة يومان — تُرفض بلا إفادة
        with pytest.raises(svc.PenaltyError):
            svc.issue(employment=emp, violation=v,
                      occurred_on=TODAY,
                      description="غياب", employee_statement="")

        # وتمرّ بها
        svc.issue(employment=emp, violation=v,
                  occurred_on=TODAY,
                  description="غياب", employee_statement="أُخطر وأفاد")


def test_reset_days_drops_old_repeats(env):
    """
    ما مضى على سابقته أكثر من **مدّة السقوط** يُعدّ أولى.

    فالموظف لا يُلاحَق بمخالفةٍ قديمة أبدًا.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        emp = env["employment"]
        svc.issue(employment=emp, violation=v, occurred_on=TODAY,
                  description="سابقة", employee_statement="")
        # ⚠️ المادة (٧٣): تسقط السابقة بمضيّ **سنة كاملة**
        assert v.reset_days == 365
        later = TODAY + timedelta(days=v.reset_days + 10)
        assert svc.occurrence_for(emp, v, later) == 1
        # وقبلها تُحتسب
        assert svc.occurrence_for(emp, v, TODAY + timedelta(days=30)) == 2


def test_documented_without_deduction(env):
    """
    ⚠️ الخصم **قرار إداريّ**: تُوثَّق المخالفة بلا خصم.

    والجزاء يبقى في صحيفته — فالتوثيق لا يُهدر.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "ABSENT-1")
        emp = env["employment"]
        pen = svc.issue(employment=emp, violation=v,
                        occurred_on=TODAY,
                        description="غياب", employee_statement="أفاد",
                        apply_deduction=False)
        assert pen.amount == Decimal("0")
        assert pen.days == Decimal("0")
        assert svc.deducted_days_in_month(emp, TODAY) == 0
        assert Penalty.objects.filter(employment=emp).exists()


def test_occurrence_not_counted_stays_at_degree(env):
    """
    ⚠️ والتكرار قرارٌ كذلك: ما لم يُحتسب لا يرفع الدرجة.

    فالتوثيق حفظُ واقعة، والتصعيد يُقرَّر.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        emp = env["employment"]
        svc.issue(employment=emp, violation=v, occurred_on=TODAY,
                  description="تأخر", employee_statement="",
                  count_occurrence=False)
        assert svc.occurrence_for(emp, v, TODAY) == 1


def test_company_switch_disables_all_deductions(env):
    """وإعدادُ الشركة سقفٌ فوقهما — مطفأً لا خصم في النظام كلّه."""
    with account_scope(env["account_id"]):
        PayrollSettings.objects.filter(
            company=env["company"]).update(penalties_deduct_enabled=False)
        v = _v(env, "ABSENT-1")
        p = svc.preview(env["employment"], v, TODAY)
        assert not p["deductible"]
        assert Decimal(p["days"]) == 0


def test_violation_without_financial_effect(env):
    """وبندٌ بلا أثر ماليّ يُوثَّق ولا يُخصم مهما كانت درجته."""
    with account_scope(env["account_id"]):
        v = _v(env, "ABSENT-1")
        ViolationType.objects.filter(id=v.id).update(financial_effect=False)
        v.refresh_from_db()
        p = svc.preview(env["employment"], v, TODAY)
        assert not p["deductible"]


def test_pending_board_lists_unsigned_violations(env):
    """
    سجلّ المقترحات يعرض من خالف ولم يُوقَّع عليه — بحسم وقته.

    فما لا يُعرض لا يُطبَّق، والمسؤول لا يبحث عن المخالفين.
    """
    from apps.attendance.models import AttendanceDay, DayStatus

    with account_scope(env["account_id"]):
        AttendanceDay.objects.create(
            account_id=env["account_id"], company=env["company"],
            employment=env["employment"], work_date=TODAY,
            status=DayStatus.PRESENT, late_minutes=45)

        rows = svc.pending_board(env["company"], TODAY,
                                 TODAY)
        assert len(rows) == 1
        assert rows[0]["minutes"] == 45
        # ٤٥ دقيقة من ٦٠٠٠ على ثماني ساعات = ١٨.٧٥
        assert Decimal(rows[0]["time_deduction"]) == Decimal("18.75")


def test_signed_day_leaves_the_board(env):
    """وما وُقّع عليه يخرج من السجلّ — فلا يُوقَّع مرّتين."""
    from apps.attendance.models import AttendanceDay, DayStatus

    with account_scope(env["account_id"]):
        AttendanceDay.objects.create(
            account_id=env["account_id"], company=env["company"],
            employment=env["employment"], work_date=TODAY,
            status=DayStatus.ABSENT)

        rows = svc.pending_board(env["company"], TODAY,
                                 TODAY)
        assert len(rows) == 1

        svc.issue_batch(company=env["company"], rows=rows,
                        employee_statement="أفاد")
        after = svc.pending_board(env["company"], TODAY,
                                  TODAY)
        assert after == []


def test_stale_violation_cannot_be_penalised(env):
    """
    ⚠️ المادة (٦٩): لا جزاء على مخالفة مضى عليها **ثلاثون يومًا**.

    فالمنشأة التي سكتت شهرًا سقط حقّها، والتوقيع بعدها باطل
    يُردّ في المحكمة العمالية.
    """
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        with pytest.raises(svc.PenaltyError) as e:
            svc.issue(employment=env["employment"], violation=v,
                      occurred_on=TODAY - timedelta(days=45),
                      description="تأخر قديم", employee_statement="أفاد")
        assert "ثلاثين" in str(e.value)


def test_fresh_violation_is_accepted(env):
    """وما كان في المهلة يُوقَّع."""
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        p = svc.issue(employment=env["employment"], violation=v,
                      occurred_on=TODAY - timedelta(days=10),
                      description="تأخر", employee_statement="أفاد")
        assert p.id


# ══════════ نسخ اللائحة (ق-130) ══════════

def test_revision_copies_and_keeps_the_old(env):
    """
    ⚠️ التنقيح **ينسخ البنود ولا يدوسها**.

    فالنسخة القديمة تبقى كما هي، وما وقع قبل السريان يُقاس بها.
    """
    from apps.employees.models_penalties import PolicyVersion

    with account_scope(env["account_id"]):
        comp = env["company"]
        v1 = svc.active_version(comp)
        assert v1 is not None
        count_before = v1.violations.count()

        v2, copied = svc.revise(
            company=comp, effective_from=TODAY + timedelta(days=1),
            note="تشديد")
        assert copied == count_before
        assert v2.number == v1.number + 1

        v1.refresh_from_db()
        assert v1.violations.count() == count_before, "دُهست القديمة"


def test_active_version_follows_the_date(env):
    """
    ⚠️⚠️ الأهمّ: **التاريخ يحكم لا التعديل**.

    فمخالفةُ الأمس تُقاس بلائحة الأمس — وهو ما يصمد أمام هيئة
    تسوية الخلافات.
    """
    with account_scope(env["account_id"]):
        comp = env["company"]
        before = svc.active_version(comp).number
        svc.revise(company=comp, effective_from=TODAY + timedelta(days=5))

        assert svc.active_version(comp).number == before
        assert svc.active_version(
            comp, TODAY + timedelta(days=5)).number == before + 1


def test_two_versions_same_day_refused(env):
    """ولا نسختان في يومٍ واحد — فأيّهما تسري؟"""
    with account_scope(env["account_id"]):
        comp = env["company"]
        day = TODAY + timedelta(days=3)
        svc.revise(company=comp, effective_from=day)
        with pytest.raises(svc.PenaltyError):
            svc.revise(company=comp, effective_from=day)


def test_penalty_records_its_version(env):
    """والجزاء يحفظ نسخته — فيُراجَع بما كان."""
    with account_scope(env["account_id"]):
        v = _v(env, "LATE-30")
        pen = svc.issue(employment=env["employment"], violation=v,
                        occurred_on=TODAY, description="تأخر",
                        employee_statement="أفاد")
        assert pen.policy_version_no == svc.active_version(
            env["company"]).number


def test_repeats_survive_a_revision(env):
    """
    ⚠️ وسوابق الموظف **تعبر التنقيح**.

    فالتنقيح ينسخ البنود بمعرّفاتٍ جديدة — والعدّ بالمعرّف يُصفّر
    سوابقه ويجعله «أول مرّة» أبدًا.
    """
    with account_scope(env["account_id"]):
        comp = env["company"]
        # نُثبّت البند القديم بمعرّفه قبل أي تنقيح
        v_old = svc.violations_on(
            comp, TODAY).filter(code="LATE-30").first()
        assert v_old is not None
        old_id = v_old.id

        svc.issue(employment=env["employment"], violation=v_old,
                  occurred_on=TODAY - timedelta(days=2),
                  description="تأخر", employee_statement="")

        # التنقيح يسري غدًا — فلا أثر رجعيّ
        tomorrow = TODAY + timedelta(days=1)
        svc.revise(company=comp, effective_from=tomorrow)
        v_new = svc.violations_on(
            comp, tomorrow).filter(code="LATE-30").first()
        assert v_new is not None
        assert v_new.id != old_id, "لم يُنسخ البند بالتنقيح"

        occ = svc.occurrence_for(env["employment"], v_new, tomorrow)
        assert occ == 2, f"صُفّرت سوابقه بالتنقيح: {occ}"


def test_backdated_revision_is_refused(env):
    """
    ⚠️ ولا تنقيح بأثرٍ رجعيّ.

    فنسخةٌ تسري قبل السارية تُعيد تقييم جزاءاتٍ وُقّعت — والموظف
    عوقب بلائحةٍ يومها، فتغييرها بعده يُبطل الجزاء لا يُصحّحه.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.PenaltyError) as e:
            svc.revise(company=env["company"],
                       effective_from=TODAY - timedelta(days=30))
        assert "رجعيّ" in str(e.value)
