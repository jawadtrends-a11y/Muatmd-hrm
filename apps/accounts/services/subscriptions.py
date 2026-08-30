"""
إدارة الاشتراكات وحساب الفوترة.

قرارات المالك (الوثيقة المعمارية 3):
  • أساس الفوترة: ذروة عدد الموظفين خلال الفترة — غير قابل للتحايل.
  • الموظف في شركتين يُحتسب مرتين.
  • التنزيل يقفل ولا يحذف.
  • الإيقاف لا يمنع التصدير أبدًا.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models_billing import (
    BillingCycle, CompanyHeadcountDaily, CompanySubscription, Plan,
    SubscriptionStatus,
)
from apps.core.features.gate import Features


class SubscriptionError(Exception):
    pass


@dataclass(frozen=True)
class BillingLine:
    company_id: int
    billed_headcount: int
    unit_price: Decimal
    base_fee: Decimal
    total: Decimal
    snapshot: dict


def _period_end(start: date, cycle: str) -> date:
    if cycle == BillingCycle.YEARLY:
        return date(start.year + 1, start.month, start.day) - timedelta(days=1)
    month = start.month + 1
    year = start.year + (1 if month > 12 else 0)
    month = 1 if month > 12 else month
    try:
        nxt = date(year, month, start.day)
    except ValueError:
        nxt = date(year, month, 28)
    return nxt - timedelta(days=1)


@transaction.atomic
def subscribe_company(*, company, plan_code: str,
                      cycle: str = BillingCycle.MONTHLY,
                      starts_on: date | None = None,
                      price_override: Decimal | None = None):
    """يُنشئ اشتراكًا للشركة. كل شركة باقتها المستقلة."""
    plan = Plan.objects.filter(code=plan_code, is_active=True).first()
    if plan is None:
        raise SubscriptionError(f"باقة غير موجودة أو معطّلة: {plan_code}")

    existing = CompanySubscription.objects.filter(
        company=company,
        status__in=[SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.PAST_DUE, SubscriptionStatus.GRACE],
    ).first()
    if existing:
        raise SubscriptionError(
            f"للشركة اشتراك قائم بالفعل: {existing.plan.code}"
        )

    start = starts_on or timezone.localdate()
    sub = CompanySubscription.objects.create(
        account=company.account, company=company, plan=plan,
        billing_cycle=cycle, status=SubscriptionStatus.TRIAL,
        starts_on=start,
        current_period_start=start,
        current_period_end=_period_end(start, cycle),
        trial_ends_on=start + timedelta(days=plan.trial_days),
        price_override_per_employee=price_override,
    )
    Features.invalidate(company.id)
    return sub


@transaction.atomic
def change_plan(*, subscription, new_plan_code: str, effective: date | None = None):
    """
    ترقية أو تنزيل. التنزيل يقفل المزايا ولا يحذف أي بيانات.
    """
    new_plan = Plan.objects.filter(code=new_plan_code, is_active=True).first()
    if new_plan is None:
        raise SubscriptionError(f"باقة غير موجودة: {new_plan_code}")

    old_plan = subscription.plan
    is_downgrade = new_plan.tier_order < old_plan.tier_order

    lost = set()
    if is_downgrade:
        old_keys = set(old_plan.features.values_list("feature_key", flat=True))
        new_keys = set(new_plan.features.values_list("feature_key", flat=True))
        lost = old_keys - new_keys

    subscription.plan = new_plan
    subscription.save(update_fields=["plan", "updated_at"])
    Features.invalidate(subscription.company_id)

    return {
        "direction": "downgrade" if is_downgrade else "upgrade",
        "from": old_plan.code,
        "to": new_plan.code,
        "locked_features": sorted(lost),   # تُقفل لا تُحذف
        "data_deleted": False,
    }


def snapshot_headcount(company, on: date | None = None) -> CompanyHeadcountDaily:
    """
    لقطة يومية لعدد الموظفين — أساس الفوترة بالذروة.
    مؤقتًا تقرأ صفرًا حتى يُبنى نموذج Employment في السبرنت 7.
    """
    day = on or timezone.localdate()
    active = 0   # TODO(السبرنت 7): Employment.objects.filter(company=..., status='active').count()

    snap, _ = CompanyHeadcountDaily.objects.update_or_create(
        company=company, snapshot_date=day,
        defaults={"account": company.account,
                  "active_employments": active,
                  "billable_employments": active},
    )
    return snap


def compute_charge(subscription, period_start=None, period_end=None) -> BillingLine:
    """
    الأساس: أعلى عدد موظفين خلال الفترة.

    لماذا الذروة لا العدد يوم الفاتورة؟ لأن الأخير قابل للتحايل
    (إيقاف الموظفين قبل الفوترة وإعادتهم بعدها). الذروة عادلة
    ومفهومة: «دفعت على 12 لأن أعلى عدد وصلته كان 12».
    """
    start = period_start or subscription.current_period_start
    end = period_end or subscription.current_period_end

    snaps = list(CompanyHeadcountDaily.objects.filter(
        company_id=subscription.company_id,
        snapshot_date__gte=start, snapshot_date__lte=end,
    ))
    if snaps:
        top = max(snaps, key=lambda s: s.billable_employments)
        peak, peak_date = top.billable_employments, top.snapshot_date
    else:
        peak, peak_date = 0, end

    plan = subscription.plan
    billable = max(peak, plan.min_billable_employees)

    if subscription.price_override_per_employee is not None:
        unit = subscription.price_override_per_employee
        tier_note = "سعر تفاوضي"
    else:
        tier = (plan.price_tiers
                .filter(from_employees__lte=billable)
                .order_by("-from_employees").first())
        if tier is None:
            raise SubscriptionError(f"لا شريحة سعر تغطي {billable} موظفًا")
        unit = (tier.price_per_employee_monthly
                if subscription.billing_cycle == BillingCycle.MONTHLY
                else (tier.price_per_employee_yearly
                      or tier.price_per_employee_monthly * 12))
        tier_note = f"شريحة {tier.from_employees}–{tier.to_employees or '∞'}"

    total = (unit * billable) + plan.base_fee_monthly

    return BillingLine(
        company_id=subscription.company_id,
        billed_headcount=billable,
        unit_price=unit,
        base_fee=plan.base_fee_monthly,
        total=total,
        snapshot={
            "peak_headcount": peak,
            "peak_date": str(peak_date),
            "min_billable": plan.min_billable_employees,
            "price_tier": tier_note,
            "plan_code": plan.code,
            "period": f"{start}..{end}",
            "formula": f"{unit} × {billable} + {plan.base_fee_monthly}",
        },
    )
