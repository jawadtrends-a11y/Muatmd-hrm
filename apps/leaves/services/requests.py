"""
خدمة الطلبات العامة (ق-54).

تستقبل أي نوع طلب، وتتحقق من صحته، وتمرّره بسلسلة الاعتماد،
وتنفّذ أثره عند الموافقة.

**المبدأ:** الطلب المعتمد يترك أثرًا حقيقيًا في النظام — سلفة
تُنشأ، وبصمة تُصحَّح، ويوم يُسجَّل حاضرًا. الطلب الذي لا يفعل
شيئًا ورقة لا نظام.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal as D

from django.db import transaction
from django.utils import timezone

from apps.leaves.models import (
    ApprovalChain, ApprovalDecision, Request, RequestApproval,
    RequestStatus, RequestType,
)

logger = logging.getLogger("muatmd.requests")


class RequestError(Exception):
    """خطأ في الطلب — رسالته تُعرض للمستخدم مباشرةً."""


@dataclass
class RequestResult:
    request: Request
    warnings: list = field(default_factory=list)
    effect: dict = field(default_factory=dict)


# ══════════ تعريف الأنواع ══════════
# كل نوع يُعلن حقوله المطلوبة ومن يستحقه

@dataclass(frozen=True)
class RequestSpec:
    code: str
    name_ar: str
    icon: str
    required_fields: tuple
    optional_fields: tuple = ()
    # من يستحق تقديمه — None يعني الجميع
    eligibility: str = ""
    hint_ar: str = ""


SPECS = {
    RequestType.LEAVE: RequestSpec(
        code="leave", name_ar="طلب إجازة", icon="leave",
        required_fields=("leave_type_code", "start_date", "days"),
        optional_fields=("note", "attachment_url"),
        hint_ar="يُخصم من رصيدك ويُسجَّل في الحضور عند الاعتماد",
    ),
    RequestType.ATTENDANCE_FIX: RequestSpec(
        code="attendance_fix", name_ar="طلب تصحيح بصمة", icon="clock",
        required_fields=("work_date", "reason"),
        optional_fields=("first_in", "last_out", "note"),
        hint_ar="يعدّل سجل حضورك لذلك اليوم عند الاعتماد",
    ),
    RequestType.PERMISSION: RequestSpec(
        code="permission", name_ar="طلب استئذان", icon="clock",
        required_fields=("work_date", "from_time", "to_time", "reason"),
        optional_fields=("note",),
        hint_ar="خروج مؤقت خلال ساعات الدوام",
    ),
    RequestType.REMOTE_WORK: RequestSpec(
        code="remote_work", name_ar="طلب عمل عن بُعد", icon="home",
        required_fields=("start_date", "days", "reason"),
        optional_fields=("note",),
        hint_ar="تُسجَّل الأيام حضورًا بلا بصمة",
    ),
    RequestType.ADVANCE: RequestSpec(
        code="advance", name_ar="طلب سلفة", icon="wallet",
        required_fields=("amount", "installments"),
        optional_fields=("reason", "note"),
        hint_ar="تُخصم أقساطها من راتبك الشهري",
    ),
    RequestType.ASSET: RequestSpec(
        code="asset", name_ar="طلب تسجيل عهدة", icon="doc",
        required_fields=("asset_name", "asset_category"),
        optional_fields=("serial_number", "value", "note"),
        hint_ar="تُسجَّل باسمك وتُخصم قيمتها إن لم تُرجع",
    ),
    RequestType.BUSINESS_TRIP: RequestSpec(
        code="business_trip", name_ar="طلب رحلة عمل", icon="doc",
        required_fields=("destination", "start_date", "days", "purpose"),
        optional_fields=("estimated_cost", "note"),
        hint_ar="بدل الانتداب حسب سياسة المنشأة",
    ),
    RequestType.TICKET: RequestSpec(
        code="ticket", name_ar="طلب تذكرة سفر", icon="doc",
        required_fields=("destination", "travel_date"),
        optional_fields=("family_members", "note"),
        eligibility="ticket_eligible",
        hint_ar="استحقاق سنوي — يشمل أفراد العائلة حسب سياسة المنشأة",
    ),
    RequestType.CERTIFICATE: RequestSpec(
        code="certificate", name_ar="طلب شهادة أو خطاب", icon="doc",
        required_fields=("certificate_type",),
        optional_fields=("addressed_to", "include_salary", "note"),
        hint_ar="صالحة 30 يومًا من تاريخ إصدارها",
    ),
    RequestType.RESIGNATION: RequestSpec(
        code="resignation", name_ar="طلب إنهاء عقد", icon="alert",
        required_fields=("last_working_day", "reason"),
        optional_fields=("note",),
        hint_ar="يبقى مفتوحًا حتى إنهاء كل معاملاتك",
    ),
    RequestType.OVERTIME: RequestSpec(
        code="overtime", name_ar="طلب اعتماد عمل إضافي", icon="clock",
        required_fields=("work_date", "hours"),
        optional_fields=("reason", "note"),
        hint_ar="الإضافي لا يدخل المسير إلا باعتماد صريح",
    ),
}


# ══════════ الأهلية ══════════

def eligible_types(employment):
    """
    الأنواع التي يستحق هذا الموظف تقديمها.

    ق-54: تذكرة السفر لغير السعوديين أساسًا — والشركة تختار
    إتاحتها للسعوديين.
    """
    from apps.payroll.models import PayrollSettings

    out = []
    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    tickets_for_saudis = bool(
        getattr(st, "tickets_for_saudis", False)) if st else False

    is_saudi = employment.person.nationality_code == "SA"

    for rtype, spec in SPECS.items():
        if spec.eligibility == "ticket_eligible":
            if is_saudi and not tickets_for_saudis:
                continue
        out.append({
            "code": rtype,
            "name_ar": spec.name_ar,
            "icon": spec.icon,
            "hint_ar": spec.hint_ar,
            "required_fields": list(spec.required_fields),
            "optional_fields": list(spec.optional_fields),
        })
    return out


# ══════════ الإنشاء ══════════

def _next_request_no(company, request_type):
    prefix = {
        RequestType.LEAVE: "LV", RequestType.ADVANCE: "AD",
        RequestType.TICKET: "TK", RequestType.ASSET: "AS",
        RequestType.PERMISSION: "PR", RequestType.CERTIFICATE: "CR",
        RequestType.RESIGNATION: "RS", RequestType.OVERTIME: "OT",
        RequestType.ATTENDANCE_FIX: "AF", RequestType.REMOTE_WORK: "RW",
        RequestType.BUSINESS_TRIP: "BT",
    }.get(request_type, "RQ")

    year = date.today().year
    n = Request.objects.filter(
        company=company, request_no__startswith=f"{prefix}-{year}").count()
    return f"{prefix}-{year}-{n + 1:04d}"


def _validate(request_type, payload):
    """يتحقق من الحقول المطلوبة ويطبّع القيم."""
    spec = SPECS.get(request_type)
    if spec is None:
        raise RequestError(f"نوع طلب غير معروف: {request_type}")

    missing = [f for f in spec.required_fields
               if payload.get(f) in (None, "", [])]
    if missing:
        raise RequestError(
            "حقول مطلوبة ناقصة: " + "، ".join(missing))

    # تطبيع التواريخ والأرقام
    clean = dict(payload)
    for key in ("start_date", "work_date", "travel_date",
                "last_working_day"):
        if clean.get(key):
            try:
                clean[key] = str(date.fromisoformat(str(clean[key])))
            except ValueError:
                raise RequestError(f"تاريخ غير صالح: {key}")

    for key in ("days", "installments", "hours"):
        if clean.get(key) not in (None, ""):
            try:
                clean[key] = float(clean[key])
                if clean[key] <= 0:
                    raise RequestError(f"القيمة يجب أن تكون أكبر من صفر: {key}")
            except (TypeError, ValueError):
                raise RequestError(f"قيمة غير رقمية: {key}")

    for key in ("amount", "value", "estimated_cost"):
        if clean.get(key) not in (None, ""):
            try:
                clean[key] = str(D(str(clean[key])))
            except Exception:
                raise RequestError(f"مبلغ غير صالح: {key}")

    return clean


@transaction.atomic
def create_request(*, employment, request_type, payload, note="",
                   attachment_url="", channel="web", submit=True):
    """
    ينشئ طلبًا ويبني سلسلة اعتماده.

    الإجازة لها مسار خاص (رصيد وحضور وأجر) فتُحوَّل لخدمتها.
    """
    if request_type == RequestType.LEAVE:
        from apps.leaves.services.leave_requests import create_leave_request
        res = create_leave_request(
            employment=employment,
            leave_type_code=payload.get("leave_type_code", ""),
            start_date=date.fromisoformat(str(payload["start_date"])),
            requested_days=payload.get("days"),
            note=note, attachment_url=attachment_url,
            channel=channel, submit=submit)
        return RequestResult(request=res.request,
                             warnings=getattr(res, "warnings", []),
                             effect={"charged_days": str(res.charged_days),
                                     "end_date": str(res.end_date)})

    clean = _validate(request_type, payload)

    # فحوص خاصة قبل الإنشاء
    warnings = _pre_checks(employment, request_type, clean)

    # يُنشأ مسودةً دائمًا ثم يُرفع — submit_request هي التي
    # تبني السلسلة وتنقل الحالة، وترفض ما ليس مسودة.
    req = Request.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        employment=employment,
        request_no=_next_request_no(employment.company, request_type),
        request_type=request_type,
        status=RequestStatus.DRAFT,
        payload=clean, note=note, attachment_url=attachment_url,
        channel=channel)

    if submit:
        _build_chain(req)
        req.refresh_from_db()

    logger.info("request_created", extra={
        "request_no": req.request_no, "type": request_type,
        "employment_id": employment.id})

    return RequestResult(request=req, warnings=warnings)


def _pre_checks(employment, request_type, payload):
    """فحوص قبل الإنشاء — تحذيرات لا موانع إلا ما وجب."""
    warnings = []

    if request_type == RequestType.ADVANCE:
        from apps.employees.services.advances import check_advance_eligibility
        from apps.payroll.models import PayrollSettings
        st = PayrollSettings.objects.filter(
            company_id=employment.company_id).first()
        if st and not st.advances_enabled:
            raise RequestError("نظام السلف غير مفعّل في شركتك")
        try:
            ok, reason = check_advance_eligibility(
                employment=employment, amount=D(str(payload["amount"])),
                settings_obj=st)
            if not ok:
                raise RequestError(reason)
        except RequestError:
            raise
        except Exception:
            pass

    elif request_type == RequestType.TICKET:
        # استحقاق سنوي — تحذير لا منع
        last = Request.objects.filter(
            employment=employment, request_type=RequestType.TICKET,
            status=RequestStatus.APPROVED,
            created_at__gte=timezone.now() - timedelta(days=365),
        ).first()
        if last:
            warnings.append(
                f"لديك تذكرة معتمدة خلال السنة الماضية ({last.request_no})")

    elif request_type == RequestType.ATTENDANCE_FIX:
        work_date = date.fromisoformat(str(payload["work_date"]))
        if work_date > date.today():
            raise RequestError("لا يُصحَّح يوم لم يأتِ بعد")
        if (date.today() - work_date).days > 60:
            warnings.append("اليوم المطلوب تصحيحه أقدم من شهرين")

    return warnings


def _build_chain(request_obj):
    """
    يبني سلسلة الاعتماد من القالب المعرّف للنوع.

    الدرجة الفارغة تُتخطى (ق-35): لو لم يكن للموظف مدير مباشر،
    تمضي الدرجة للتالية بدل أن يعلق الطلب.
    """
    from apps.leaves.services.approvals import submit_request as _submit
    try:
        _submit(request_obj)
    except Exception as e:  # noqa: BLE001
        logger.warning("chain_build_failed", extra={
            "request_no": request_obj.request_no, "error": str(e)})


# ══════════════════ الأثر عند الاعتماد ══════════════════
# الطلب المعتمد يترك أثرًا حقيقيًا — لا مجرد حالة تتغيّر


@transaction.atomic
def apply_effect(request_obj):
    """
    ينفّذ أثر الطلب المعتمد.

    يُستدعى من decide() بعد اكتمال السلسلة. الفشل هنا يُسجَّل
    ولا يلغي الاعتماد — الموافقة قرار إداري تمّ، والأثر تقني
    يُعاد تنفيذه.
    """
    handler = EFFECTS.get(request_obj.request_type)
    if handler is None:
        return {"applied": False, "reason": "لا أثر تلقائي لهذا النوع"}

    try:
        result = handler(request_obj)
        logger.info("effect_applied", extra={
            "request_no": request_obj.request_no,
            "type": request_obj.request_type})
        return {"applied": True, **(result or {})}
    except Exception as e:  # noqa: BLE001
        logger.error("effect_failed", extra={
            "request_no": request_obj.request_no, "error": str(e)})
        return {"applied": False, "error": str(e)}


def _effect_attendance_fix(req):
    """يصحّح سجل الحضور — بعلم التعديل اليدوي وأثره في التدقيق."""
    from apps.attendance.models import AttendanceDay, DayStatus

    p = req.payload
    work_date = date.fromisoformat(str(p["work_date"]))

    day, _created = AttendanceDay.objects.get_or_create(
        account_id=req.account_id, company_id=req.company_id,
        employment=req.employment, work_date=work_date,
        defaults={"status": DayStatus.PRESENT})

    def _dt(value):
        if not value:
            return None
        return timezone.make_aware(
            datetime.fromisoformat(f"{work_date}T{value}"))

    if p.get("first_in"):
        day.first_in = _dt(p["first_in"])
    if p.get("last_out"):
        day.last_out = _dt(p["last_out"])

    if day.first_in and day.last_out:
        minutes = int((day.last_out - day.first_in).total_seconds() / 60)
        day.worked_minutes = max(0, minutes)
        day.status = DayStatus.PRESENT
        day.late_minutes = 0      # التصحيح يلغي التأخير

    day.is_manually_adjusted = True
    day.adjustment_note = f"تصحيح بطلب {req.request_no}: {p.get('reason','')}"
    day.save()

    return {"attendance_day_id": day.id, "work_date": str(work_date)}


def _effect_remote_work(req):
    """يسجّل أيام العمل عن بُعد حضورًا كاملًا بلا بصمة."""
    from apps.attendance.models import AttendanceDay, DayStatus

    p = req.payload
    start = date.fromisoformat(str(p["start_date"]))
    days = int(float(p["days"]))

    made = []
    cursor = start
    remaining = days
    while remaining > 0:
        if cursor.weekday() not in (4, 5):      # تخطي الراحة
            day, _ = AttendanceDay.objects.update_or_create(
                account_id=req.account_id, company_id=req.company_id,
                employment=req.employment, work_date=cursor,
                defaults={
                    "status": DayStatus.PRESENT,
                    "worked_minutes": 8 * 60,
                    "late_minutes": 0,
                    "is_manually_adjusted": True,
                    "adjustment_note": f"عمل عن بُعد — {req.request_no}",
                })
            made.append(str(cursor))
            remaining -= 1
        cursor += timedelta(days=1)

    return {"days_marked": len(made), "dates": made}


def _effect_permission(req):
    """
    الاستئذان يخصم ساعاته من وقت العمل.

    لا يُحتسب غيابًا — خروج مأذون خلال الدوام.
    """
    from apps.attendance.models import AttendanceDay

    p = req.payload
    work_date = date.fromisoformat(str(p["work_date"]))
    day = AttendanceDay.objects.filter(
        employment=req.employment, work_date=work_date).first()
    if day is None:
        return {"skipped": "لا سجل حضور لذلك اليوم"}

    try:
        h1, m1 = map(int, str(p["from_time"]).split(":")[:2])
        h2, m2 = map(int, str(p["to_time"]).split(":")[:2])
        minutes = max(0, (h2 * 60 + m2) - (h1 * 60 + m1))
    except (ValueError, KeyError):
        minutes = 0

    day.early_out_minutes = (day.early_out_minutes or 0) + minutes
    day.is_manually_adjusted = True
    day.adjustment_note = (
        f"استئذان {minutes} دقيقة — {req.request_no}")
    day.save()

    return {"permission_minutes": minutes}


def _effect_advance(req):
    """ينشئ السلفة بأقساطها — تُخصم من المسير تلقائيًا."""
    from apps.employees.services.advances import create_advance
    from apps.payroll.models import PayrollSettings

    p = req.payload
    st = PayrollSettings.objects.filter(company_id=req.company_id).first()

    today = date.today()
    next_month = today.month + 1
    next_year = today.year
    if next_month > 12:
        next_month, next_year = 1, next_year + 1

    advance = create_advance(
        employment=req.employment,
        amount=D(str(p["amount"])),
        settings_obj=st,
        start_year=next_year, start_month=next_month,
        installments_count=int(float(p["installments"])),
        reason=p.get("reason", f"بطلب {req.request_no}"))

    return {"advance_no": advance.advance_no,
            "installments": advance.installments_count}


def _effect_asset(req):
    """يسجّل العهدة باسم الموظف."""
    from apps.employees.services.assets import assign_asset

    p = req.payload
    asset = assign_asset(
        employment=req.employment,
        name_ar=p["asset_name"],
        category=p.get("asset_category", "other"),
        value=D(str(p.get("value") or 0)),
        serial_number=p.get("serial_number", ""))

    return {"asset_no": asset.asset_no}


def _effect_overtime(req):
    """يعتمد ساعات الإضافي فتدخل المسير (ق-24)."""
    from apps.attendance.models import AttendanceDay

    p = req.payload
    work_date = date.fromisoformat(str(p["work_date"]))
    day = AttendanceDay.objects.filter(
        employment=req.employment, work_date=work_date).first()
    if day is None:
        return {"skipped": "لا سجل حضور لذلك اليوم"}

    minutes = int(float(p["hours"]) * 60)
    day.approved_overtime_minutes = minutes
    day.is_manually_adjusted = True
    day.adjustment_note = f"إضافي معتمد بطلب {req.request_no}"
    day.save()

    return {"approved_minutes": minutes}


def _effect_certificate(req):
    """
    الشهادة صالحة 30 يومًا (ق-54).

    التوليد الفعلي للملف يتم عند التحميل — هنا نسجّل الصلاحية.
    """
    valid_until = date.today() + timedelta(days=30)
    req.payload = {**req.payload,
                   "issued_at": str(date.today()),
                   "valid_until": str(valid_until)}
    req.save(update_fields=["payload", "updated_at"])
    return {"valid_until": str(valid_until)}


def _effect_resignation(req):
    """
    طلب إنهاء العقد يبقى مفتوحًا حتى إتمام المعاملات (ق-54).

    لا يغيّر حالة الموظف تلقائيًا — إنهاء الخدمة قرار بمخالصة
    وإخلاء طرف وإرجاع عهد.
    """
    return {"note": "يبقى مفتوحًا حتى إنهاء المخالصة وإخلاء الطرف"}


EFFECTS = {
    RequestType.ATTENDANCE_FIX: _effect_attendance_fix,
    RequestType.REMOTE_WORK: _effect_remote_work,
    RequestType.PERMISSION: _effect_permission,
    RequestType.ADVANCE: _effect_advance,
    RequestType.ASSET: _effect_asset,
    RequestType.OVERTIME: _effect_overtime,
    RequestType.CERTIFICATE: _effect_certificate,
    RequestType.RESIGNATION: _effect_resignation,
    # التذكرة ورحلة العمل: أثرهما مالي بسياسة المنشأة — يُصرفان
    # يدويًا أو بالمسير حسب اختيار الشركة (ق-54)
}
