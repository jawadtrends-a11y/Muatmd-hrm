"""
أنشطة العمل اليومية (ق-143).

⚠️ **والأثر الماليّ لا يقع بإقرار الموظف وحده** — بل بمراجعةٍ
يعتمدها المدير.
"""
import logging
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ZERO = Decimal("0")

#: ⚠️ تنبيهٌ نظاميّ يُحمَل مع كل حسم
DEDUCTION_WARNING = (
    "⚠️ الحسم من الأجر لا يكون نظامًا إلا وفق لائحة الجزاءات "
    "(المادة ٧١): مخالفةٌ محدّدة، وتحقيق، وإشعار. وحسمُ التقصير "
    "بلا ذلك مخالفةٌ مسؤوليتها على صاحب العمل."
)


class ActivityError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


@transaction.atomic
def assign(*, employment, title, start_date, end_date, description="",
           target_count=None, unit="", pay_effect="none",
           pay_basis="per_activity", bonus_amount=None,
           deduction_amount=None, by_employment_id=None,
           skip_weekends=True):
    """
    يُسند نشاطًا يوميًّا على مدًى — **سلفًا لا كل صباح**.

    ⚠️ **ويتخطّى أيام الراحة** افتراضًا: فنشاطٌ في يوم راحةٍ يبقى
    «لم يُنجَز» بلا ذنب.
    """
    from apps.attendance.models import AttendanceDay, DayStatus
    from apps.employees.models import PayEffect, WorkActivity
    from apps.payroll.models import PayrollSettings

    # ⚠️ **ثلاث طبقات**: الباقة، ثم إعدادات الشركة، ثم اختيار
    # المدير — وتفعيل الشركة لا يُلزم المديرين (قرار جواد).
    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    if st is None or not st.activities_enabled:
        raise ActivityError(
            "أنشطة العمل غير مفعَّلة — تُفعَّل من إعدادات الشركة")

    if not (title or "").strip():
        raise ActivityError("عنوان النشاط مطلوب")
    if end_date < start_date:
        raise ActivityError("نهاية المدى قبل بدايته")
    if (end_date - start_date).days > 366:
        raise ActivityError("المدى يتجاوز سنة")

    if pay_effect in (PayEffect.BONUS, PayEffect.BOTH) and not bonus_amount:
        raise ActivityError("حدّد مبلغ المكافأة")
    if (pay_effect in (PayEffect.DEDUCTION, PayEffect.BOTH)
            and not deduction_amount):
        raise ActivityError("حدّد مبلغ الحسم")
    if pay_basis == "per_unit" and not target_count:
        raise ActivityError("الاحتساب لكل وحدة يحتاج عددًا مستهدَفًا")

    batch = uuid.uuid4().hex[:16]

    rest_days = set()
    if skip_weekends:
        rest_days = set(AttendanceDay.objects.filter(
            employment=employment, work_date__gte=start_date,
            work_date__lte=end_date,
            status__in=[DayStatus.WEEKEND, DayStatus.HOLIDAY]
        ).values_list("work_date", flat=True))

    rows, day = [], start_date
    while day <= end_date:
        if day not in rest_days:
            rows.append(WorkActivity(
                account_id=employment.account_id,
                company_id=employment.company_id,
                employment=employment, work_date=day,
                title=title.strip()[:200],
                description=description or "",
                target_count=target_count, unit=unit or "",
                pay_effect=pay_effect, pay_basis=pay_basis,
                bonus_amount=bonus_amount,
                deduction_amount=deduction_amount,
                assigned_by_employment_id=by_employment_id,
                batch_key=batch))
        day += timedelta(days=1)

    if not rows:
        raise ActivityError("لا أيام عملٍ في هذا المدى")

    WorkActivity.objects.bulk_create(rows, ignore_conflicts=True)
    logger.info("أُسند نشاط «%s» لـ%s يومًا", title, len(rows))
    return {"batch_key": batch, "created": len(rows)}


