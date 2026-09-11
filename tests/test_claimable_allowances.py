"""
حرّاس المخصّصات المصروفة ومنع التكرار اليوميّ (ق-134).

⚠️ **لا طلبان من نوعٍ واحد في يومٍ واحد** — إلا أن يكون الأول
مرفوضًا أو مسحوبًا: فالرفض قد يُصحَّح بعد تفاهم.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import Request, RequestStatus, RequestType
from apps.leaves.services.requests import RequestError, create_request
from apps.payroll.models import (
    AllowanceEligibility, AmountMode, ClaimableAllowance)

TODAY = date.today()


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="alw-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="ياسر", family_name_ar="القرني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1055566688", mobile="0505556668")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="A-1",
            join_date=TODAY - timedelta(days=120),
            salary_lines=[(basic, Decimal("6000"))])

        lunch = ClaimableAllowance.objects.create(
            account=acc, company=comp, code="LUNCH", name_ar="غداء عمل",
            mode=AmountMode.CAP, amount=Decimal("60"))
        trans = ClaimableAllowance.objects.create(
            account=acc, company=comp, code="TRANS",
            name_ar="بدل مواصلات",
            mode=AmountMode.FIXED, amount=Decimal("30"))
        for a in (lunch, trans):
            AllowanceEligibility.objects.create(
                account=acc, company=comp, allowance=a, employment=emp)

        # مخصّصٌ لم يُسند له
        vip = ClaimableAllowance.objects.create(
            account=acc, company=comp, code="VIP", name_ar="بدل ضيافة",
            mode=AmountMode.CAP, amount=Decimal("500"))

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "lunch": lunch, "trans": trans, "vip": vip}


def _claim(env, allowance, amount, on=None, **extra):
    return create_request(
        employment=env["emp"],
        request_type=RequestType.CUSTOM_PAYMENT,
        payload={"allowance_id": allowance.id,
                 "work_date": str(on or TODAY),
                 "amount": str(amount), **extra})


def test_unassigned_allowance_is_refused(env):
    """
    ⚠️ **لا يُطلب ما لم يُسند**.

    فطلبُ من لا يستحقّ يُردّ، ويضيع وقت الطرفين.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(RequestError) as e:
            _claim(env, env["vip"], 100)
        assert "مُسنَد" in str(e.value)


def test_fixed_amount_must_match(env):
    """والثابت يُصرف كما هو — لا أقلّ ولا أكثر."""
    with account_scope(env["account_id"]):
        with pytest.raises(RequestError):
            _claim(env, env["trans"], 25)
        assert _claim(env, env["trans"], 30) is not None


def test_cap_is_enforced(env):
    """والسقف لا يُتجاوَز — وما دونه يمرّ."""
    with account_scope(env["account_id"]):
        assert _claim(env, env["lunch"], 45) is not None
        with pytest.raises(RequestError) as e:
            _claim(env, env["lunch"], 90, on=TODAY - timedelta(days=1))
        assert "سقف" in str(e.value)


def test_two_different_allowances_same_day(env):
    """
    ⚠️⚠️ الأهمّ: **مخصّصان مختلفان في يومٍ واحد يمرّان**.

    فمن له «غداء عمل» و«مواصلات» يطلبهما معًا — والمنع على المخصّص
    نفسه لا على نوع الطلب.
    """
    with account_scope(env["account_id"]):
        assert _claim(env, env["lunch"], 40) is not None
        assert _claim(env, env["trans"], 30) is not None


def test_same_allowance_twice_is_refused(env):
    """ونفس المخصّص مرّتين في اليوم يُرفض."""
    with account_scope(env["account_id"]):
        _claim(env, env["lunch"], 40)
        with pytest.raises(RequestError) as e:
            _claim(env, env["lunch"], 50)
        assert "بنفس التاريخ" in str(e.value)


def test_rejected_can_be_resubmitted(env):
    """
    ⚠️ **والمرفوض يُعاد تقديمه**.

    فالرفض قد يُصحَّح بعد تفاهم، ويُطلب من الموظف إعادة التقديم —
    ومنعُه يجعله عاجزًا عن تنفيذ ما طُلب منه.
    """
    with account_scope(env["account_id"]):
        first = _claim(env, env["lunch"], 40).request
        Request.objects.filter(id=first.id).update(
            status=RequestStatus.REJECTED)

        again = _claim(env, env["lunch"], 50)
        assert again is not None


def test_next_day_is_allowed(env):
    """واليوم التالي يُطلب فيه — فالمنع يوميّ لا مطلق."""
    with account_scope(env["account_id"]):
        _claim(env, env["lunch"], 40)
        assert _claim(env, env["lunch"], 40,
                      on=TODAY - timedelta(days=1)) is not None


