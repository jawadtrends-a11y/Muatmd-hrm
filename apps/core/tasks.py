"""
أساس المهام الخلفية — كل مهمة ترث AccountTask بلا استثناء.

الخطر: المهام تعمل خارج سياق الطلب، فبلا account_id صريح تعمل
بلا عزل. راجع الوثيقة المعمارية (2) القسم 2.2.
"""
from celery import Task
from django.db import transaction

from apps.core.tenancy.context import _apply


class MissingAccountContext(RuntimeError):
    """تُرفع حين تُستدعى مهمة بلا account_id — خطأ برمجي لا حالة تشغيل."""


class AccountTask(Task):
    """
    مهمة مربوطة بحساب. تستقبل account_id صراحةً وتضبط السياق بنفسها.

    الاستخدام:
        @shared_task(base=AccountTask, bind=True)
        def my_task(self, account_id, ...):
            ...

        my_task.apply_async(kwargs={"account_id": 5})
    """

    abstract = True

    def __call__(self, *args, **kwargs):
        account_id = kwargs.get("account_id")
        if account_id is None:
            raise MissingAccountContext(
                f"المهمة {self.name} استُدعيت بلا account_id — ممنوع تنفيذها"
            )
        company_ids = kwargs.get("company_ids") or []
        user_id = kwargs.get("user_id")

        with transaction.atomic():
            _apply(account_id, company_ids, user_id)
            try:
                return super().__call__(*args, **kwargs)
            finally:
                _apply(None, None, None)
