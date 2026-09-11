"""
حرّاس تذاكر الدعم (ق-133).

⚠️ **زمن الاستجابة يُقاس ولا يبقى وعدًا**: نبيع «٨ ساعات عمل»
فيجب أن يُحسب موعدُه ويُعلَم من تجاوزناه.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.models_billing import Plan
from apps.accounts.models_billing_v2 import AccountSubscription
from apps.accounts.services.provisioning import provision_account
from apps.core.models import SupportTicket, TicketStatus
from apps.core.services import tickets as svc
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person

RIYADH = ZoneInfo("Asia/Riyadh")


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    r = provision_account(slug="tkt-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="عمر", family_name_ar="الزهراني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1033344477", mobile="0503334447")
        create_employment(person=p, company=comp, employee_no="K-1",
                          join_date=timezone.localdate() - timedelta(days=90),
                          salary_lines=[(basic, Decimal("5000"))])
        yield {"account_id": r.account_id, "comp": comp, "person": p}


def test_ticket_needs_a_screenshot(env):
    """
    ⚠️ الأهمّ: **لا تذكرة بلا صورة شاشة**.

    فـ«لا يعمل» بلا صورة تُستهلك في أسئلةٍ متبادلة — والشاشة تقول
    أكثر من فقرة.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(svc.TicketError) as e:
            svc.open_ticket(company=env["comp"], person=env["person"],
                            subject="عطل", body="لا يعمل",
                            screenshot_url="")
        assert "صورة" in str(e.value)


def test_ticket_needs_subject_and_body(env):
    """والعنوان والشرح كذلك."""
    with account_scope(env["account_id"]):
        for kw in ({"subject": ""}, {"body": ""}):
            args = {"subject": "عطل", "body": "شرح",
                    "screenshot_url": "/f/x.png", **kw}
            with pytest.raises(svc.TicketError):
                svc.open_ticket(company=env["comp"],
                                person=env["person"], **args)


def test_business_hours_skip_the_weekend(env):
    """
    ⚠️⚠️ **ساعات العمل تتخطّى العطلة**.

    فتذكرةٌ تُفتح الخميس ٤:٣٠م بمهلة ساعتين تستحقّ الأحد ٩:٣٠ص —
    لا الخميس ٦:٣٠م. والوعد بساعات العمل يجب أن يُحسب بها.
    """
    thu = datetime(2026, 9, 10, 16, 30, tzinfo=RIYADH)
    due = svc.add_business_hours(thu, 2)
    assert due.weekday() == 6, due          # الأحد
    assert (due.hour, due.minute) == (9, 30), due


def test_business_hours_within_a_day(env):
    """وداخل اليوم تُحسب كما هي."""
    sun = datetime(2026, 9, 13, 9, 0, tzinfo=RIYADH)
    assert svc.add_business_hours(sun, 3).hour == 12


def test_sla_follows_the_plan(env):
    """
    ومهلة الاستجابة **من الباقة**: أساسيّ ٢٤ ساعة، احترافيّ ٨
    ساعات عمل، متقدّم ساعتان.
    """
    with account_scope(env["account_id"]):
        for code, hours, business in (("basic", 24, False),
                                      ("premium", 8, True),
                                      ("enterprise", 2, True)):
            plan = Plan.objects.filter(code=code).first()
            if plan is None:
                continue
            AccountSubscription.objects.filter(
                account_id=env["account_id"]).update(plan=plan)
            h, b, c = svc.sla_for(env["account_id"])
            assert (h, b) == (hours, business), (code, h, b)


def test_sla_is_frozen_at_open(env):
    """
    ⚠️ **والمهلة تُجمَّد عند الفتح**.

    فترقية الباقة بعدها لا تُغيّر تعهّدنا في تذكرةٍ قائمة، ولا
    تخفيضُها يُعفينا منه.
    """
    with account_scope(env["account_id"]):
        basic = Plan.objects.filter(code="basic").first()
        AccountSubscription.objects.filter(
            account_id=env["account_id"]).update(plan=basic)

        t = svc.open_ticket(company=env["comp"], person=env["person"],
                            subject="عطل", body="شرح",
                            screenshot_url="/f/x.png")
        assert t.sla_hours == 24

        ent = Plan.objects.filter(code="enterprise").first()
        AccountSubscription.objects.filter(
            account_id=env["account_id"]).update(plan=ent)
        t.refresh_from_db()
        assert t.sla_hours == 24, "تبدّلت مهلة تذكرةٍ قائمة"


def test_first_response_is_stamped(env):
    """
    ⚠️ وأول ردٍّ من الدعم **يُختم وقته** — به يُقاس الوفاء.
    """
    with account_scope(env["account_id"]):
        t = svc.open_ticket(company=env["comp"], person=env["person"],
                            subject="عطل", body="شرح",
                            screenshot_url="/f/x.png")
        assert t.first_response_at is None

        svc.reply(ticket=t, body="نراجعها", from_support=True)
        t.refresh_from_db()
        assert t.first_response_at is not None
        assert t.status == TicketStatus.WAITING

        # وردّ العميل يعيدها مفتوحة
        svc.reply(ticket=t, body="ما زالت", from_support=False,
                  person=env["person"])
        t.refresh_from_db()
        assert t.status == TicketStatus.OPEN


def test_breach_is_detected(env):
    """
    ومن تجاوزنا مهلته **يُعلَم** — فمستوى الخدمة يُقاس لا يُدّعى.
    """
    with account_scope(env["account_id"]):
        t = svc.open_ticket(company=env["comp"], person=env["person"],
                            subject="عطل", body="شرح",
                            screenshot_url="/f/x.png")
        assert t.breached is False

        SupportTicket.objects.filter(id=t.id).update(
            due_at=timezone.now() - timedelta(hours=1))
        t.refresh_from_db()
        assert t.breached is True

        svc.reply(ticket=t, body="اعتذارنا", from_support=True)
        t.refresh_from_db()
        assert t.breached is False, "رُدّ عليها ومع ذلك تُعدّ متجاوَزة"


def test_resolved_ticket_takes_no_reply(env):
    """والمغلقة لا تُستأنف — تُفتح تذكرةٌ جديدة."""
    with account_scope(env["account_id"]):
        t = svc.open_ticket(company=env["comp"], person=env["person"],
                            subject="عطل", body="شرح",
                            screenshot_url="/f/x.png")
        svc.resolve(ticket=t)
        with pytest.raises(svc.TicketError):
            svc.reply(ticket=t, body="إضافة", from_support=False,
                      person=env["person"])


def test_ticket_numbers_do_not_repeat(env):
    """والأرقام لا تتكرّر — فالرقم مرجع التذكرة."""
    with account_scope(env["account_id"]):
        nums = {svc.open_ticket(
            company=env["comp"], person=env["person"], subject="ع",
            body="ش", screenshot_url="/f/x.png").ticket_no
            for _ in range(3)}
        assert len(nums) == 3, nums
