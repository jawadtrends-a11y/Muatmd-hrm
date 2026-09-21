"""
الاستبعاد اليدوي من المسير (ق-228).

⚠️⚠️ **والاستبعاد والإعادة كلاهما يُعيد احتساب المسير**: فالمسير
يحفظ إجمالياته (العدد والإجمالي والصافي) — **واستبعادٌ بلا احتسابٍ
يترك الملخّص يكذب**. والمحرّك وحده يكتب الحقيقة.
"""
from django.db import transaction
from django.utils import timezone

from apps.payroll.models import Payslip
from apps.payroll.models_exclusion import ExclusionScope, PayrollExclusion

EDITABLE = {"draft", "calculated", "failed"}


class ExclusionError(Exception):
    """رسالةٌ تُسمّي المطلوب."""


def _guard(run):
    if run.status not in EDITABLE:
        raise ExclusionError(
            "المسير مرفوعٌ أو معتمد — لا يُستبعد منه أحد ولا يُعاد إليه")


@transaction.atomic
def exclude(*, run, employment, scope, reason, by_person_id=None):
    from apps.payroll.services.engine import calculate_run

    _guard(run)
    reason = (reason or "").strip()
    if not reason:
        raise ExclusionError("سبب الاستبعاد مطلوب")
    if scope not in ExclusionScope.values:
        raise ExclusionError("نطاق الاستبعاد غير معروف")
    if employment.company_id != run.company_id:
        raise ExclusionError("الموظف من شركةٍ أخرى")

    active = PayrollExclusion.objects.filter(
        employment=employment, revoked_at__isnull=True)
    if active.filter(scope=ExclusionScope.UNTIL_REVOKED).exists() or \
            active.filter(scope=ExclusionScope.RUN, run=run).exists():
        raise ExclusionError("الموظف مستبعَدٌ أصلًا")

    ex = PayrollExclusion.objects.create(
        account_id=run.account_id, company_id=run.company_id,
        employment=employment, scope=scope,
        run=run if scope == ExclusionScope.RUN else None,
        reason=reason[:255], excluded_by_person_id=by_person_id)

    Payslip.objects.filter(run=run, employment=employment).delete()
    calculate_run(run)
    return ex


@transaction.atomic
def revoke(*, exclusion, run, by_person_id=None):
    """⚠️ **الإعادة لا تحذف** — تُسجَّل بفاعلها وتاريخها (ق-44)."""
    from apps.payroll.services.engine import calculate_run

    _guard(run)
    if exclusion.revoked_at:
        raise ExclusionError("أُعيد الموظف أصلًا")
    exclusion.revoked_at = timezone.now()
    exclusion.revoked_by_person_id = by_person_id
    exclusion.save(update_fields=["revoked_at", "revoked_by_person_id",
                                  "updated_at"])
    calculate_run(run)
    return exclusion
