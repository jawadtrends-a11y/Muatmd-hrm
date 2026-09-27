"""
عكس أثر الطلبات المعتمدة (ق-٢٦٨).

⚠️⚠️ **الاعتماد يُحدث أثرًا، والإلغاء كان يُغيّر حالةً فقط.** فالطلب المعتمد
يُنشئ سلفةً، أو يُعفي من البصمة، أو يعتمد ساعات إضافي — **وإلغاؤه بلا عكس
أثره يترك النظام مناقضًا لنفسه**: طلبٌ «ملغى» وسلفتُه تُخصم من المسير.

⭐ **قرار جواد: موظّف الموارد يُلغي أيّ طلبٍ بعد اعتماده** — فلكلّ نوعٍ عكسُه
هنا، **وما لا أثر له يُلغى بتغيير الحالة وحدها** بلا استثناءٍ يدويّ.
"""
import logging
from datetime import date

from django.db import transaction

logger = logging.getLogger("muatmd.requests")


def revert_advance(req):
    """
    ⭐ **قرار جواد:** لم تُستلم أقساطٌ بعد → إلغاءٌ كامل؛ سُدّدت بالكامل →
    `SETTLED`؛ **سُدّدت جزئيًّا → يُمنع**: فالمال خرج ولم يُستردّ كلُّه،
    والشطب (`WRITTEN_OFF`) قرارٌ آخر بيد الموارد.
    """
    from apps.employees.models_assets import Advance, AdvanceStatus
    from apps.leaves.services.balances import LeaveError

    # ⭐ بالربط الصريح لا بالبحث في النصّ (ق-٢٥٨: التسمية جزءٌ من العقد)
    adv = Advance.objects.filter(request=req).order_by("-id").first()
    if adv is None:      # ⚠️ سلفٌ قديمةٌ قبل ربط الحقل
        adv = Advance.objects.filter(
            employment=req.employment,
            reason__contains=req.request_no).order_by("-id").first()
    if adv is None:
        return {"skipped": "لا سلفة مرتبطة"}

    paid = adv.installments.filter(is_deducted=True).count()
    total = adv.installments_count or 0

    if paid == 0:
        adv.status = AdvanceStatus.CANCELLED
        adv.save(update_fields=["status", "updated_at"])
        adv.installments.filter(is_deducted=False).delete()
        return {"advance": "cancelled"}

    if total and paid >= total:
        adv.status = AdvanceStatus.SETTLED
        adv.save(update_fields=["status", "updated_at"])
        return {"advance": "settled"}

    raise LeaveError(
        f"سُدّد {paid} من {total} قسطًا — لا تُلغى سلفةٌ بدأ سدادها. "
        f"أكمل سدادها أو اشطبها من شاشة السلف")


def revert_attendance_exemption(req):
    """⚠️ الإعفاء يُعطَّل لا يُحذف — فسجلّ من أُعفي ومتى يبقى."""
    from django.utils import timezone

    from apps.attendance.models_exemption import AttendanceExemption

    n = AttendanceExemption.objects.filter(
        employment=req.employment, is_active=True
    ).update(is_active=False, revoked_at=timezone.now())
    return {"exemptions_revoked": n}


def revert_overtime(req):
    """⚠️ الساعات المعتمدة تعود صفرًا — **والمحتسب بالبصمة يبقى** كما هو."""
    from apps.attendance.models import AttendanceDay

    p = req.payload or {}
    if not p.get("work_date"):
        return {"skipped": "لا تاريخ"}
    day = AttendanceDay.objects.filter(
        employment=req.employment,
        work_date=date.fromisoformat(str(p["work_date"]))).first()
    if day is None:
        return {"skipped": "لا سجل حضور"}
    day.approved_overtime_minutes = 0
    day.overtime_rate_choice = ""
    day.adjustment_note = f"أُلغي اعتماد الإضافي — {req.request_no}"
    day.save(update_fields=["approved_overtime_minutes",
                            "overtime_rate_choice", "adjustment_note",
                            "updated_at"])
    return {"overtime_cleared": True}


def revert_permission(req):
    """⚠️ دقائق الاستئذان تُطرح — ولا تنزل تحت الصفر."""
    from apps.attendance.models import AttendanceDay

    p = req.payload or {}
    if not p.get("work_date"):
        return {"skipped": "لا تاريخ"}
    day = AttendanceDay.objects.filter(
        employment=req.employment,
        work_date=date.fromisoformat(str(p["work_date"]))).first()
    if day is None:
        return {"skipped": "لا سجل حضور"}
    try:
        h1, m1 = map(int, str(p["from_time"]).split(":")[:2])
        h2, m2 = map(int, str(p["to_time"]).split(":")[:2])
        minutes = max(0, (h2 * 60 + m2) - (h1 * 60 + m1))
    except (ValueError, KeyError):
        minutes = 0
    day.early_out_minutes = max(0, (day.early_out_minutes or 0) - minutes)
    day.adjustment_note = f"أُلغي الاستئذان — {req.request_no}"
    day.save(update_fields=["early_out_minutes", "adjustment_note",
                            "updated_at"])
    return {"permission_minutes_removed": minutes}