def test_attachment_is_enforced_when_required(env):
    """وما يلزمه مرفق لا يمرّ بلاه."""
    with account_scope(env["account_id"]):
        env["lunch"].requires_attachment = True
        env["lunch"].save(update_fields=["requires_attachment"])

        with pytest.raises(RequestError) as e:
            _claim(env, env["lunch"], 40)
        assert "مرفق" in str(e.value)

        assert _claim(env, env["lunch"], 40,
                      attachment_url="/f/bill.png") is not None


def test_overtime_is_daily_unique(env):
    """
    ⚠️ والقاعدة تعمّ: **العمل الإضافي كذلك مرّةً في اليوم**.

    فطلبان لنفس اليوم يُحتسبان مرّتين — والأجر يُدفع مضاعفًا بلا
    عمل.
    """
    with account_scope(env["account_id"]):
        payload = {"work_date": str(TODAY), "from_time": "18:00",
                   "to_time": "21:00"}
        create_request(employment=env["emp"],
                       request_type=RequestType.OVERTIME,
                       payload=payload)
        with pytest.raises(RequestError):
            create_request(employment=env["emp"],
                           request_type=RequestType.OVERTIME,
                           payload=payload)


# ══════════ الصرف (ق-134) ══════════

def test_approval_creates_a_claim(env):
    """
    ⚠️ **اعتماد الطلب يُنشئ مستحقًّا** — بلا طريقة صرفٍ بعد.

    فالقرار عند الموارد لا عند الموظف: أيُدرج في المسير أم يُصرف
    خارجه.
    """
    from apps.payroll.models import AllowanceClaim

    with account_scope(env["account_id"]):
        req = _claim(env, env["lunch"], 40).request
        claim = AllowanceClaim.objects.filter(request_id=req.id).first()
        assert claim is not None, "اعتُمد الطلب ولم يُنشأ المستحقّ"
        assert claim.method == "", "حُدّدت طريقة الصرف بلا قرار"
        assert claim.is_settled is False


def test_effect_runs_without_an_approval_chain(env):
    """
    ⚠️⚠️ **علّة عامّة**: شركةٌ بلا سلسلة اعتماد تُعتمد طلباتها
    فورًا — **وكان الأثر لا يقع**.

    فالإجازة لا تُخصم، والعمل عن بُعد لا يُسجَّل حضورًا، والمخصّص
    لا يصير مستحقًّا — وكلّها تمرّ بالسكوت.
    """
    from apps.attendance.models import AttendanceDay, DayStatus

    with account_scope(env["account_id"]):
        day = TODAY - timedelta(days=2)
        create_request(employment=env["emp"],
                       request_type=RequestType.REMOTE_WORK,
                       payload={"start_date": str(day), "days": 1,
                                "reason": "ظرف"})
        assert AttendanceDay.objects.filter(
            employment=env["emp"], work_date=day,
            status=DayStatus.PRESENT).exists(), (
                "اعتُمد الطلب ولم يقع أثره")


def test_claim_is_not_settled_twice(env):
    """
    ⚠️ **ولا يُصرف مرّتين**: بندٌ في المسير ثم صرفٌ نقديّ يُضاعف
    المبلغ.
    """
    from apps.payroll.models import AllowanceClaim, DisbursementMethod

    with account_scope(env["account_id"]):
        req = _claim(env, env["lunch"], 40).request
        c = AllowanceClaim.objects.get(request_id=req.id)
        c.method = DisbursementMethod.OUTSIDE
        c.paid_on = TODAY
        c.is_settled = True
        c.save()

        c.refresh_from_db()
        assert c.is_settled is True
        # والمسار يرفض الثاني — يُختبر بالـAPI في حرّاس المسارات


def test_outside_payroll_records_when_and_who(env):
    """
    وخارج المسير **يُوثَّق متى وبمن** — ولا نسأل كيف.

    فمسؤوليتنا تنتهي بالتوثيق: كاش أو حوالة أو غيرها.
    """
    from apps.payroll.models import AllowanceClaim, DisbursementMethod

    with account_scope(env["account_id"]):
        req = _claim(env, env["lunch"], 40).request
        c = AllowanceClaim.objects.get(request_id=req.id)
        c.method = DisbursementMethod.OUTSIDE
        c.paid_on = TODAY
        c.paid_note = "نقدًا من العهدة"
        c.is_settled = True
        c.save()

        c.refresh_from_db()
        assert c.paid_on == TODAY
        assert c.paid_note
        assert c.payroll_run_type == "", "خارج المسير ومع ذلك نوع مسير"
