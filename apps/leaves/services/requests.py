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
from decimal import Decimal, Decimal as D

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
        required_fields=("leave_type_code", "start_date", "end_date"),
        optional_fields=("note", "attachment_url"),
        hint_ar="اختر من تاريخ إلى تاريخ — النظام يحتسب المخصوم من رصيدك",
    ),
    RequestType.ATTENDANCE_FIX: RequestSpec(
        code="attendance_fix", name_ar="طلب تصحيح بصمة", icon="clock",
        required_fields=("work_date", "fix_target", "reason"),
        optional_fields=("first_in", "last_out", "note"),
        hint_ar="حدّد أي بصمة تصحّح — ولا يُقبل طلبان لنفس اليوم",
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
        required_fields=("destination", "start_date", "end_date", "purpose"),
        optional_fields=("estimated_cost", "note"),
        hint_ar="من المغادرة إلى العودة — لا تُخصم من رصيد الإجازات",
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
        required_fields=("termination_reason", "request_date"),
        # ق-79: البديل إلزامي لمن يشغل موقعًا إداريًا — وإلزامه
        # يُحسب بموقع المُقدِّم لا بشرط مكتوب هنا، فالموظف العادي
        # لا يقطع بمغادرته سلسلة
        optional_fields=("successor_employment_id", "note"),
        hint_ar="مدة الإشعار 30 يومًا تبدأ من تاريخ الاعتماد النهائي",
    ),
    RequestType.OVERTIME: RequestSpec(
        code="overtime", name_ar="طلب اعتماد عمل إضافي", icon="clock",
        required_fields=("work_date", "from_time", "to_time"),
        optional_fields=("reason", "note"),
        hint_ar="من أي وقت إلى أي وقت — تُحتسب بالدقيقة لا بالساعة",
    ),
}


# ══════════ الأهلية ══════════

