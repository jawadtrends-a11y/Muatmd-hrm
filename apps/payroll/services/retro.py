"""
التسويات الرجعية (ق-69).

طلب يُعتمد بعد إغلاق مسير شهره يترك فرقًا. والفرق يُحتسب بإعادة
حساب الشهر بالبيانات المصححة — لا بردّ الخصم كاملًا: موظف تأخر
ساعة ونسي بصمته ساعتين يعود له أجر ساعة لا ساعتين.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.payroll.models import (PayrollRun, PayrollRunStatus, RetroAdjustment,
                                 RetroSource, RetroStatus)


class RetroError(ValueError):
    """خطأ في التسوية الرجعية — رسالة تخبر بما يُفعل."""


def closed_run_for(*, company, year, month):
    """مسير الشهر إن كان مغلقًا — وإلا None."""
    return PayrollRun.objects.filter(
        company=company, period_year=year, period_month=month,
        status=PayrollRunStatus.APPROVED).first()


def can_reopen(run, settings_obj):
    """
    هل يُعاد فتح المسير؟

    المهلة تُقاس من اعتماده: بعدها لا يُمسّ (ق-44) وتصير التسوية
    في المسير التالي حتمًا.
    """
    if run is None:
        return False
    hours = getattr(settings_obj, "retro_reopen_hours", 48) or 48
    closed_at = run.approved_at or run.updated_at
    if closed_at is None:
        return False
    return timezone.now() - closed_at <= timedelta(hours=hours)


@transaction.atomic
def record_adjustment(*, employment, year, month, source,
                      amount_before, amount_after, reason_ar="",
                      source_request=None, actor=None):
    """
    يسجّل فرقًا مستحقًا عن شهر أُغلق مسيره.

    ويحفظ القيمتين — قبل وبعد — لا الفرق وحده: من يراجع بعد سنة
    يحتاج معرفة كيف حُسب (ق-80).
    """
    before = Decimal(str(amount_before))
    after = Decimal(str(amount_after))
    diff = after - before

    if diff == 0:
        return None      # لا فرق — لا تسوية

    adj = RetroAdjustment.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        employment=employment,
        period_year=year, period_month=month,
        source=source, source_request=source_request,
        amount_before=before, amount_after=after, amount=diff,
        reason_ar=reason_ar or _default_reason(source, diff),
    )

    from apps.core.services.audit import log_create
    log_create(
        instance=adj, actor=actor, label=employment.employee_no,
        summary=(f"تسوية رجعية {year}/{month:02d}: "
                 f"{'استحقاق' if diff > 0 else 'استرداد'} {abs(diff)}"),
        channel="web")
    return adj


def _default_reason(source, diff):
    label = dict(RetroSource.choices).get(source, "تعديل")
    return f"{label} — {'فرق مستحق' if diff > 0 else 'فرق مسترد'}"


def pending_for_run(*, company, year, month):
    """
    التسويات التي تنتظر الإدراج في مسير يُعدّ الآن.

    تظهر لموظف الموارد تلقائيًا، فيدمجها أو يؤجّلها أو يلغيها
    (ق-69).
    """
    return RetroAdjustment.objects.filter(
        company=company, status=RetroStatus.PENDING,
    ).exclude(
        # لا تُدرج تسوية شهر في مسير الشهر نفسه
        period_year=year, period_month=month,
    ).select_related("employment__person")


@transaction.atomic
def merge_into_run(*, adjustments, run, actor=None):
    """يدمج التسويات في مسير قيد الإعداد."""
    if run.status not in (PayrollRunStatus.DRAFT,
                          PayrollRunStatus.CALCULATED):
        raise RetroError(
            f"المسير {run.get_status_display()} — لا تُدرج فيه تسويات")

    n = 0
    for adj in adjustments:
        if adj.status != RetroStatus.PENDING:
            continue
        adj.status = RetroStatus.MERGED
        adj.merged_run = run
        adj.decided_by_person_id = getattr(actor, "id", None)
        adj.decided_at = timezone.now()
        adj.save(update_fields=["status", "merged_run",
                                "decided_by_person_id", "decided_at",
                                "updated_at"])
        n += 1
    return n


@transaction.atomic
def decide_adjustment(*, adjustment, action, actor=None, note=""):
    """
    موظف الموارد يؤجّل التسوية أو يلغيها.

    التأجيل يبقيها معلّقة لمسير لاحق، والإلغاء ينهيها.
    """
    if adjustment.status != RetroStatus.PENDING:
        raise RetroError(
            f"التسوية {adjustment.get_status_display()} — لا يُعاد القرار")

    if action not in ("defer", "cancel"):
        raise RetroError("الإجراء إما تأجيل أو إلغاء")

    adjustment.status = (RetroStatus.DEFERRED if action == "defer"
                         else RetroStatus.CANCELLED)
    adjustment.decided_by_person_id = getattr(actor, "id", None)
    adjustment.decided_at = timezone.now()
    adjustment.note = note
    adjustment.save(update_fields=["status", "decided_by_person_id",
                                   "decided_at", "note", "updated_at"])

    from apps.core.services.audit import log_action
    log_action(
        instance=adjustment, action="update", actor=actor,
        label=adjustment.employment.employee_no,
        summary=("أُجّلت التسوية" if action == "defer" else "أُلغيت التسوية"),
        channel="web")
    return adjustment


def revive_deferred(*, company):
    """المؤجَّلة تعود معلّقة عند إعداد المسير التالي."""
    return RetroAdjustment.objects.filter(
        company=company, status=RetroStatus.DEFERRED
    ).update(status=RetroStatus.PENDING)
