"""
ربط سياق الحساب بطلبات HTTP.

يحلّ الحساب من المستخدم المسجّل، ويثبّته على الاتصال قبل أي استعلام.
ATOMIC_REQUESTS=True يضمن وجود معاملة، فـSET LOCAL يعمل ويسقط تلقائيًا.

راجع الوثيقة المعمارية (2) القسم 2.1.
"""
from django.http import JsonResponse

from apps.core.tenancy.context import AccountContext, apply_context

EXEMPT_PREFIXES = ("/health", "/static/", "/media/", "/admin/", "/api/schema", "/api/docs")


class AccountContextMiddleware:
    """
    مصدر السياق الحالي: المستخدم المسجّل.
    لاحقًا (السبرنت 3) يضاف: النطاق الفرعي، ومبدّل الشركة، ورمز JWT.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(EXEMPT_PREFIXES):
            return self.get_response(request)

        ctx = self._resolve(request)
        if ctx is None:
            # لا سياق = لا بيانات. الطلب يمضي لكن الاستعلامات ترجع فارغة.
            return self.get_response(request)

        request.account_ctx = ctx
        apply_context(ctx)
        return self.get_response(request)

    @staticmethod
    def _resolve(request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        membership = getattr(user, "account_membership", None)
        if membership is None:
            return None

        return AccountContext(
            account_id=membership.account_id,
            company_ids=list(membership.company_ids or []),
            active_company_id=membership.active_company_id,
            user_id=user.id,
        )
