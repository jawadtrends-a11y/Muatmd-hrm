"""
مهام الطلبات الدورية.
"""
from celery import shared_task


@shared_task(name="leaves.escalate_overdue")
def escalate_overdue_task():
    """
    ينقل الطلبات المتأخرة للدرجة التالية (ق-87).

    يعمل كل ساعة: المهل بالساعات، وفحصها كل دقيقة إسراف وكل يوم
    تأخير.
    """
    from apps.accounts.models import Account
    from apps.core.tenancy.context import account_scope
    from apps.leaves.services.approvals import escalate_overdue

    total = 0
    for acc_id in Account.objects.values_list("id", flat=True):
        with account_scope(acc_id):
            total += escalate_overdue().get("escalated", 0)
    return {"escalated": total}
