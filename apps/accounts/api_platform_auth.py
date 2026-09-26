"""
مصادقة لوحة المنصة والانتحال (ق-51).

مسارات /platform/* — معزولة عن مسارات العملاء بالوسيط.
"""
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.services.platform import auth
from apps.accounts.services.platform import impersonation as imp

SECURE_COOKIE = True      # HTTPS فقط في الإنتاج


def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return (fwd.split(",")[0].strip() if fwd
            else request.META.get("REMOTE_ADDR"))


def _set_session_cookie(response, token, hours):
    response.set_cookie(
        auth.COOKIE_NAME, token, max_age=hours * 3600,
        # ⚠️⚠️ **`Strict` يمنع إرسال الكوكي بعد أيّ تنقّلٍ من خارج الصفحة** —
        # فيدخل المستخدم، ثم يُحوّله التطبيق للوحة، **فلا يُرسل الكوكي**
        # ويُطرد فورًا لصفحة الدخول. و`Lax` يحمي من CSRF بالقدر نفسه
        # لطلبات POST، ويسمح بالتنقّل العاديّ.
        httponly=True, secure=SECURE_COOKIE, samesite="Lax",
        path="/")
    return response


# ══════════ الدخول ══════════

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def platform_login(request):
    """
    دخول لوحة المنصة — خطوتان عند تفعيل التحقق الثنائي.
    """
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    totp = request.data.get("totp_code")

    if not username or not password:
        return Response({"detail": "اسم المستخدم وكلمة المرور مطلوبان"},
                        status=400)

    try:
        user, session = auth.authenticate(
            username=username, password=password, totp_code=totp,
            ip=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""))
    except auth.TotpRequired as e:
        return Response({
            "detail": "أدخل رمز التحقق من تطبيق المصادقة",
            "code": "totp_required",
            "challenge": e.challenge_token,
        }, status=401)
    except auth.AuthError as e:
        return Response({"detail": str(e), "code": "auth_failed"},
                        status=401)

    response = Response({
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "role_label": user.get_role_display(),
            "capabilities": user.capabilities,
            "totp_enabled": user.totp_enabled,
        },
        "expires_at": session.expires_at,
    })
    return _set_session_cookie(response, session.token, auth.SESSION_HOURS)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def platform_logout(request):
    token = request.COOKIES.get(auth.COOKIE_NAME)
    if token:
        auth.logout(token)
    response = Response({"logged_out": True})
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    response.delete_cookie(imp.COOKIE_NAME, path="/")
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def platform_me(request):
    """المستخدم الحالي وقدراته — تبني الواجهة عليها."""
    user = getattr(request, "platform_user", None)
    if user is None:
        return Response({"detail": "غير مسجّل الدخول"}, status=401)

    session = imp.resolve_impersonation(
        request.COOKIES.get(imp.COOKIE_NAME))

    return Response({
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "role_label": user.get_role_display(),
        "capabilities": user.capabilities,
        "totp_enabled": user.totp_enabled,
        "last_login_at": user.last_login_at,
        "impersonating": imp.banner_for(session) if session else None,
    })


# ══════════ التحقق الثنائي ══════════

@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def platform_totp_setup(request):
    """
    إعداد التحقق الثنائي — إلزامي (ق-51).

    GET يعطي الرابط للرمز المربّع، وPOST يفعّله بعد تأكيد رمز صحيح.
    """
    user = getattr(request, "platform_user", None)
    if user is None:
        return Response({"detail": "غير مسجّل الدخول"}, status=401)

    if request.method == "GET":
        if user.totp_enabled:
            return Response({"enabled": True,
                             "detail": "مفعّل بالفعل"})
        if not user.totp_secret:
            user.totp_secret = auth.generate_totp_secret()
            user.save(update_fields=["totp_secret", "updated_at"])
        return Response({
            "enabled": False,
            "secret": user.totp_secret,
            "otpauth_uri": auth.totp_uri(user),
            "note": "امسح الرمز بتطبيق المصادقة ثم أكّد برمز منه",
        })

    try:
        auth.enable_totp(user, request.data.get("code", ""))
    except auth.AuthError as e:
        return Response({"detail": str(e)}, status=400)
    return Response({"enabled": True})