def revert_salary_fix(req):
    """
    ⚠️ **تثبيت الراتب يُنهي فترة التجربة** — وعكسه يُعيدها.
    ⚠️⚠️ **ولا يُعاد ما لا نعرف أصله**: إن لم تُحفظ المدّة السابقة في
    الحمولة، لا يُخمَّن تاريخٌ — فالتجربة مدّةٌ لها أثرٌ في الفصل والحقوق.
    """
    from apps.leaves.services.balances import LeaveError

    p = req.payload or {}
    prev = p.get("previous_probation_end")
    if not prev:
        raise LeaveError(
            "لا تُعرف فترة التجربة السابقة — عدّلها يدويًّا من ملفّ الموظف")
    emp = req.employment
    emp.probation_end_date = date.fromisoformat(str(prev))
    emp.save(update_fields=["probation_end_date"])
    return {"probation_restored": str(prev)}


# ══════════ الموزّع (ق-٢٦٨) ══════════

def _reversals():
    """⚠️ يُبنى عند الطلب — فلا استيراد دائريّ عند الإقلاع."""
    from apps.leaves.models import RequestType

    return {
        RequestType.ADVANCE: revert_advance,
        RequestType.ATTENDANCE_EXEMPTION: revert_attendance_exemption,
        RequestType.OVERTIME: revert_overtime,
        RequestType.PERMISSION: revert_permission,
        RequestType.SALARY_FIX: revert_salary_fix,
    }


def revert_effect(request_obj):
    """
    يعكس أثر طلبٍ معتمد — كلٌّ بحسب نوعه.

    ⭐ **وما لا أثر له يُلغى بتغيير الحالة وحدها** (شهادة، تظلّم، عهدة…):
    فلا استثناءَ يدويٌّ لكل نوع، والغياب عن الجدول هو الجواب.

    ⚠️⚠️ **والفشل هنا يُوقف الإلغاء** — بخلاف `apply_effect` حيث الاعتماد
    قرارٌ إداريٌّ تمّ والأثر يُعاد تنفيذه. **فطلبٌ يُعلَن ملغىً وأثرُه قائم
    أسوأ من طلبٍ لم يُلغَ**: سلفةٌ تُخصم من مسير موظفٍ ألغى النظام طلبها.

    ⭐ **والإجازة ليست هنا**: لها `revoke_approved_leave` (ق-٢٦٧) التي تردّ
    الرصيد وتعكس التسوية المالية أيضًا.
    """
    fn = _reversals().get(request_obj.request_type)
    if fn is None:
        return {"reverted": False, "reason": "لا أثر تلقائي لهذا النوع"}
    out = fn(request_obj) or {}
    logger.info("effect_reverted",
                extra={"request_no": request_obj.request_no,
                       "type": request_obj.request_type})
    return {"reverted": True, **out}


@transaction.atomic
def revoke_any_request(*, request_obj, by_person, reason):
    """
    إلغاء أيّ طلبٍ معتمدٍ غير الإجازة — للموارد البشرية، بسببٍ إلزاميّ.

    ⭐ **قرار جواد: موظّف الموارد يُلغي أيّ طلبٍ بعد اعتماده.** والإجازة لها
    `revoke_approved_leave` (ق-٢٦٧) لأنّ عكسها يمسّ الرصيد والتسوية المالية.
    """
    from django.utils import timezone

    from apps.leaves.models import RequestStatus
    from apps.leaves.services.balances import LeaveError

    if request_obj.status != RequestStatus.APPROVED:
        raise LeaveError(
            f"الطلب {request_obj.get_status_display()} — لا يُلغى هنا")
    if not str(reason or "").strip():
        # ⚠️ **الإلغاء يُعلَّل**: قرارٌ يعكس أثرًا وقع، فيُراجَع
        raise LeaveError("اكتب سبب الإلغاء")

    # ⚠️⚠️ **العكس أولًا**: فإن فشل، بقي الطلب معتمدًا وأثرُه متّسقٌ معه.
    # وطلبٌ يُعلَن ملغىً وأثرُه قائم أسوأ من طلبٍ لم يُلغَ.
    out = revert_effect(request_obj)

    p = dict(request_obj.payload or {})
    p["revoked_at"] = timezone.now().isoformat()
    p["revoke_reason"] = str(reason).strip()
    request_obj.payload = p
    request_obj.status = RequestStatus.CANCELLED
    request_obj.closed_at = timezone.now()
    request_obj.save(update_fields=["payload", "status", "closed_at",
                                    "updated_at"])

    from apps.core.services.audit import log_action
    log_action(
        instance=request_obj, action="update", actor=by_person,
        label=request_obj.request_no,
        summary=f"ألغت الموارد طلبًا معتمدًا — {reason}", channel="web")

    return {"status": request_obj.status, **out}
