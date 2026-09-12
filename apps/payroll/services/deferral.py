"""
تأجيل بنود القسيمة (ق-136).

⚠️ **الراتب لا يُؤجَّل**: تأجيله مخالفةٌ نظامية — وإنما يُؤجَّل
بندٌ منه.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class DeferralError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


#: ⚠️ **بنودٌ لا تُؤجَّل أبدًا** — تأجيلها مخالفة أو عبث:
#
# الراتب وبدلاته أجرٌ مستحقٌّ في موعده (المادة ٩٠)، والتأمينات
# اقتطاعٌ نظاميّ لا يُؤخَّر، وحسم الغياب أثرٌ محسوب لا قرار.
NEVER_DEFERRABLE = {"BASIC", "HOUSING", "TRANSPORT",
                    "GOSI_EMPLOYEE", "GOSI_EMPLOYER",
                    "ABSENCE", "LATE", "UNPAID_LEAVE"}


def deferrable_lines(payslip):
    """
    بنود القسيمة التي **يجوز** تأجيلها.

    فالراتب وبدلاته والتأمينات وحسم الغياب خارجها — وعرضها
    للتأجيل إغراءٌ بمخالفة.
    """
    out = []
    for line in payslip.lines.all():
        code = (line.component_code or "").upper()
        if code in NEVER_DEFERRABLE:
            continue
        if code.startswith("GOSI"):
            continue
        out.append(line)
    return out


@transaction.atomic
def defer(*, payslip, component_code, to_year, to_month, reason,
          by_person_id=None):
    """
    يؤجّل بندًا من قسيمة إلى شهرٍ يُحدَّد.

    ⚠️ **وقبل الاعتماد فقط**: المسير المعتمد سجلٌّ ماليّ نهائيّ
    يُصرف عليه ويُرحَّل للمحاسبة.
    """
    from apps.payroll.models import (
        DeferralStatus, PayrollRunStatus, PayslipDeferral)

    run = payslip.run
    if run.status in (PayrollRunStatus.APPROVED, PayrollRunStatus.PAID):
        raise DeferralError(
            "المسير معتمد — لا يُؤجَّل بندٌ منه")

    code = (component_code or "").upper()
    if code in NEVER_DEFERRABLE or code.startswith("GOSI"):
        raise DeferralError(
            "الراتب وبدلاته والتأمينات لا تُؤجَّل — أجرٌ مستحقٌّ في موعده")

    line = payslip.lines.filter(component_code=component_code).first()
    if line is None:
        raise DeferralError("البند غير موجود في القسيمة")

    target = int(to_year) * 12 + int(to_month)
    current = run.period_year * 12 + run.period_month
    if target <= current:
        raise DeferralError("شهر التأجيل يجب أن يكون بعد شهر المسير")
    if not (1 <= int(to_month) <= 12):
        raise DeferralError("شهر غير صالح")

    if PayslipDeferral.objects.filter(
            payslip=payslip, component_code=component_code,
            status=DeferralStatus.PENDING).exists():
        raise DeferralError("هذا البند مؤجَّل بالفعل")

    # قسط السلفة: جدولها يمتدّ شهرًا فلا يُثقَل عليه بقسطين
    advance_id = None
    if component_code.startswith("ADVANCE_"):
        try:
            advance_id = int(component_code.split("_", 1)[1])
        except (ValueError, IndexError):
            advance_id = None

    d = PayslipDeferral.objects.create(
        account_id=payslip.account_id, company_id=payslip.company_id,
        payslip=payslip, employment=payslip.employment,
        component_code=component_code, name_ar=line.name_ar,
        line_type=line.line_type, amount=line.amount,
        from_year=run.period_year, from_month=run.period_month,
        to_year=int(to_year), to_month=int(to_month),
        reason=(reason or "")[:255], advance_id=advance_id,
        deferred_by_person_id=by_person_id)

    logger.info("أُجِّل %s من %s-%s إلى %s-%s",
                component_code, run.period_year, run.period_month,
                to_year, to_month)
    return d


@transaction.atomic
def cancel(*, deferral):
    """يلغي تأجيلًا لم يُطبَّق بعد."""
    from apps.payroll.models import DeferralStatus

    if deferral.status != DeferralStatus.PENDING:
        raise DeferralError("طُبّق أو أُلغي — لا يُعدَّل")
    deferral.status = DeferralStatus.CANCELLED
    deferral.save(update_fields=["status", "updated_at"])
    return deferral


def pending_for(company_id, year, month):
    """المؤجَّلات المستحقّة في هذا الشهر."""
    from apps.payroll.models import DeferralStatus, PayslipDeferral

    return (PayslipDeferral.objects
            .filter(company_id=company_id, to_year=year, to_month=month,
                    status=DeferralStatus.PENDING)
            .select_related("employment"))


@transaction.atomic
def mark_applied(*, deferrals, run):
    """
    يعلّم المؤجَّلات مطبَّقةً — **عند اعتماد المسير لا حسابه**.

    فمسيرٌ يُحسب ثم يُلغى لا يستهلك تأجيلًا.
    """
    from apps.payroll.models import DeferralStatus, PayslipDeferral

    ids = [d.id for d in deferrals]
    if not ids:
        return 0
    return PayslipDeferral.objects.filter(id__in=ids).update(
        status=DeferralStatus.APPLIED, applied_run_id=run.id,
        updated_at=timezone.now())
