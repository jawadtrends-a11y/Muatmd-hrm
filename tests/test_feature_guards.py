"""
حرّاس بوّابة المزايا عند أبوابها (ق-123).

⚠️ **الميزة بلا حارس تسويقُ وهم**: تُباع في الباقة ويستعملها من
لم يشترها. فكل ميزة تُفحص عند بابها — في الخدمة لا في الشاشة،
فإخفاء الزرّ تحسينُ عرضٍ لا حماية.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.models_billing import Plan, PlanFeature, PlanPriceTier
from apps.accounts.models_billing_v2 import (
    AccountSubscription, BillingCycle, SubscriptionState)
from apps.accounts.services.provisioning import provision_account
from apps.core.features.gate import Features, FeatureNotInPlan
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import RequestType
from apps.leaves.services.requests import create_request


def _plan(code, keys, order):
    p = Plan.objects.create(code=code, name_ar=code, tier_order=order,
                            base_fee_monthly=Decimal("0"),
                            min_billable_employees=1)
    PlanPriceTier.objects.create(
        plan=p, from_employees=1, to_employees=None,
        price_per_employee_monthly=Decimal("15"),
        price_per_employee_yearly=Decimal("180"))
    PlanFeature.objects.bulk_create(
        [PlanFeature(plan=p, feature_key=k, value="true") for k in keys])
    return p


@pytest.fixture
def env(db):
    from apps.payroll.models import PayComponent

    small = _plan("g-small", ["req_leave", "req_permission"], 1)
    big = _plan("g-big", ["req_leave", "req_permission", "req_advance"], 2)

    r = provision_account(slug="guards", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        p, _ = create_person(
            account=acc, first_name_ar="فهد", family_name_ar="الدوسري",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1055566677", mobile="0505556667")
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="G-1",
            join_date=date.today() - timedelta(days=400),
            salary_lines=[(basic, Decimal("6000"))])

        sub = AccountSubscription.objects.get(account_id=r.account_id)
        sub.plan = small
        sub.cycle = BillingCycle.MONTHLY
        sub.state = SubscriptionState.ACTIVE
        sub.current_period_start = date.today()
        sub.current_period_end = date.today() + timedelta(days=30)
        sub.save()
        Features.invalidate(comp.id)

        yield {"account_id": r.account_id, "company": comp,
               "employment": emp, "small": small, "big": big}


def test_request_type_in_plan_is_allowed(env):
    """ما فتحته باقته يُقدَّم."""
    with account_scope(env["account_id"]):
        req = create_request(
            employment=env["employment"],
            request_type=RequestType.PERMISSION,
            payload={"work_date": str(date.today()),
                     "from_time": "09:00", "to_time": "10:00",
                     "reason": "ظرف خاص"},
            note="استئذان")
        assert req is not None


def test_request_type_outside_plan_is_refused(env):
    """
    ⚠️ الأهمّ: ما لم تفتحه باقته **يُرفض** — ولو نادى المسار.

    فبلا هذا يُباع «طلب السلفة» في المميزة ويستعمله من اشترى
    الأساسية.
    """
    with account_scope(env["account_id"]):
        with pytest.raises(FeatureNotInPlan):
            create_request(
                employment=env["employment"],
                request_type=RequestType.ADVANCE,
                payload={"amount": "1000", "installments": 5},
                note="سلفة")


def test_upgrading_the_plan_opens_it(env):
    """وترقية الباقة تفتحه فورًا — فالحراسة بالباقة لا بالكود."""
    with account_scope(env["account_id"]):
        AccountSubscription.objects.filter(
            account_id=env["account_id"]).update(plan=env["big"])
        Features.invalidate(env["company"].id)

        req = create_request(
            employment=env["employment"],
            request_type=RequestType.ADVANCE,
            payload={"amount": "1000", "installments": 5},
            note="سلفة")
        assert req is not None


def test_refusal_points_to_the_right_plan(env):
    """
    والرفض يدلّ على **أصغر باقة تفتحها** — فالمنع بلا طريقٍ
    للحلّ إحباط.
    """
    from apps.core.features.gate import upgrade_hint

    with account_scope(env["account_id"]):
        # الباقات الحقيقية تُخفى — وإلا رشّحت نفسها
        Plan.objects.exclude(
            id__in=[env["small"].id, env["big"].id]).update(is_public=False)
        Plan.objects.filter(id=env["small"].id).update(is_public=True)
        Plan.objects.filter(id=env["big"].id).update(is_public=True)
        h = upgrade_hint(env["company"].id, "req_advance")
        assert h is not None
        assert h["plan_code"] == "g-big", h
