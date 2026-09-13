"""
حرّاس تقييم الأداء (ق-146).

**أربع طبقات** (قرار جواد): المدير يضع، والموارد تعتمد، والمشرف
يُدخل، والموارد تعتمد.

⚠️⚠️ **وتقييم المدير مجهولٌ دائمًا** — فلو رآه باسم صاحبه لم
يصدق أحد.

⚠️ **والأثر تقريرٌ فقط** — لا مال.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.models import (
    ApprovalState, KPI, KPIAssignment, PeerReview, ReviewCycle,
    ReviewKind)
from apps.employees.services import performance as svc
from apps.employees.services.hiring import create_employment, create_person
from apps.organization.models import Department
from apps.payroll.models import PayComponent


@pytest.fixture
def env(db):
    r = provision_account(slug="perf-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        dept = (Department.objects.filter(company=comp).first()
                or Department.objects.create(
                    account=acc, company=comp, code="OPS",
                    name_ar="العمليات"))

        # ⚠️ أسماءٌ متباينة — فحارس التشابه يمنع المتقاربة
        names = [("خالد", "العتيبي"), ("سارة", "الدوسري"),
                 ("مازن", "الشمري"), ("لمياء", "القحطاني"),
                 ("طارق", "الغامدي")]
        emps = []
        for i, (fn, ln) in enumerate(names):
            p, _ = create_person(
                account=acc, first_name_ar=fn, family_name_ar=ln,
                gender="male", nationality_code="SA",
                id_type="national_id",
                id_number=f"1{i}55566{i}7{i}", mobile=f"0501{i}2233{i}")
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=f"K-{i}",
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("8000"))])
            emps.append(e)

        cycle = ReviewCycle.objects.create(
            account=acc, company=comp, code="Q1", name_ar="الربع الأول",
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31))

        yield {"account_id": r.account_id, "comp": comp, "dept": dept,
               "emps": emps, "cycle": cycle}


def _kpi(env, code="TXN", scale="percent", direction="higher",
         approve=True):
    k = svc.create_kpi(department=env["dept"], code=code,
                       name_ar="مؤشّر " + code, scale=scale,
                       direction=direction)
    if approve:
        svc.decide_kpi(kpi=k, approve=True)
        k.refresh_from_db()
    return k


def test_kpi_starts_pending(env):
    """
    ⚠️ **والمؤشّر يبدأ بانتظار الموارد**.

    فمؤشّرٌ يضعه مديرٌ ويقيس به فريقه بلا مراجعة يصير حكمًا بلا
    ضابط.
    """
    with account_scope(env["account_id"]):
        k = _kpi(env, approve=False)
        assert k.state == ApprovalState.PENDING
        assert k.is_usable is False


def test_unapproved_kpi_cannot_be_assigned(env):
    """وغير المعتمَد لا يُقاس به."""
    with account_scope(env["account_id"]):
        k = _kpi(env, approve=False)
        with pytest.raises(svc.PerformanceError) as e:
            svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                       kpi=k, target=100, weight=50)
        assert "غير معتمد" in str(e.value)


def test_weights_cannot_exceed_100(env):
    """
    ⚠️ **ومجموع الأوزان لا يتجاوز ١٠٠** — فوزنٌ زائد يُجمّل
    النتيجة.
    """
    with account_scope(env["account_id"]):
        k1, k2 = _kpi(env, "A"), _kpi(env, "B")
        svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                   kpi=k1, target=100, weight=70)
        with pytest.raises(svc.PerformanceError) as e:
            svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                       kpi=k2, target=100, weight=40)
        assert "يتجاوز" in str(e.value)


def test_cannot_enter_own_actual(env):
    """
    ⚠️ **ولا يُدخل أحدٌ فعليّ نفسه** — فمن يقيس نفسه لا يُحاسَب.
    """
    with account_scope(env["account_id"]):
        k = _kpi(env)
        a = svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                       kpi=k, target=100, weight=50)
        with pytest.raises(svc.PerformanceError) as e:
            svc.enter_actual(assignment=a, actual=90,
                             by_employment=env["emps"][0])
        assert "نفسك" in str(e.value)


def test_score_requires_approval(env):
    """
    ⚠️⚠️ **والمدخَل ليس نتيجةً قبل مراجعته**.
    """
    with account_scope(env["account_id"]):
        k = _kpi(env)
        a = svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                       kpi=k, target=100, weight=100)
        svc.enter_actual(assignment=a, actual=90,
                         by_employment=env["emps"][1])

        assert svc.final_score(env["cycle"],
                               env["emps"][0])["kpi_score"] is None
        svc.approve_actual(assignment=a)
        assert svc.final_score(env["cycle"],
                               env["emps"][0])["kpi_score"] == 90.0


def test_lower_is_better_is_inverted(env):
    """
    ⚠️ **والأقلّ أفضل يُقلب**: فمؤشّر «نسبة الأخطاء» يُقاس عكسًا،
    وحسابُه كغيره يقلب المعنى.
    """
    with account_scope(env["account_id"]):
        k = _kpi(env, "ERR", direction="lower")
        a = svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                       kpi=k, target=10, weight=100)
        svc.enter_actual(assignment=a, actual=5,
                         by_employment=env["emps"][1])
        # هدفٌ ١٠ وفعليّ ٥ — أي ضعف الجودة
        assert a.score > 100


def test_scale_5_is_out_of_five(env):
    """وسُلّم الخمسة يُحسب على خمسة لا على الهدف."""
    with account_scope(env["account_id"]):
        k = _kpi(env, "QLT", scale="scale_5")
        a = svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                       kpi=k, target=5, weight=100)
        svc.enter_actual(assignment=a, actual=4,
                         by_employment=env["emps"][1])
        assert a.score == Decimal("80")


def test_upward_review_stores_no_identity(env):
    """
    ⚠️⚠️ الأهمّ: **لا يُحفظ اسم من قيّم مديره**.

    فلو رآه المدير باسمه لم يصدق أحد.
    """
    with account_scope(env["account_id"]):
        mgr = env["emps"][0]
        for e in env["emps"][1:4]:
            svc.submit_upward_review(cycle=env["cycle"],
                                     author_employment=e,
                                     manager_employment=mgr, score=4)

        rows = PeerReview.objects.filter(cycle=env["cycle"],
                                         kind=ReviewKind.UPWARD)
        assert rows.count() == 3
        assert all(r.author_employment_id is None for r in rows), (
            "حُفظت هوية المقيّم!")


def test_upward_duplicate_blocked_without_identity(env):
    """
    ⚠️ **والتكرار يُمنع بالبصمة** — تُطابق ولا تُفكّ.

    فبلا هذا يُقيَّم المدير مرّاتٍ من شخصٍ واحد.
    """
    with account_scope(env["account_id"]):
        mgr, author = env["emps"][0], env["emps"][1]
        svc.submit_upward_review(cycle=env["cycle"],
                                 author_employment=author,
                                 manager_employment=mgr, score=5)
        with pytest.raises(svc.PerformanceError):
            svc.submit_upward_review(cycle=env["cycle"],
                                     author_employment=author,
                                     manager_employment=mgr, score=1)


def test_upward_summary_hidden_below_threshold(env):
    """
    ⚠️ **ولا تُعرض الخلاصة دون حدٍّ أدنى**: فواحدٌ يُعرَف
    بالضرورة، واثنان يُخمَّنان.
    """
    with account_scope(env["account_id"]):
        mgr = env["emps"][0]
        svc.submit_upward_review(cycle=env["cycle"],
                                 author_employment=env["emps"][1],
                                 manager_employment=mgr, score=2,
                                 comment="سرّيّ")

        out = svc.upward_summary(env["cycle"], mgr)
        assert out["average"] is None, "كُشفت خلاصةٌ بتقييمٍ واحد"
        assert out["comments"] == []
        assert "حمايةً" in out["note"]


def test_upward_summary_shown_above_threshold(env):
    """وبثلاثةٍ فأكثر تُعرض مجمَّعة."""
    with account_scope(env["account_id"]):
        mgr = env["emps"][0]
        for e in env["emps"][1:4]:
            svc.submit_upward_review(cycle=env["cycle"],
                                     author_employment=e,
                                     manager_employment=mgr, score=4)
        out = svc.upward_summary(env["cycle"], mgr)
        assert out["count"] == 3
        assert out["average"] == 4.0


def test_self_review_is_attributed(env):
    """والذاتيّ منسوبٌ لصاحبه — فهو عن نفسه."""
    with account_scope(env["account_id"]):
        r = svc.submit_self_review(cycle=env["cycle"],
                                   employment=env["emps"][0], score=4)
        assert r.author_employment_id == env["emps"][0].id


def test_no_pay_effect(env):
    """
    ⚠️ **والأثر تقريرٌ فقط** — لا مال (قرار جواد).
    """
    with account_scope(env["account_id"]):
        out = svc.final_score(env["cycle"], env["emps"][0])
        assert out["affects_pay"] is False


def test_closed_cycle_is_locked(env):
    """والمغلقة لا يُضاف إليها."""
    with account_scope(env["account_id"]):
        env["cycle"].is_open = False
        env["cycle"].save(update_fields=["is_open"])
        k = _kpi(env)
        with pytest.raises(svc.PerformanceError):
            svc.assign(cycle=env["cycle"], employment=env["emps"][0],
                       kpi=k, target=100, weight=50)
