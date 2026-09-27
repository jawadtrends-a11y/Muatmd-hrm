"""
إعادة احتساب أيّام الحضور بأثرٍ رجعيّ (ق-٢٦٢).

⚠️⚠️ **الاحتساب يقرأ الماضي مرّةً ولا يعود إليه.** يُبنى يومُ الحضور من ثلاثة
مصادر — العطل والإجازات المعتمدة والإعفاءات — **وتُقرأ كلُّها لحظةَ الاحتساب**.
فكلّ ما يُدخَل بعدُ عن يومٍ مضى **لا يُغيّر حالته**:

- عطلةٌ تُضاف لاحقًا → اليوم يبقى **غيابًا** (اليوم الوطني: ١٤ موظفًا)
- ⭐ **إجازةٌ تُعتمد بعد يومين** → أيّامها تبقى **غيابًا**، وهو الأشيع: الموظف
  يغيب ثم يُقدّم طلبه، والمدير يعتمده بعد أيام
- إعفاءٌ يُسجَّل بأثرٍ رجعيّ → لا أثر له

⚠️ **والأثر ماليٌّ لا شكليّ**: اليوم الغائب يُنشئ **خصمًا** ويُقترح عليه **جزاء**.
فمع عشرات الموظفين تصير أخطاءً متراكمةً لا يكتشفها إلا من يراجع كل يوم.

فتُعاد المعالجة عند كل حدثٍ يمسّ الماضي — **في الخلفية** لا في الطلب، إذ قد
تشمل شركةً كاملةً لشهر.
"""
import logging
from datetime import date

logger = logging.getLogger("muatmd.attendance")


def recompute_employment(*, employment, start_date, end_date):
    """يعيد بناء أيّام موظفٍ واحد في مدى، ويُسقط خصومًا زال أساسُها."""
    from apps.attendance.services.processing import process_employment_days

    process_employment_days(employment=employment, start_date=start_date,
                            end_date=end_date, force=True)
    _drop_stale_deductions(employment, start_date, end_date)


def _drop_stale_deductions(employment, start_date, end_date):
    """
    ⚠️⚠️ **الخصم يتبع اليوم، لا يسبقه.** إعادةُ الاحتساب تُصحّح حالة اليوم —
    لكن الخصمَ المُنشأ عليه **يبقى**: ١٤ خصمًا بـ٢٧٨٤ ريالًا على يومٍ صار
    عطلةً رسميّة. فمن زال أساسُه يُحذف.

    ⚠️ **والمعتمد (`applied`) لا يُمسّ**: قرارٌ اتخذته الموارد وقد يكون دخل
    مسيرًا معتمدًا — فيُسجَّل تحذيرٌ ويُترك لقرار بشريّ، لا يُمحى بصمت.
    """
    from apps.attendance.models import AttendanceDay, DayStatus
    from apps.payroll.models import (AttendanceDeduction,
                                     AttendanceDeductionStatus)

    # أيّام لم تعد تستوجب خصمًا
    clear = set(
        AttendanceDay.objects
        .filter(employment=employment, work_date__gte=start_date,
                work_date__lte=end_date,
                status__in=[DayStatus.HOLIDAY, DayStatus.WEEKEND,
                            DayStatus.LEAVE, DayStatus.EXEMPT,
                            DayStatus.NOT_SCHEDULED, DayStatus.PRESENT])
        .values_list("work_date", flat=True))
    if not clear:
        return

    qs = AttendanceDeduction.objects.filter(
        employment=employment, work_date__in=clear)
    applied = qs.filter(status=AttendanceDeductionStatus.APPLIED)
    if applied.exists():
        logger.warning(
            "stale_applied_deductions",
            extra={"employment_id": employment.id,
                   "count": applied.count()})
    n = qs.exclude(status=AttendanceDeductionStatus.APPLIED).delete()[0]
    if n:
        logger.info("stale_deductions_dropped",
                    extra={"employment_id": employment.id, "count": n})


def recompute_company(*, company, start_date, end_date, branch_id=None):
    """
    يعيد بناء أيّام كل موظفي الشركة في مدى.

    ⚠️ ويُقيَّد بالفرع إن كانت العطلة لفرعٍ بعينه — فلا تُمسّ بقيّة الفروع.
    """
    from apps.employees.models import Employment, EmploymentStatus

    qs = Employment.objects.filter(company=company)
    if hasattr(Employment, "status"):
        qs = qs.exclude(status=EmploymentStatus.TERMINATED)
    if branch_id:
        qs = qs.filter(branch_id=branch_id)

    n = 0
    for emp in qs.iterator():
        try:
            recompute_employment(employment=emp, start_date=start_date,
                                 end_date=end_date)
            n += 1
        except Exception:
            # ⚠️ فشلُ موظفٍ لا يوقف البقيّة — وإلا ضاعت إعادةُ احتساب شركةٍ كاملة
            logger.exception("recompute_failed",
                             extra={"employment_id": emp.id})
    logger.info("recompute_company_done",
                extra={"company_id": company.id, "count": n})
    return n
