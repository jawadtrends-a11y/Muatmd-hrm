"""
أنواع الطلبات المخصّصة (ق-142).

⚠️ **ولا أثر آليًّا لها**: تُقدَّم وتُعتمد وتُوثَّق — فالأثر يحتاج
كودًا، وادّعاؤه يبيع وهمًا.
"""
import logging
import re
from datetime import date

from django.db import transaction

logger = logging.getLogger(__name__)

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

#: ⚠️ مفاتيح محجوزة — تصادمها مع حقول الطلب يُفسد الحمولة
RESERVED_KEYS = {
    "request_type", "status", "note", "attachment_url",
    "employment_id", "custom_type_code", "custom_type_name",
}

#: ⚠️ **و`work_date` ليس محجوزًا**: فهو المفتاح القياسيّ للتاريخ،
# وخاصّية «مرّة في اليوم» تقرؤه — فحجزُه يجعلها بلا سبيل.


class CustomTypeError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def validate_key(key):
    """
    يتحقّق من مفتاح الحقل.

    ⚠️ **فمفتاحٌ عربيّ أو بمسافة** يكسر الحمولة، **والمحجوز**
    يصادم حقول الطلب الأساسية.
    """
    k = (key or "").strip()
    if not KEY_RE.match(k):
        raise CustomTypeError(
            "المفتاح بالإنجليزية الصغيرة وأرقامٍ وشرطةٍ سفلية، "
            "ويبدأ بحرف")
    if k in RESERVED_KEYS:
        raise CustomTypeError(f"«{k}» مفتاحٌ محجوز — اختر غيره")
    return k


def validate_payload(request_type, payload):
    """
    يتحقّق من حمولة طلبٍ مخصّص.

    **الإلزاميّ يُطلَب، والقائمة تُقيَّد بخياراتها** — فقيمةٌ خارج
    القائمة تُفسد التقارير.
    """
    from apps.leaves.models import FieldKind

    payload = payload or {}
    missing = []
    for f in request_type.fields.all():
        v = payload.get(f.key)
        if f.is_required and v in (None, "", []):
            missing.append(f.label_ar)
            continue
        if v in (None, ""):
            continue

        if f.kind == FieldKind.SELECT and f.option_list:
            if str(v) not in f.option_list:
                raise CustomTypeError(
                    f"«{f.label_ar}»: قيمةٌ خارج الخيارات")
        elif f.kind == FieldKind.NUMBER:
            try:
                float(v)
            except (TypeError, ValueError):
                raise CustomTypeError(f"«{f.label_ar}»: رقمٌ غير صالح")
        elif f.kind == FieldKind.DATE:
            try:
                date.fromisoformat(str(v))
            except ValueError:
                raise CustomTypeError(f"«{f.label_ar}»: تاريخٌ غير صالح")

    if missing:
        raise CustomTypeError("حقول مطلوبة: " + "، ".join(missing))

    if request_type.requires_attachment and not payload.get(
            "attachment_url"):
        raise CustomTypeError("هذا الطلب يلزمه مرفق")

    return True


def check_daily_duplicate(employment, request_type, payload):
    """
    ⚠️ **مرّةً في اليوم** إن اشترطه النوع — كقاعدة ق-134.

    والمرفوض لا يمنع: فالرفض قد يُصحَّح بعد تفاهم.
    """
    from apps.leaves.models import Request, RequestStatus

    if not request_type.daily_unique:
        return None

    day = payload.get("work_date") or payload.get("date")
    if not day:
        return None

    dup = Request.objects.filter(
        employment=employment, request_type="custom",
        status__in=[RequestStatus.PENDING, RequestStatus.APPROVED],
        payload__custom_type_code=request_type.code,
        payload__work_date=str(day)).first()
    if dup:
        raise CustomTypeError(
            f"لديك {request_type.name_ar} بنفس التاريخ: "
            f"{dup.request_no} — ولا يُقدَّم ثانٍ إلا إن رُفض الأول")
    return None


@transaction.atomic
def submit(*, employment, request_type, payload, note=""):
    """
    يقدّم طلبًا من نوعٍ مخصّص.

    ⚠️ **ويُحفظ رمز النوع في الحمولة**: فبدونه لا يُعرف أيّ نوعٍ
    هو بعد تعديل الكتالوج.
    """
    from apps.leaves.services.requests import create_request
    from apps.leaves.models import RequestType

    if not request_type.is_active:
        raise CustomTypeError("هذا الطلب معطَّل")

    validate_payload(request_type, payload)
    check_daily_duplicate(employment, request_type, payload)

    full = {**(payload or {}),
            "custom_type_code": request_type.code,
            "custom_type_name": request_type.name_ar}

    return create_request(employment=employment,
                          request_type=RequestType.CUSTOM,
                          payload=full, note=note)
