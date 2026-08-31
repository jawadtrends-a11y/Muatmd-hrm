"""
انتحال جلسة العميل للدعم الفني (ق-51).

يرى السوبر أدمن ما يراه العميل بالضبط — الشاشة والصلاحيات معًا.
الجلسة مؤقتة، وكل كتابة تُسجَّل باسمه لا باسم العميل.
"""
import logging
import secrets
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from apps.accounts.models_admin import (
    ImpersonationSession, PlatformAuditLog, PlatformUser,
)

logger = logging.getLogger("muatmd.platform")

IMPERSONATION_HOURS = 1      # تنتهي تلقائيًا فلا تُنسى مفتوحة
COOKIE_NAME = "muatmd_impersonation"


class ImpersonationError(Exception):
    pass


@transaction.atomic
def start_impersonation(*, platform_user, account_id, reason="",
                        as_role="", company_id=None, ip=None):
    """
    يبدأ جلسة انتحال.

    القراءة افتراضًا — الكتابة تحتاج تأكيدًا صريحًا في كل عملية.
    """
    from apps.accounts.models import Account

    if not platform_user.can("account.impersonate"):
        raise ImpersonationError(
            f"دورك ({platform_user.get_role_display()}) لا يسمح بالدخول "
            "لحسابات العملاء")

    account = Account.objects.filter(id=account_id).first()
    if account is None:
        raise ImpersonationError("الحساب غير موجود")

    # إنهاء أي جلسة سابقة — لا جلستان معًا
    ImpersonationSession.objects.filter(
        platform_user=platform_user, ended_at__isnull=True
    ).update(ended_at=timezone.now())

    session = ImpersonationSession.objects.create(
        platform_user=platform_user, account_id=account.id,
        account_label=account.display_name_ar, company_id=company_id,
        as_role=as_role, token=secrets.token_urlsafe(48), reason=reason,
        ip_address=ip,
        expires_at=timezone.now() + timedelta(hours=IMPERSONATION_HOURS))

    PlatformAuditLog.objects.create(
        user=platform_user, user_name=platform_user.full_name,
        action="impersonation.start", target_account_id=account.id,
        target_label=account.display_name_ar, ip_address=ip,
        detail={"reason": reason, "as_role": as_role,
                "expires_at": str(session.expires_at)})

    logger.info("impersonation_started", extra={
        "platform_user": platform_user.username,
        "account_id": account.id, "reason": reason})
    return session


def resolve_impersonation(token):
    """يحوّل الرمز لجلسة نشطة — أو None."""
    if not token:
        return None
    s = ImpersonationSession.objects.filter(
        token=token).select_related("platform_user").first()
    return s if (s and s.is_active) else None


@transaction.atomic
def end_impersonation(token):
    """ينهي الجلسة ويسجّل ما جرى."""
    s = ImpersonationSession.objects.filter(
        token=token, ended_at__isnull=True).first()
    if s is None:
        return None

    s.ended_at = timezone.now()
    s.save(update_fields=["ended_at", "updated_at"])

    duration = int((s.ended_at - s.created_at).total_seconds() / 60)
    PlatformAuditLog.objects.create(
        user=s.platform_user, user_name=s.platform_user.full_name,
        action="impersonation.end", target_account_id=s.account_id,
        target_label=s.account_label,
        detail={"duration_minutes": duration, "writes": s.writes_count})
    return s


def record_write(session, *, action, target="", detail=None):
    """
    يسجّل عملية كتابة أثناء الانتحال — باسم السوبر أدمن.

    تُسجَّل مرتين: في سجل المنصة، وفي سجل عمليات المنشأة فيراها
    العميل (ق-44).
    """
    session.writes_count = models.F("writes_count") + 1
    session.save(update_fields=["writes_count", "updated_at"])

    PlatformAuditLog.objects.create(
        user=session.platform_user, user_name=session.platform_user.full_name,
        action=f"impersonation.{action}",
        target_account_id=session.account_id,
        target_label=target or session.account_label,
        detail=detail or {}, ip_address=session.ip_address)

    logger.warning("impersonation_write", extra={
        "platform_user": session.platform_user.username,
        "account_id": session.account_id, "action": action})


def banner_for(session):
    """
    الشريط الأحمر الثابت — يمنع نسيان السياق (ق-46).
    """
    return {
        "active": True,
        "account": session.account_label,
        "as_role": session.as_role or "بكامل الصلاحيات",
        "minutes_left": session.minutes_left,
        "platform_user": session.platform_user.full_name,
        "message": (f"أنت في حساب العميل «{session.account_label}» "
                    f"— للدعم الفني. تنتهي الجلسة خلال "
                    f"{session.minutes_left} دقيقة."),
        "warning": "كل تعديل يُسجَّل باسمك ويظهر للعميل",
    }
