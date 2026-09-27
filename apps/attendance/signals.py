"""
إشارات تُعيد احتساب أيّام الحضور عند كل حدثٍ يمسّ الماضي (ق-٢٦٢).

⚠️⚠️ **الاحتساب يقرأ الماضي مرّةً ولا يعود إليه** — فعطلةٌ تُضاف بعد أسبوع،
أو **إجازةٌ تُعتمد بعد يومين** (وهو الأشيع: الموظف يغيب ثم يُقدّم طلبه)،
تترك أيّامها **غيابًا** في السجلّ. **والغياب يُنشئ خصمًا ويُقترح عليه جزاء.**
"""
import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger("muatmd.attendance")


def _queue_company(company_id, account_id, start, end, branch_id=None):
    from apps.attendance.tasks import recompute_company_days
    try:
        recompute_company_days.apply_async(kwargs={
            "account_id": account_id, "company_id": company_id,
            "start_date": str(start), "end_date": str(end),
            "branch_id": branch_id})
    except Exception:
        # ⚠️ تعذُّرُ الإرسال للطابور لا يُسقط حفظَ العطلة نفسها
        logger.exception("recompute_enqueue_failed")


def _queue_employment(employment_id, account_id, start, end):
    from apps.attendance.tasks import recompute_employment_days
    try:
        recompute_employment_days.apply_async(kwargs={
            "account_id": account_id, "employment_id": employment_id,
            "start_date": str(start), "end_date": str(end)})
    except Exception:
        logger.exception("recompute_enqueue_failed")


def register():
    """تُستدعى من `AttendanceConfig.ready()`."""
    from apps.attendance.models_exemption import AttendanceExemption
    from apps.leaves.models import Request, RequestStatus, RequestType
    from apps.organization.models import Holiday

    @receiver(post_save, sender=Holiday, dispatch_uid="recompute_holiday_save")
    def _holiday_saved(sender, instance, **kwargs):
        _queue_company(instance.company_id, instance.account_id,
                       instance.start_date, instance.end_date,
                       getattr(instance, "branch_id", None))

    @receiver(post_delete, sender=Holiday, dispatch_uid="recompute_holiday_del")
    def _holiday_deleted(sender, instance, **kwargs):
        # ⚠️ وحذفُ عطلةٍ يُعيد الأيّام لحالتها الصحيحة أيضًا
        _queue_company(instance.company_id, instance.account_id,
                       instance.start_date, instance.end_date,
                       getattr(instance, "branch_id", None))

    @receiver(post_save, sender=Request, dispatch_uid="recompute_leave_save")
    def _request_saved(sender, instance, **kwargs):
        # ⚠️ الاعتماد **والإلغاء** كلاهما يُغيّر الحالة — فكلاهما يُعيد الاحتساب
        if instance.request_type != RequestType.LEAVE:
            return
        if instance.status not in (RequestStatus.APPROVED,
                                   RequestStatus.CANCELLED,
                                   RequestStatus.REJECTED,
                                   RequestStatus.WITHDRAWN):
            return
        p = instance.payload or {}
        s, e = p.get("start_date"), p.get("end_date")
        if not s or not e:
            return
        _queue_employment(instance.employment_id, instance.account_id, s, e)

    @receiver(post_save, sender=AttendanceExemption,
              dispatch_uid="recompute_exemption_save")
    def _exemption_saved(sender, instance, **kwargs):
        # ⚠️⚠️ **الإعفاء المفتوح (`end_date` فارغ) هو الأصل** — المدير العام
        # والمندوب الخارجي معفيّان بلا أجل. فلو أُخذ `start_date` نهايةً،
        # أُعيد يومٌ واحدٌ وبقي الشهر كلُّه غيابًا. فتمتدّ لليوم.
        from datetime import date as _d
        end = instance.end_date or max(_d.today(), instance.start_date)
        _queue_employment(instance.employment_id, instance.account_id,
                          instance.start_date, end)

    logger.info("attendance_recompute_signals_registered")
