"""
ربط سياق الحساب بطلبات HTTP.

مصيدتان محلولتان هنا:

1) جدول العضوية محمي بـRLS والـmiddleware يحتاج قراءته ليضبط السياق
   — حلقة مغلقة. تُكسر بدالتي SECURITY DEFINER + SET row_security=off
   (accounts/migrations/0007).

2) ATOMIC_REQUESTS يفتح المعاملة حول الـview فقط، فـSET LOCAL المضبوط
   في الـmiddleware يسقط قبل وصول الطلب. الحل: نفتح المعاملة هنا
   ونبقيها مفتوحة طوال الطلب، فتصير معاملة الـview متداخلة معها.

راجع الوثيقة المعمارية (2) القسم 2.1.
"""
from django.db import connection, transaction

from apps.core.tenancy.context import AccountContext, apply_context

EXEMPT_PREFIXES = ("/health", "/static/", "/media/", "/admin/",
                   "/api/schema", "/api/docs")


class AccountContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(EXEMPT_PREFIXES):
            return self.get_response(request)

        ctx = self._resolve(request)
        if ctx is None:
            # بلا سياق: الطلب يمضي والاستعلامات ترجع فارغة (fail closed)
            return self.get_response(request)

        request.account_ctx = ctx
        # المعاملة تُفتح هنا لا في الـview، وإلا سقط SET LOCAL قبل وصوله
        with transaction.atomic():
            apply_context(ctx)
            return self.get_response(request)

    @staticmethod
    def _user_of(request):
        # المستخدم من الجلسة أو من رمز الدخول (ق-53).
        # مصادقة DRF تعمل داخل الـview لا في الوسائط، فالوسيط
        # لا يرى مستخدم الرمز إن لم يحلّه بنفسه.
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return user
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return None
        from apps.accounts.services.auth_tokens import resolve
        return resolve(header[7:].strip())

    @classmethod
    def _resolve(cls, request):
        user = cls._user_of(request)
        if user is None:
            return None

        with connection.cursor() as cur:
            cur.execute(
                "SELECT membership_id, account_id, active_company_id,"
                "       is_account_owner, account_status"
                " FROM app_lookup_membership(%s)",
                [user.id],
            )
            row = cur.fetchone()
            if row is None:
                return None
            membership_id, account_id, active_company_id, _owner, _status = row

            cur.execute("SELECT app_lookup_company_ids(%s)", [membership_id])
            company_ids = cur.fetchone()[0] or []

        return AccountContext(
            account_id=account_id,
            company_ids=list(company_ids),
            active_company_id=active_company_id,
            user_id=user.id,
        )
