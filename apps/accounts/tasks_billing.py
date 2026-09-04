"""
مهام الفوترة المجدولة (ق-48).

التجديد التلقائي خيار يفعّله العميل، وعند الفشل ثلاث محاولات
(الاستحقاق، +12 ساعة، +24 ساعة) ثم إشعار صريح.
"""
import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("muatmd.billing")


@shared_task(name="billing.evaluate_subscriptions")
def evaluate_subscriptions():
    """
    مهمة يومية: تحدّث حالات الاشتراكات حسب التواريخ.

    التجربة تنتهي لقراءة، والاشتراك يمر بمهلة ثلاثة أيام ثم قراءة.
    """
    from apps.accounts.models_billing_v2 import AccountSubscription
    from apps.accounts.services.billing_v2 import evaluate_state
    from apps.core.tenancy.context import account_scope

    changed = 0
    for sub_id, acc_id in AccountSubscription.objects.values_list(
            "id", "account_id"):
        with account_scope(acc_id):
            sub = AccountSubscription.objects.filter(id=sub_id).first()
            if sub is None:
                continue
            result = evaluate_state(sub)
            if result:
                changed += 1
                logger.info("subscription_state_changed", extra={
                    "account_id": acc_id, "state": sub.state,
                    "reason": result})
    return {"evaluated": True, "changed": changed}


@shared_task(name="billing.send_renewal_alerts")
def send_renewal_alerts():
    """
    التنبيه قبل الانتهاء: 5 أيام للشهري و15 للسنوي (ق-48).

    يظهر لمالك الحساب ومديري الموارد البشرية.
    """
    from apps.accounts.models_billing_v2 import (
        AccountSubscription, SubscriptionState,
    )
    from apps.accounts.services.billing_v2 import renewal_alert_due
    from apps.core.tenancy.context import account_scope
    from apps.notifications.bus import emit

    sent = 0
    qs = AccountSubscription.objects.filter(state=SubscriptionState.ACTIVE)
    for sub_id, acc_id in qs.values_list("id", "account_id"):
        with account_scope(acc_id):
            sub = AccountSubscription.objects.filter(id=sub_id).first()
            if sub is None or not renewal_alert_due(sub):
                continue
            days = (sub.current_period_end - date.today()).days
            emit("subscription.renewal_due", account_id=acc_id,
                 company_id=None,
                 context={
                     "days_left": days,
                     "end_date": str(sub.current_period_end),
                     "cycle": sub.get_cycle_display(),
                     "auto_renew": sub.auto_renew,
                  "link_url": "/settings"},
                 recipients=[])
            sent += 1
    return {"alerts_sent": sent}


@shared_task(name="billing.run_auto_renewals")
def run_auto_renewals():
    """
    التجديد التلقائي لمن فعّله (ق-48).

    ينشئ الفاتورة ويشحن البطاقة المحفوظة. الفشل يجدول محاولة
    تالية بدل أن يوقف الحساب فورًا.
    """
    from apps.accounts.models_billing_v2 import (
        AccountSubscription, PaymentStatus, SubscriptionState,
    )
    from apps.accounts.services.billing_v2 import create_invoice, issue_invoice
    from apps.accounts.services.payments.service import charge_saved_card
    from apps.core.tenancy.context import account_scope

    today = date.today()
    due = AccountSubscription.objects.filter(
        state=SubscriptionState.ACTIVE, auto_renew=True,
        next_billing_date__lte=today, saved_card__isnull=False)

    results = {"attempted": 0, "paid": 0, "failed": 0}
    for sub_id, acc_id in due.values_list("id", "account_id"):
        with account_scope(acc_id):
            sub = AccountSubscription.objects.filter(id=sub_id).first()
            if sub is None or sub.saved_card is None:
                continue

            results["attempted"] += 1
            try:
                invoice, _ = create_invoice(
                    subscription=sub, period_start=sub.next_billing_date)
                issue_invoice(invoice)
                payment = charge_saved_card(invoice=invoice,
                                            card=sub.saved_card)
            except Exception as e:  # noqa: BLE001
                results["failed"] += 1
                logger.error("auto_renewal_error", extra={
                    "account_id": acc_id, "error": str(e)})
                continue

            if payment.status == PaymentStatus.PAID:
                results["paid"] += 1
            else:
                results["failed"] += 1
                retry_failed_renewal.apply_async(
                    args=[sub_id, acc_id, invoice.id, 1],
                    countdown=12 * 3600)
    return results


@shared_task(name="billing.retry_failed_renewal")
def retry_failed_renewal(subscription_id, account_id, invoice_id, attempt):
    """
    إعادة محاولة التجديد: الثانية بعد 12 ساعة، والثالثة بعد 24 (ق-48).

    بعد الثالثة إشعار صريح — لا إيقاف فوري.
    """
    from apps.accounts.models_billing_v2 import (
        AccountSubscription, Invoice, PaymentStatus,
    )
    from apps.accounts.models_platform import get_settings
    from apps.accounts.services.payments.service import charge_saved_card
    from apps.core.tenancy.context import account_scope
    from apps.notifications.bus import emit

    schedule = get_settings().auto_retry_schedule      # [12, 24]

    with account_scope(account_id):
        sub = AccountSubscription.objects.filter(id=subscription_id).first()
        invoice = Invoice.objects.filter(id=invoice_id).first()
        if sub is None or invoice is None or sub.saved_card is None:
            return {"skipped": True}
        if invoice.status == "paid":
            return {"already_paid": True}

        payment = charge_saved_card(invoice=invoice, card=sub.saved_card)
        if payment.status == PaymentStatus.PAID:
            return {"attempt": attempt, "paid": True}

        if attempt < len(schedule):
            retry_failed_renewal.apply_async(
                args=[subscription_id, account_id, invoice_id, attempt + 1],
                countdown=schedule[attempt] * 3600)
            return {"attempt": attempt, "rescheduled": True}

        # استُنفدت المحاولات — إشعار صريح (ق-48)
        emit("subscription.renewal_failed", account_id=account_id,
             company_id=None,
             context={
                 "invoice_no": invoice.invoice_no,
                 "amount": str(invoice.total),
                 "attempts": attempt,
                 "reason": payment.failure_message,
                  "link_url": "/settings"},
             recipients=[])
        logger.warning("auto_renewal_exhausted", extra={
            "account_id": account_id, "invoice_id": invoice_id})
        return {"attempt": attempt, "exhausted": True}


@shared_task(name="billing.snapshot_headcount")
def snapshot_headcount():
    """
    لقطة يومية لعدد الموظفين — أساس الفوترة بالذروة (ق-49).

    بلا هذه اللقطات لا نعرف الذروة، فيصير الاحتساب على عدد يوم
    الفاتورة وهو قابل للتحايل.
    """
    from apps.accounts.models import Account, Company, CompanyHeadcountDaily
    from apps.core.tenancy.context import account_scope
    from apps.employees.models import Employment, EmploymentStatus

    today = date.today()
    count = 0
    for acc_id in Account.objects.values_list("id", flat=True):
        with account_scope(acc_id):
            for comp_id in Company.objects.filter(
                    account_id=acc_id).values_list("id", flat=True):
                n = Employment.objects.filter(
                    company_id=comp_id,
                    status=EmploymentStatus.ACTIVE).count()
                CompanyHeadcountDaily.objects.update_or_create(
                    company_id=comp_id, snapshot_date=today,
                    defaults={"account_id": acc_id,
                              "billable_employments": n})
                count += 1
    return {"snapshots": count, "date": str(today)}