# ══════════ الانتحال ══════════

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def impersonate_start(request, account_id):
    """
    يبدأ جلسة دعم فني في حساب عميل (ق-51).

    القراءة مفتوحة، والكتابة تحتاج ترويسة تأكيد في كل عملية.
    """
    user = getattr(request, "platform_user", None)
    if user is None:
        return Response({"detail": "غير مسجّل الدخول"}, status=401)

    try:
        session = imp.start_impersonation(
            platform_user=user, account_id=account_id,
            reason=request.data.get("reason", ""),
            as_role=request.data.get("as_role", ""),
            company_id=request.data.get("company_id"),
            ip=_client_ip(request))
    except imp.ImpersonationError as e:
        return Response({"detail": str(e), "code": "impersonation_denied"},
                        status=403)

    # ق-220: ⚠️⚠️ **والرمز يُرجع للوحة**: فالكوكي على نطاقها
    # **لا يصل نطاق العميل** — فاللوحة تفتح شاشته به، ونظامه
    # يُبدّله رمزَ دخول.
    response = Response({**imp.banner_for(session),
                         "token": session.token})
    response.set_cookie(
        imp.COOKIE_NAME, session.token,
        max_age=imp.IMPERSONATION_HOURS * 3600,
        httponly=True, secure=SECURE_COOKIE, samesite="Lax", path="/")
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def impersonate_end(request):
    """ينهي جلسة الدعم."""
    token = request.COOKIES.get(imp.COOKIE_NAME)
    session = imp.end_impersonation(token) if token else None

    response = Response({
        "ended": session is not None,
        "writes": session.writes_count if session else 0,
    })
    response.delete_cookie(imp.COOKIE_NAME, path="/")
    return response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def impersonation_status(request):
    """
    حالة الانتحال — تُقرأ في كل شاشة لعرض الشريط الأحمر.
    """
    session = getattr(request, "impersonation", None)
    if session is None:
        return Response({"active": False})
    return Response(imp.banner_for(session))


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@csrf_exempt
def impersonate_claim(request):
    """
    يُبدّل رمزَ جلسةِ الدعم برمزِ دخولٍ في نظام العميل (ق-220).

    ⚠️⚠️ **وكوكي اللوحة لا يصل نطاق العميل**: فالجلسة كانت
    تُسجَّل **والشريط يظهر**، **والدخول لا يقع** — فاللوحة تُحدّث
    نفسها ولا تنقل أحدًا.

    **فاللوحة تفتح نطاق العميل برمزٍ في الرابط، والنظام يُبدّله
    هنا** — ولا يعتمد على نطاقٍ مشترك.

    ⚠️ **والرمز يُستهلك مرّةً**: فرابطٌ يُعاد استعماله **بابٌ بلا
    قفل**.
    """
    from apps.accounts.models_access import AccountMembership
    from apps.accounts.services import auth_tokens as auth
    from apps.accounts.services.platform import impersonation as imp

    token = (request.data.get("token") or "").strip()
    session = imp.resolve_impersonation(token)
    if session is None:
        return Response({"detail": "جلسة الدعم منتهية أو غير صحيحة",
                         "code": "invalid_session"}, status=403)

    # ⚠️ **ويُدخل بحساب مالك الحساب**: فهو **أوسع صلاحيةً**،
    # والدور المطلوب يُقيّده في الجلسة.
    # ⚠️⚠️ **وسياسة العزل تحجب العضوية عمّن لا سياق له** (ق-107):
    # **والعلّة نفسها للمرّة السابعة** — فكلُّ قراءةٍ في خدمات
    # اللوحة **تحتاج سياقها**.
    from apps.core.tenancy.context import account_scope

    with account_scope(session.account_id):
        m = (AccountMembership.objects
             .filter(account_id=session.account_id,
                     is_account_owner=True)
             .select_related("user").first())
        if m is None:
            m = (AccountMembership.objects
                 .filter(account_id=session.account_id)
                 .select_related("user").first())
    if m is None:
        return Response({"detail": "لا مستخدمَ في هذا الحساب"},
                        status=404)

    raw, _tok = auth.issue_for_impersonation(
        user=m.user, ip=_client_ip(request))

    return Response({
        "token": raw,
        "banner": imp.banner_for(session),
    })
