"""
استقبال البصمات من الأجهزة (ق-84).

مسار واحد لكل مصدر: وسيطنا، أو BioTime، أو أي برنامج آخر. فمن
عنده BioTime لا نطلب منه تركه، ومن ليس عنده نعطيه برمجيتنا.

والتعافي من الانقطاع أصل التصميم: الجهاز يخزّن بصماته محليًّا حين
ينقطع، والوسيط يرفعها متأخرة — فالمسار يقبلها بتاريخها الأصلي
ويتجاهل المكرّرة.
"""
import logging

from django.contrib.auth.hashers import check_password
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

log = logging.getLogger("muatmd.attendance")

#: أقصى عدد بصمات في الدفعة الواحدة — يمنع طلبًا يستهلك الخادم
MAX_BATCH = 500


def _authenticate(request):
    """
    يتحقق من مفتاح الجهاز.

    والمفتاح مجزّأ في القاعدة، فالمقارنة بالتجزئة لا بالنص —
    ومن يقرأ القاعدة لا ينتحل جهازًا.
    """
    from apps.attendance.models_sites import PunchDevice

    key = (request.headers.get("X-Device-Key")
           or request.data.get("device_key") or "").strip()
    code = (request.headers.get("X-Device-Code")
            or request.data.get("device_code") or "").strip().upper()

    if not key or not code:
        return None, "رمز الجهاز ومفتاحه مطلوبان"

    # الجهاز يصادق نفسه — لا مستخدم في السياق ولا نطاق يُفلتر به
    device = PunchDevice.objects.filter(
        device_code=code, is_active=True).first()
    if device is None:
        return None, "جهاز غير معروف أو معطّل"

    if not check_password(key, device.api_key_hash):
        log.warning("device_auth_failed", extra={"device": code})
        return None, "مفتاح غير صحيح"

    return device, None


@api_view(["POST"])
@permission_classes([AllowAny])
def ingest_punches(request):
    """
    يستقبل دفعة بصمات من جهاز.

    الجسم:
        {"punches": [
            {"employee_no": "1007", "punched_at": "2026-09-05T08:01:33",
             "external_ref": "12345"},
            ...
        ]}

    والرد يفصّل: كم قُبل، وكم كان مكرّرًا، وكم موظف لم يُعرف —
    فالوسيط يعرف ما وصل وما لم يصل، ولا يعيد رفع ما قُبل.
    """
    from apps.attendance.models import AttendancePunch, PunchSource
    from apps.core.tenancy.context import account_scope
    from apps.employees.models import Employment, EmploymentStatus

    device, err = _authenticate(request)
    if device is None:
        return Response({"detail": err, "code": "device_auth"}, status=401)

    rows = request.data.get("punches") or []
    if not isinstance(rows, list):
        return Response({"detail": "punches يجب أن تكون قائمة"}, status=400)
    if len(rows) > MAX_BATCH:
        return Response(
            {"detail": f"أقصى دفعة {MAX_BATCH} بصمة — قسّمها",
             "code": "batch_too_large"}, status=413)

    accepted = duplicated = 0
    unknown = []
    invalid = []

    with account_scope(device.account_id):
        # خريطة الأرقام الوظيفية — استعلام واحد لا استعلام لكل بصمة
        emp_by_no = {
            e.employee_no: e
            for e in Employment.objects.filter(
                company_id=device.company_id,
                status=EmploymentStatus.ACTIVE)
        }

        for row in rows:
            no = str(row.get("employee_no") or row.get("user_id") or "")
            raw_at = row.get("punched_at") or row.get("timestamp")

            emp = emp_by_no.get(no)
            if emp is None:
                unknown.append(no)
                continue

            at = parse_datetime(str(raw_at)) if raw_at else None
            if at is None:
                invalid.append({"employee_no": no, "punched_at": raw_at})
                continue

            if at.tzinfo is None:
                from django.utils import timezone as tz
                at = tz.make_aware(at)

            # ق-84: الجهاز + الموظف + الوقت بالثانية بصمة واحدة
            # مهما رُفعت مرات — فالرفع المتكرّر بعد الانقطاع لا
            # يُحتسب حضورًا مضاعفًا
            _obj, created = AttendancePunch.objects.get_or_create(
                account_id=device.account_id,
                company_id=device.company_id,
                employment=emp,
                punched_at=at,
                device_id=device.device_code,
                defaults={
                    "source": PunchSource.DEVICE,
                    "external_ref": str(row.get("external_ref") or ""),
                    "raw_payload": row,
                })
            if created:
                accepted += 1
            else:
                duplicated += 1

        # آخر اتصال — به يُعرف الجهاز الصامت قبل أن يشتكي أحد
        from django.utils import timezone
        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])

    log.info("punches_ingested", extra={
        "device": device.device_code, "accepted": accepted,
        "duplicated": duplicated, "unknown": len(unknown),
    })

    return Response({
        "accepted": accepted,
        "duplicated": duplicated,
        "unknown_employees": sorted(set(unknown))[:20],
        "invalid": invalid[:20],
        "received": len(rows),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def device_ping(request):
    """
    يتحقق الوسيط من مفتاحه قبل أن يبدأ الرفع.

    فمن يضبط جهازًا يحتاج تأكيدًا أن الإعداد صحيح — لا أن يكتشف
    الخطأ بعد يوم من بصمات ضائعة.
    """
    device, err = _authenticate(request)
    if device is None:
        return Response({"detail": err, "code": "device_auth"}, status=401)

    return Response({
        "ok": True,
        "device_code": device.device_code,
        "name_ar": device.name_ar,
        "company_id": device.company_id,
        "last_seen_at": device.last_seen_at,
    })
