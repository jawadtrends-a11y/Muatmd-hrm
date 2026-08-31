"""
وسيط لوحة المنصة (ق-51).

يفصل المسارين بنيويًا:
  • /platform/*  — جلسة منصة فقط، وجلسة عميل تُرفض
  • بقية المسارات — جلسة عميل، أو جلسة انتحال بضوابطها

الفصل هنا لا في كل نقطة: مسار واحد للتحقق يعني ثغرة واحدة
محتملة لا أربعين.
"""
import logging

from django.http import JsonResponse

from apps.accounts.services.platform import auth as platform_auth
from apps.accounts.services.platform import impersonation as imp

logger = logging.getLogger("muatmd.platform")

PLATFORM_PREFIX = "/platform/"

# مسارات المنصة المفتوحة بلا جلسة
PLATFORM_PUBLIC = {
    "/platform/auth/login",
    "/platform/auth/totp",
}


class PlatformAuthMiddleware:
    """
    يضع request.platform_user و request.impersonation.

    ولا يسمح بتداخل الجلستين: من يدخل لوحة المنصة لا يحمل جلسة
    عميل، ومن يتصفح كعميل لا يصل لمسارات اللوحة.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.platform_user = None
        request.impersonation = None

        is_platform_path = request.path.startswith(PLATFORM_PREFIX)

        # ── جلسة المنصة ──
        token = request.COOKIES.get(platform_auth.COOKIE_NAME)
        if token:
            request.platform_user = platform_auth.resolve_session(token)

        # ── جلسة الانتحال — تُقرأ دائمًا ──
        # داخل /platform/ لعرض الشريط، وخارجه لتطبيق السياق
        imp_token = request.COOKIES.get(imp.COOKIE_NAME)
        if imp_token:
            session = imp.resolve_impersonation(imp_token)
            if session is not None:
                request.impersonation = session
                if not is_platform_path:
                    logger.info("impersonated_request", extra={
                        "platform_user": session.platform_user.username,
                        "account_id": session.account_id,
                        "path": request.path,
                        "method": request.method})

        if is_platform_path:
            if request.path.rstrip("/") in PLATFORM_PUBLIC:
                return self.get_response(request)
            if request.platform_user is None:
                return JsonResponse(
                    {"detail": "يلزم الدخول للوحة المنصة",
                     "code": "platform_auth_required"}, status=401)

        return self.get_response(request)


class ImpersonationGuardMiddleware:
    """
    يحرس الكتابة أثناء الانتحال (ق-46).

    القراءة مفتوحة، والكتابة تحتاج ترويسة تأكيد صريحة — فلا
    يعدّل السوبر أدمن بالخطأ وهو يظن نفسه في حسابه.

    يجب أن يلي PlatformAuthMiddleware.
    """

    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    CONFIRM_HEADER = "HTTP_X_IMPERSONATION_CONFIRM"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = getattr(request, "impersonation", None)
        if session is None:
            return self.get_response(request)

        # مسارات اللوحة نفسها ليست كتابة في بيانات العميل —
        # إنهاء الانتحال مثلًا يجب ألا يطلب تأكيدًا
        if request.path.startswith(PLATFORM_PREFIX):
            return self.get_response(request)

        if request.method in self.WRITE_METHODS:
            confirmed = request.META.get(self.CONFIRM_HEADER, "")
            if str(confirmed).lower() not in ("1", "true", "yes"):
                return JsonResponse({
                    "detail": (f"أنت في حساب العميل «{session.account_label}» "
                               "— أكّد العملية للمتابعة"),
                    "code": "impersonation_confirm_required",
                    "account": session.account_label,
                    "warning": "كل تعديل يُسجَّل باسمك ويظهر للعميل",
                }, status=428)

            imp.record_write(
                session,
                action=f"{request.method.lower()}:{request.path}",
                detail={"method": request.method, "path": request.path})

        response = self.get_response(request)

        # الشريط الأحمر — يمنع نسيان السياق
        response["X-Impersonation"] = session.account_label
        response["X-Impersonation-Minutes-Left"] = str(session.minutes_left)
        return response
