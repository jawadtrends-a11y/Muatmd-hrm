"""
تذكير المديرين بما ينتظر قرارهم (ق-105).

**قبل نهاية فترة عمله بساعتين** — لا في وقت ثابت للجميع: من ينتهي
دوامه الثالثة يُذكَّر الواحدة، ومن ينتهي السابعة يُذكَّر الخامسة.
فالتذكير قبل انصرافه بوقت يكفي للقرار، لا بعد أن غادر.

**ومن أُعفي من البصمة** (ق-104) لا نهاية لفترته عمليًّا — فيُذكَّر
**الثالثة عصرًا** بتوقيت السعودية.

وتعمل كل ربع ساعة: نافذة الساعتين تُفحص بدقّة تكفي، وفحصها كل
دقيقة إسراف.
"""
import logging
from datetime import datetime, time, timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

EVENT_KEY = "approvals.end_of_shift_reminder"
WINDOW_MINUTES = 15
HOURS_BEFORE = 2
EXEMPT_HOUR = 15          # الثالثة عصرًا لمن لا نهاية لفترته


def _reminder_time(employment, today):
    """
    متى يُذكَّر هذا المدير اليوم — أو None إن لم يكن له وقت.
    """
    from apps.attendance.models_exemption import AttendanceExemption
    from apps.attendance.services.rules import effective_shift

    exempt = AttendanceExemption.objects.filter(
        employment=employment, is_active=True,
        start_date__lte=today).first()
    if exempt and exempt.covers(today):
        return time(EXEMPT_HOUR, 0)

    shift = effective_shift(employment, today)
    if shift is None or shift.end_time is None:
        return time(EXEMPT_HOUR, 0)

    # يوم راحة لا تذكير فيه: لا قرار يُنتظر ممّن ليس على رأس عمله
    weekday = (today.weekday() + 1) % 7
    working = set(shift.working_days or [0, 1, 2, 3, 4])
    if weekday not in working:
        return None

    end = datetime.combine(today, shift.end_time)
    return (end - timedelta(hours=HOURS_BEFORE)).time()


def _within_window(target, now_t):
    """هل حان وقته في هذه الدورة؟"""
    if target is None:
        return False
    a = target.hour * 60 + target.minute
    b = now_t.hour * 60 + now_t.minute
    return 0 <= (b - a) < WINDOW_MINUTES


@shared_task(name="leaves.remind_pending_approvals")
def remind_pending_approvals():
    """
    يذكّر كل مدير بما ينتظر قراره — قبل نهاية فترته بساعتين.
    """
    from apps.accounts.models import Account
    from apps.core.tenancy.context import account_scope
    from apps.employees.models import Employment, EmploymentStatus
    from apps.leaves.services.approvals import pending_for
    from apps.notifications.bus import emit

    now = timezone.localtime()
    today = now.date()
    now_t = now.time()
    sent = 0

    for acc_id in Account.objects.values_list("id", flat=True):
        with account_scope(acc_id):
            for emp in Employment.objects.filter(
                    status=EmploymentStatus.ACTIVE).select_related(
                        "person", "company"):
                if not _within_window(_reminder_time(emp, today), now_t):
                    continue
                count = pending_for(emp).count()
                if not count:
                    continue          # لا تذكير بلا شيء ينتظر
                emit(EVENT_KEY,
                     account_id=acc_id,
                     company_id=emp.company_id,
                     context={"count": count,
                              "count_en": count,
                              "link_url": "/me/requests"},
                     recipients=[emp.person_id])
                sent += 1

    logger.info("reminders_sent", extra={"count": sent})
    return {"reminded": sent}