# ق-65: تعديل البيانات يُطلب من الملف لا من «خدماتي» — فلا
# بطاقة له هنا، لكن النوع يبقى صالحًا للإنشاء والاعتماد.
HIDDEN_FROM_SERVICES = {RequestType.PROFILE_UPDATE}


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
        if rtype in HIDDEN_FROM_SERVICES:
            continue
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
        from apps.leaves.models import LeaveType
        from apps.leaves.services.balances import compute_days_between
        from apps.leaves.services.leave_requests import create_leave_request

        start = date.fromisoformat(str(payload["start_date"]))

        # ق-59: الموظف يختار تاريخين، والنظام يحتسب الأيام المخصومة
        days = payload.get("days")
        if payload.get("end_date"):
            lt = LeaveType.objects.filter(
                company_id=employment.company_id,
                code=payload.get("leave_type_code", "")).first()
            if lt is None:
                raise RequestError("نوع إجازة غير معروف")
            calc = compute_days_between(
                company=employment.company, leave_type=lt,
                start_date=start,
                end_date=date.fromisoformat(str(payload["end_date"])))
            days = calc.charged_days

        if not days:
            raise RequestError("حدّد تاريخي البداية والنهاية")

        res = create_leave_request(
            employment=employment,
            leave_type_code=payload.get("leave_type_code", ""),
            start_date=start,
            requested_days=days,
            note=note, attachment_url=attachment_url,
            channel=channel, submit=submit)
        return RequestResult(request=res.request,
                             warnings=getattr(res, "warnings", []),
                             effect={"charged_days": str(res.charged_days),
                                     "end_date": str(res.end_date)})

    # ق-65: طلب التعديل يبني الفرق «من → إلى» قبل الحفظ
    if request_type == RequestType.PROFILE_UPDATE:
        diff = build_profile_diff(employment, payload.get("changes")
                                  or payload)
        clean = {"changes": diff, "count": len(diff)}
        warnings = []
    else:
        clean = _validate(request_type, payload)
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

        # ق-59: لا طلبان لنفس اليوم — الثاني يتعارض مع الأول
        dup = Request.objects.filter(
            employment=employment,
            request_type=RequestType.ATTENDANCE_FIX,
            status__in=[RequestStatus.PENDING, RequestStatus.APPROVED],
            payload__work_date=str(work_date)).first()
        if dup:
            raise RequestError(
                f"لديك طلب تصحيح لنفس اليوم: {dup.request_no} "
                f"({dup.get_status_display()})")

        # لا بد من بصمة واحدة على الأقل حسب المختار
        target = payload.get("fix_target", "both")
        if target in ("in", "both") and not payload.get("first_in"):
            raise RequestError("حدّد وقت الحضور")
        if target in ("out", "both") and not payload.get("last_out"):
            raise RequestError("حدّد وقت الانصراف")

    elif request_type == RequestType.OVERTIME:
        # ق-59: من وقت إلى وقت — تُحتسب بالدقيقة
        try:
            h1, m1 = map(int, str(payload["from_time"]).split(":")[:2])
            h2, m2 = map(int, str(payload["to_time"]).split(":")[:2])
        except (KeyError, ValueError):
            raise RequestError("حدّد وقتي بداية ونهاية العمل الإضافي")
        minutes = (h2 * 60 + m2) - (h1 * 60 + m1)
        if minutes <= 0:
            minutes += 24 * 60
        payload["minutes"] = minutes
        payload["hours"] = round(minutes / 60, 2)
        if minutes > 600:
            warnings.append("أكثر من عشر ساعات — راجع الاحتساب")

    elif request_type == RequestType.BUSINESS_TRIP:
        start = date.fromisoformat(str(payload["start_date"]))
        end = date.fromisoformat(str(payload["end_date"]))
        if end < start:
            raise RequestError("تاريخ العودة قبل المغادرة")
        payload["days"] = (end - start).days + 1

    elif request_type == RequestType.RESIGNATION:
        # ق-59: مدة الإشعار من الاعتماد لا من التقديم (م/75)
        payload["notice_days"] = 30
        payload["request_date"] = payload.get(
            "request_date") or str(date.today())

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

    # ق-69: ما كان محتسبًا قبل التصحيح — به يُقاس الفرق
    before_minutes = day.worked_minutes or 0

    def _dt(value):
        if not value:
            return None
        return timezone.make_aware(
            datetime.fromisoformat(f"{work_date}T{value}"))

    target = p.get("fix_target", "both")
    if p.get("first_in") and target in ("in", "both"):
        day.first_in = _dt(p["first_in"])
    if p.get("last_out") and target in ("out", "both"):
        day.last_out = _dt(p["last_out"])

    if day.first_in and day.last_out:
        minutes = int((day.last_out - day.first_in).total_seconds() / 60)
        day.worked_minutes = max(0, minutes)
        day.status = DayStatus.PRESENT
        day.late_minutes = 0      # التصحيح يلغي التأخير

    day.is_manually_adjusted = True
    day.adjustment_note = f"تصحيح بطلب {req.request_no}: {p.get('reason','')}"
    day.save()

    out = {"attendance_day_id": day.id, "work_date": str(work_date)}

    # ق-69: التصحيح في شهر أُغلق مسيره يترك فرقًا مستحقًا.
    #
    # والفرق يُحتسب بإعادة حساب الشهر بالبيانات المصححة لا بردّ
    # الخصم كاملًا: من تأخر ساعة ونسي بصمته ساعتين يعود له أجر
    # ساعة لا ساعتين.
    retro = _retro_for_month(req, work_date, before_minutes, day)
    if retro:
        out["retro"] = retro

    return out


def _retro_for_month(req, work_date, before_minutes, day):
    """
    يسجّل تسوية رجعية إن كان مسير الشهر مغلقًا (ق-69).

    ولا يُنشئ شيئًا إن كان المسير مفتوحًا — فالاحتساب القادم يأخذ
    التصحيح بنفسه.
    """
    from apps.payroll.models import PayrollSettings
    from apps.payroll.services.retro import (RetroSource, closed_run_for,
                                             record_adjustment)

    run = closed_run_for(company=req.company,
                         year=work_date.year, month=work_date.month)
    if run is None:
        return None      # المسير مفتوح — لا حاجة لتسوية

    st = PayrollSettings.objects.filter(company=req.company).first()
    daily = _daily_wage(req.employment)
    if daily is None:
        return None

    # الفرق بالدقائق × أجر الدقيقة — لا قيمة اليوم كاملًا
    minute_wage = daily / Decimal("480")      # 8 ساعات معيارية
    gained = Decimal(str(max(0, day.worked_minutes - before_minutes)))
    if gained == 0:
        return None

    adj = record_adjustment(
        employment=req.employment,
        year=work_date.year, month=work_date.month,
        source=RetroSource.ATTENDANCE_FIX,
        amount_before=Decimal("0"),
        amount_after=(minute_wage * gained).quantize(Decimal("0.01")),
        reason_ar=f"تصحيح بصمة {work_date} بطلب {req.request_no}",
        source_request=req)
    return {"id": adj.id, "amount": str(adj.amount)} if adj else None


