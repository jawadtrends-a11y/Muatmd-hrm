"""مهمة تشخيصية للتحقق من عمل AccountTask — تُحذف لاحقًا."""
from celery import shared_task

from apps.accounts.models import Account
from apps.core.tasks import AccountTask


@shared_task(base=AccountTask, bind=True)
def probe_isolation(self, account_id, **kwargs):
    return {
        "account_id": account_id,
        "visible_slugs": list(Account.objects.values_list("slug", flat=True)),
        "visible_count": Account.objects.count(),
    }