@transaction.atomic
def report(*, activity, status, done_count=None, done_note="",
           pending_note=""):
    """
    إقرار الموظف آخر اليوم.

    ⚠️ **والجزئيّ والمتعذّر يُحدَّد فيهما ما أُنجز وما لم يُنجَز**
    — لا سببٌ عامّ: فالمدير يعرف العائق لا الرقم وحده (قرار جواد).
    """
    from apps.employees.models import ActivityStatus

    if activity.is_reviewed:
        raise ActivityError("رُوجع النشاط — لا يُعدَّل إقراره")
    if status not in (ActivityStatus.DONE, ActivityStatus.PARTIAL,
                      ActivityStatus.NOT_DONE):
        raise ActivityError("حالة غير معروفة")

    if status in (ActivityStatus.PARTIAL, ActivityStatus.NOT_DONE):
        if not (pending_note or "").strip():
            raise ActivityError(
                "بيّن ما لم يُنجَز — فالمدير يعرف العائق لا الرقم وحده")
    if status == ActivityStatus.PARTIAL:
        if not (done_note or "").strip():
            raise ActivityError("بيّن ما أُنجز")

    if activity.is_measurable:
        if done_count is None:
            raise ActivityError("حدّد العدد المنجَز")
        if int(done_count) > (activity.target_count or 0) * 10:
            raise ActivityError("العدد المنجَز غير معقول")
        activity.done_count = int(done_count)

    activity.status = status
    activity.done_note = (done_note or "")[:2000]
    activity.pending_note = (pending_note or "")[:2000]
    activity.reported_at = timezone.now()
    activity.save()
    return activity


def compute_amount(activity):
    """
    المبلغ المستحقّ — **موجبٌ مكافأةً وسالبٌ حسمًا**.

    ⚠️ **ولا يُحتسب لما لم يُقرّ بعد**: فنشاطٌ بانتظار الإقرار
    ليس تقصيرًا.
    """
    from apps.employees.models import ActivityStatus, PayBasis, PayEffect

    if activity.pay_effect == PayEffect.NONE:
        return ZERO
    if activity.status == ActivityStatus.PENDING:
        return ZERO

    bonus = Decimal(str(activity.bonus_amount or 0))
    deduct = Decimal(str(activity.deduction_amount or 0))

    if activity.status == ActivityStatus.DONE:
        if activity.pay_effect in (PayEffect.BONUS, PayEffect.BOTH):
            if activity.pay_basis == PayBasis.PER_UNIT:
                return bonus * Decimal(activity.done_count
                                       or activity.target_count or 0)
            return bonus
        return ZERO

    if activity.status == ActivityStatus.NOT_DONE:
        if activity.pay_effect in (PayEffect.DEDUCTION, PayEffect.BOTH):
            if activity.pay_basis == PayBasis.PER_UNIT:
                return -(deduct * Decimal(activity.target_count or 0))
            return -deduct
        return ZERO

    # جزئيّ: المكافأة بما أُنجز، والحسم بما تبقّى — وبالوحدة فقط
    if activity.pay_basis != PayBasis.PER_UNIT:
        return ZERO

    done = Decimal(activity.done_count or 0)
    target = Decimal(activity.target_count or 0)
    out = ZERO
    if activity.pay_effect in (PayEffect.BONUS, PayEffect.BOTH):
        out += bonus * done
    if activity.pay_effect in (PayEffect.DEDUCTION, PayEffect.BOTH):
        out -= deduct * max(target - done, ZERO)
    return out


@transaction.atomic
def review(*, activity, by_person_id=None, note="", override=None):
    """
    مراجعة المدير — **وبها وحدها يقع الأثر الماليّ**.

    ⚠️ فمالٌ يُصرف أو يُحسم بقول صاحبه بلا مراجعة — والمراجعة هي
    الضابط.
    """
    from apps.employees.models import ActivityStatus

    if activity.status == ActivityStatus.PENDING:
        raise ActivityError("لم يُقرَّ النشاط بعد")
    if activity.is_reviewed:
        raise ActivityError("رُوجع بالفعل")

    amount = (Decimal(str(override)) if override is not None
              else compute_amount(activity))

    activity.is_reviewed = True
    activity.reviewed_by_person_id = by_person_id
    activity.reviewed_at = timezone.now()
    activity.review_note = (note or "")[:255]
    activity.settled_amount = amount
    activity.save(update_fields=[
        "is_reviewed", "reviewed_by_person_id", "reviewed_at",
        "review_note", "settled_amount", "updated_at"])
    return activity


def pending_amount(employment, year, month):
    """ما رُوجع ولم يدخل المسير — لشهرٍ بعينه."""
    from django.db.models import Sum

    from apps.employees.models import WorkActivity

    return WorkActivity.objects.filter(
        employment=employment, is_reviewed=True, is_paid=False,
        work_date__year=year, work_date__month=month
    ).aggregate(t=Sum("settled_amount"))["t"] or ZERO