def _daily_wage(employment):
    """أجر اليوم من آخر هيكل راتب ساري."""
    from apps.employees.models import SalaryStructure

    st = (SalaryStructure.objects
          .filter(employment=employment, effective_to__isnull=True)
          .order_by("-effective_from").first())
    if st is None:
        return None
    return (st.gross_monthly or Decimal("0")) / Decimal("30")


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

    before = day.approved_overtime_minutes or 0
    minutes = int(p.get("minutes") or float(p.get("hours", 0)) * 60)
    day.approved_overtime_minutes = minutes
    day.is_manually_adjusted = True
    day.adjustment_note = f"إضافي معتمد بطلب {req.request_no}"
    day.save()

    out = {"approved_minutes": minutes}

    # ق-69: الإضافي المعتمد بعد إغلاق مسير شهره لم يُحتسب أصلًا —
    # فالفرق قيمته كاملة لا نصفه.
    retro = _retro_overtime(req, work_date, before, minutes)
    if retro:
        out["retro"] = retro
    return out


def _retro_overtime(req, work_date, before_minutes, after_minutes):
    """
    تسوية عن إضافي اعتُمد بعد إغلاق مسير شهره (ق-69).

    وأجر الإضافي بمعامله النظامي (1.5) لا بأجر الدقيقة العادي.
    """
    from apps.payroll.services.retro import (RetroSource, closed_run_for,
                                             record_adjustment)

    run = closed_run_for(company=req.company,
                         year=work_date.year, month=work_date.month)
    if run is None:
        return None      # المسير مفتوح — الاحتساب يأخذه

    gained = Decimal(str(max(0, after_minutes - before_minutes)))
    if gained == 0:
        return None

    daily = _daily_wage(req.employment)
    if daily is None:
        return None

    # ق-24: الإضافي بمعامل 1.5 من أجر الساعة
    minute_wage = daily / Decimal("480")
    amount = (minute_wage * gained * Decimal("1.5")).quantize(
        Decimal("0.01"))

    adj = record_adjustment(
        employment=req.employment,
        year=work_date.year, month=work_date.month,
        source=RetroSource.OVERTIME,
        amount_before=Decimal("0"), amount_after=amount,
        reason_ar=(f"إضافي {work_date} — {int(gained)} دقيقة "
                   f"بطلب {req.request_no}"),
        source_request=req)
    return {"id": adj.id, "amount": str(adj.amount)} if adj else None


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

    والخليفة يُفعَّل هنا لا عند التقديم (ق-79): البديل يُسمّى مع
    الطلب، والمهام لا تنتقل حتى يُعتمد — فقد يُرفض.
    """
    out = {"note": "يبقى مفتوحًا حتى إنهاء المخالصة وإخلاء الطرف"}

    sid = (req.payload or {}).get("successor_employment_id")
    if not sid:
        return out

    from apps.employees.models import Employment
    from apps.leaves.services.delegation import (DelegationError,
                                                 appoint_successor,
                                                 successor_of)

    if successor_of(req.employment) is not None:
        out["successor"] = "معيَّن سلفًا"
        return out

    successor = Employment.objects.filter(
        id=sid, company_id=req.company_id).first()
    if successor is None:
        out["successor_error"] = "البديل غير موجود"
        return out

    try:
        # يسري من تاريخ الطلب — فالمهام تنتقل حين يُعتمد لا قبله
        starts = (req.payload or {}).get("request_date")
        from datetime import date as _date
        appoint_successor(
            leaving=req.employment, successor=successor,
            effective_from=(_date.fromisoformat(str(starts)) if starts
                            else _date.today()),
            note=f"خلافة بموجب {req.request_no}")
        out["successor"] = successor.person.display_name
    except (DelegationError, ValueError) as e:
        # فشل الخلافة لا يلغي اعتماد الاستقالة — القرار الإداري تمّ
        out["successor_error"] = str(e)

    return out





# ══════════ طلب تعديل البيانات (ق-65) ══════════

# الحقول التي يطلب الموظف تعديلها — كل شيء عدا الراتب والعقد
EDITABLE_BY_EMPLOYEE = {
    # الشخصية
    "first_name_ar": "الاسم الأول",
    "father_name_ar": "اسم الأب",
    "grandfather_name_ar": "اسم الجد",
    "family_name_ar": "اسم العائلة",
    "full_name_en": "الاسم بالإنجليزية",
    "birth_date": "تاريخ الميلاد",
    "marital_status": "الحالة الاجتماعية",
    "id_expiry_date": "انتهاء الهوية",
    "passport_number": "رقم الجواز",
    "passport_expiry_date": "انتهاء الجواز",
    "border_number": "رقم الحدود",
    "mobile": "الجوال",
    "email": "البريد الإلكتروني",
    # البنك
    "iban": "الآيبان",
    # التأمينات
    "gosi_scheme_code": "نظام التأمينات",
}

# ما لا يُطلب أبدًا (ق-65): قرارات إدارية والتزامات تعاقدية
FORBIDDEN_FIELDS = {
    "salary", "basic_salary", "allowances",
    "contract_type", "contract_start_date", "contract_end_date",
    "probation_days", "join_date", "service_start_date",
}

PERSON_FIELDS = {
    "first_name_ar", "father_name_ar", "grandfather_name_ar",
    "family_name_ar", "full_name_en", "birth_date", "marital_status",
    "id_expiry_date", "passport_number", "passport_expiry_date",
    "border_number", "email", "gosi_scheme_code",
}


def field_label(key):
    return EDITABLE_BY_EMPLOYEE.get(key, key)


def current_value(employment, key):
    """القيمة الحالية للحقل — من الشخص أو الارتباط."""
    person = employment.person
    if key == "mobile":
        return person.mobile_e164 or ""
    if key in PERSON_FIELDS:
        v = getattr(person, key, "")
    else:
        v = getattr(employment, key, "")
    return "" if v is None else str(v)


def build_profile_diff(employment, requested):
    """
    يبني قائمة الفروقات: من → إلى (ق-65).

    **المعتمِد يرى ما يتغيّر بالضبط** — لا «طلب تعديل بيانات»
    مبهمًا.
    """
    diff = []
    for key, new_value in (requested or {}).items():
        if key in FORBIDDEN_FIELDS:
            raise RequestError(
                f"{field_label(key)} لا يُعدَّل بطلب — راجع الموارد البشرية")
        if key not in EDITABLE_BY_EMPLOYEE:
            continue

        old_value = current_value(employment, key)
        new_str = "" if new_value is None else str(new_value)
        if old_value == new_str:
            continue

        diff.append({
            "field": key,
            "label": field_label(key),
            "from": old_value,
            "to": new_str,
        })

    if not diff:
        raise RequestError("لا تغييرات — عدّل حقلًا واحدًا على الأقل")

    return diff


def _effect_profile_update(req):
    """
    يطبّق التعديلات المعتمدة على الملف (ق-65).

    ويُسجَّل في سجل العمليات باسم الموظف ومعتمِده معًا.
    """
    emp = req.employment
    person = emp.person
    applied = []

    for change in (req.payload.get("changes") or []):
        key = change.get("field")
        value = change.get("to")
        if key in FORBIDDEN_FIELDS or key not in EDITABLE_BY_EMPLOYEE:
            continue

        if key == "mobile":
            from apps.employees.services.validators import normalize_mobile
            normalized, err = normalize_mobile(value)
            if err:
                continue
            person.mobile_e164 = normalized
        elif key == "iban":
            from apps.employees.services.validators import validate_saudi_iban
            ok, _err = validate_saudi_iban(value)
            if not ok:
                continue
            emp.iban = value
        elif key in PERSON_FIELDS:
            setattr(person, key, value or None)
        else:
            setattr(emp, key, value or None)

        applied.append(key)

    person.save()
    emp.save()

    return {"applied": applied, "count": len(applied)}


# ══════════ خريطة الآثار — بعد تعريف كل الدوال ══════════

EFFECTS = {
    RequestType.PROFILE_UPDATE: _effect_profile_update,
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
