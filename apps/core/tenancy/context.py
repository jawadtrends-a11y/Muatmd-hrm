"""
سياق الحساب — الطبقة الوحيدة التي تضبط عزل قاعدة البيانات.

قاعدة حاكمة: لا يُضبط app.account_id في أي مكان آخر من النظام.
راجع الوثيقة المعمارية (2) القسم 2.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.db import connection, transaction


@dataclass(frozen=True)
class AccountContext:
    account_id: int
    company_ids: list = field(default_factory=list)
    active_company_id: int | None = None
    user_id: int | None = None


def _apply(account_id, company_ids, user_id):
    """
    SET LOCAL — محلي للمعاملة، يسقط تلقائيًا عند انتهائها.
    شرط العمل مع PgBouncer في وضع transaction pooling.
    """
    with connection.cursor() as cur:
        cur.execute(
            "SELECT set_config('app.account_id', %s, TRUE),"
            "       set_config('app.company_ids', %s, TRUE),"
            "       set_config('app.user_id', %s, TRUE)",
            [
                str(account_id) if account_id else "",
                ",".join(str(c) for c in (company_ids or [])),
                str(user_id) if user_id else "",
            ],
        )


def apply_context(ctx: AccountContext):
    """يثبّت السياق على الاتصال الحالي. يتطلب وجود معاملة مفتوحة."""
    _apply(ctx.account_id, ctx.company_ids, ctx.user_id)


def clear_context():
    _apply(None, None, None)


@contextmanager
def account_scope(account_id, company_ids=None, user_id=None):
    """
    سياق يدوي للمهام الخلفية والأوامر الإدارية والاختبارات.

    الاستخدام:
        with account_scope(account.id):
            Company.objects.all()   # شركات هذا الحساب فقط
    """
    with transaction.atomic():
        _apply(account_id, company_ids, user_id)
        try:
            yield
        finally:
            _apply(None, None, None)


def current_account_id():
    """يقرأ الحساب المثبَّت فعليًا على الاتصال — للتشخيص والاختبار."""
    with connection.cursor() as cur:
        cur.execute("SELECT app_current_account_id()")
        return cur.fetchone()[0]
