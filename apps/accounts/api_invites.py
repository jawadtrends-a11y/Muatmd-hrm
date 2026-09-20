"""
مسارات الدعوة للانضمام (ق-94).

مساران محميّان (الدعوة الفردية والجماعية) بـemployees.invite،
ومساران مفتوحان بلا توثيق: المعاينة والقبول — فالموظف يفتح
الرابط قبل أن يملك حسابًا، ولا سبيل لتوثيقه. وحمايتهما بالرمز
نفسه: عشوائيّ ٣٢ بايت، مجزّأ في القاعدة، ينتهي في سبعة أيام.
"""
import logging

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, authentication_classes)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Company
from apps.accounts.models_invite import hash_token
from apps.accounts.services.invites import (
    InviteError, can_invite, create_invite, generate_username,
    invite_url, send_invite_email)
from apps.core.access.gate import Gate
from apps.employees.models import Person

log = logging.getLogger(__name__)

BLOCK_AR = {
    "already_has_account": "لهذا الموظف حساب دخول أصلًا",
    "no_identifier": ("لا يملك الموظف بريدًا ولا رقم هوية/إقامة/حدود "
                      "ولا جوالًا — أكمل بياناته أولًا لتتمكّن من دعوته"),
}


def _ctx(request):
    c = getattr(request, "account_ctx", None)
    return (getattr(c, "account_id", None),
            getattr(c, "active_company_id", None))


def _resolve_invite_role(request, account_id):
    """
    ق-223: الدور المختار للدعوة — أو «موظف».

    ⚠⚠ **ولا يُدعى أحدٌ بدورٍ أعلى من دور الداعي**: فبلا
    هذا **يلتفّ مديرُ إدارةٍ على القيد** بدعوة موظفٍ بدور المدير
    العام — وهو ما يمنعه إسنادُ الدور المباشر (ق-115).
    """
    from apps.accounts.models_access import Role
    from apps.employees.api import ROLE_RANK, _may_assign_roles
    from apps.accounts.services.invites import default_role

    raw_id = request.data.get("role_id")
    if not raw_id:
        return default_role(account_id)

    role = Role.objects.filter(account_id=account_id, id=raw_id).first()
    if role is None:
        raise InviteError("unknown_role", "دور غير معروف")

    may, my_rank = _may_assign_roles(request.user)
    if not may:
        raise InviteError("role_forbidden", "لا تملك إسناد الأدوار")
    if ROLE_RANK.get(role.code, 99) > my_rank:
        raise InviteError(
            "role_forbidden",
            f"لا تملك دعوة بدور «{role.name_ar}» — وهو أعلى من دورك")
    return role


def _invite_one(request, person, account_id, company_id, company):
    invite, raw = create_invite(
        person, account_id=account_id, company_id=company_id,
        role=_resolve_invite_role(request, account_id),
        invited_by_person_id=getattr(
            getattr(request.user, "person", None), "id", None))
    sent = send_invite_email(invite, person, raw,
                             company.legal_name_ar, company.legal_name_en)
    return {
        "person_id": person.id,
        "name": person.display_name,
        "role": invite.role.name_ar if invite.role else "",
        "url": invite_url(raw),
        "email_sent": sent,
        "email": (person.email or "").strip(),
        "expires_at": invite.expires_at.isoformat(),
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite_person(request, person_id):
    """دعوة موظف واحد — تُرجع الرابط لينسخه المستخدم دائمًا."""
    Gate.require(request.user, "employees.invite")
    account_id, company_id = _ctx(request)

    qs = Gate.filter_queryset(request.user, "employees.invite",
                              Person.objects.all())
    person = qs.filter(id=person_id).first()
    if person is None:
        return Response({"detail": "الموظف غير متاح"},
                        status=status.HTTP_404_NOT_FOUND)

    ok, code = can_invite(person)
    if not ok:
        return Response({"code": code, "detail": BLOCK_AR.get(code, code)},
                        status=status.HTTP_400_BAD_REQUEST)

    company = Company.objects.filter(id=company_id).first()
    try:
        return Response(_invite_one(request, person, account_id,
                                    company_id, company))
    except InviteError as e:
        return Response({"code": e.code, "detail": str(e)},
                        status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite_bulk(request):
    """
    دعوة مجموعة — {"person_ids": [...]} أو {"all": true}.

    ولا تسقط الدفعة كلّها لتعذّر واحد: كلٌّ يُبلَّغ عنه بحاله،
    فالمستخدم يرى من دُعي ومن تعذّر ولماذا.
    """
    Gate.require(request.user, "employees.invite")
    account_id, company_id = _ctx(request)

    qs = Gate.filter_queryset(request.user, "employees.invite",
                              Person.objects.all())
    if request.data.get("all"):
        people = list(qs.filter(user__isnull=True)[:500])
    else:
        ids = request.data.get("person_ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "لم تُحدَّد أسماء"},
                            status=status.HTTP_400_BAD_REQUEST)
        people = list(qs.filter(id__in=ids))

    company = Company.objects.filter(id=company_id).first()
    invited, skipped = [], []
    for p in people:
        ok, code = can_invite(p)
        if not ok:
            skipped.append({"person_id": p.id, "name": p.display_name,
                            "code": code,
                            "detail": BLOCK_AR.get(code, code)})
            continue
        try:
            invited.append(_invite_one(request, p, account_id,
                                       company_id, company))
        except InviteError as e:
            skipped.append({"person_id": p.id, "name": p.display_name,
                            "code": e.code, "detail": str(e)})

    return Response({
        "invited": invited, "skipped": skipped,
        "counts": {"invited": len(invited), "skipped": len(skipped)},
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def invite_preview(request, token):
    """معاينة الدعوة — بلا توثيق، وترجع أقلّ ما يلزم."""
    with connection.cursor() as c:
        c.execute("SELECT * FROM app_invite_preview(%s)",
                  [hash_token(token)])
        row = c.fetchone()
    if row is None:
        return Response({"valid": False, "code": "not_found"},
                        status=status.HTTP_404_NOT_FOUND)
    _id, name, co_ar, co_en, locale, usable = row
    if not usable:
        return Response({"valid": False, "code": "expired"},
                        status=status.HTTP_410_GONE)
    # ق-223: \u26a0 **وبريدٌ مطابقٌ لمستخدمٍ قائم لا يحتاج حسابًا
    # ثانيًا** (قرار جواد): فالشخص واحد — والشاشة تعرض تأكيدًا
    # لا كلمةَ مرور.
    return Response({
        "valid": True, "name": name,
        "company_ar": co_ar, "company_en": co_en or co_ar,
        "default_locale": locale,
        "existing_user": _existing_user_id(token) is not None,
    })


def _existing_user_id(token):
    """معرّف مستخدمٍ ببريد الموظف نفسه — أو None."""
    with connection.cursor() as c:
        c.execute("SELECT app_invite_existing_user(%s)", [hash_token(token)])
        row = c.fetchone()
    return row[0] if row and row[0] else None


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def invite_accept(request, token):
    """قبول الدعوة — إنشاء الحساب وربطه، ذرّيًّا."""
    password = str(request.data.get("password") or "")
    locale = request.data.get("locale") or None
    if locale not in (None, "ar", "en", "ur"):
        locale = None

    # ق-223: \u26a0\u26a0 **ومن بريده بريدُ مستخدمٍ قائم لا يُنشأ له
    # حسابٌ ثانٍ** (قرار جواد): فالبريد واحدٌ والشخص واحد —
    # **وكلمةُ المرور لا تُطلب ولا تُفحص**، والدعوة تأكيدُ استلام.
    existing = _existing_user_id(token)
    if existing is not None:
        th_e = hash_token(token)
        with transaction.atomic():
            with connection.cursor() as c:
                c.execute(
                    "SELECT ok, reason FROM app_invite_accept(%s,%s,%s)",
                    [th_e, existing, locale])
                ok_e, reason_e = c.fetchone()
            if not ok_e:
                transaction.set_rollback(True)
                code_e = {"not_found": 404, "expired": 410,
                          "already_used": 409, "already_has_account": 409}
                return Response({"accepted": False, "code": reason_e},
                                status=code_e.get(reason_e, 400))
        return Response({"accepted": True, "linked_existing": True})

    # رسائل جانغو تختلط لغةً (بعضها مترجم وبعضها لا) — فنكتبها
    # نحن بلغة واحدة واضحة، ورسالةً واحدة لا ثلاثًا متفرّقة.
    if len(password) < 8:
        return Response(
            {"code": "weak_password",
             "detail": "كلمة المرور ثمانية أحرف فأكثر",
             "detail_en": "Password must be at least 8 characters"},
            status=status.HTTP_400_BAD_REQUEST)
    if password.isdigit():
        return Response(
            {"code": "weak_password",
             "detail": "لا تجعلها أرقامًا فقط — أضف حروفًا",
             "detail_en": "Do not use digits only — add letters"},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        validate_password(password)
    except ValidationError:
        return Response(
            {"code": "weak_password",
             "detail": "كلمة المرور شائعة أو ضعيفة — اختر غيرها",
             "detail_en": "This password is too common — choose another"},
            status=status.HTTP_400_BAD_REQUEST)

    th = hash_token(token)
    with transaction.atomic():
        user = User.objects.create_user(username=generate_username(),
                                        password=password)
        with connection.cursor() as c:
            c.execute("SELECT ok, reason FROM app_invite_accept(%s,%s,%s)",
                      [th, user.id, locale])
            ok, reason = c.fetchone()
        if not ok:
            # الحساب لم يُربط بأحد — فلا نتركه معلّقًا.
            transaction.set_rollback(True)
            code = {"not_found": 404, "expired": 410,
                    "already_used": 409, "already_has_account": 409}
            return Response({"accepted": False, "code": reason},
                            status=code.get(reason, 400))

    return Response({"accepted": True,
                     "note": "أُنشئ حسابك — ادخل ببريدك أو هويتك أو جوالك"})
