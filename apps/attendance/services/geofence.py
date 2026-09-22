"""
التحقق من البصمة بالنطاق المكاني (ق-62).

المسافة تُحسب بمعادلة Haversine — لا تحتاج خريطة ولا مفتاحًا،
فالبصمة اليومية عملية رياضية بحتة.
"""
import logging
from math import asin, cos, radians, sin, sqrt

from django.utils import timezone

logger = logging.getLogger("muatmd.attendance")

EARTH_RADIUS_M = 6_371_000


class MobilePunchDisabled(Exception):
    """بصمة الجوال معطّلة لهذا الموظف (ق-96)."""


class GeofenceError(Exception):
    """
    رفض بصمة — رسالته تُعرض للموظف.

    ق-233: \u26a0 **برمزٍ ونصٍّ إنجليزيّ** — فموظف التطبيق الإنجليزيّ كان يقرأ
    الرفض بالعربية. و`str(e)` يبقى عربيًّا فلا ينكسر ما يعتمد عليه.
    """

    def __init__(self, message, code="outside_geofence", en=""):
        super().__init__(message)
        self.code, self.en = code, en or message


def distance_meters(lat1, lon1, lat2, lon2) -> float:
    """
    المسافة بين نقطتين على سطح الأرض — Haversine.

    الدقة كافية تمامًا للمسافات القصيرة (خطأ أقل من متر في
    نطاق كيلومترات).
    """
    p1, p2 = radians(float(lat1)), radians(float(lat2))
    dp = p2 - p1
    dl = radians(float(lon2) - float(lon1))

    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def sites_for(employment, at_date=None):
    """مواقع الموظف السارية."""
    from apps.attendance.models_sites import SiteAssignment

    day = at_date or timezone.localdate()
    qs = SiteAssignment.objects.filter(
        employment=employment, site__is_active=True
    ).select_related("site")

    out = []
    for a in qs:
        if a.effective_from and a.effective_from > day:
            continue
        if a.effective_to and a.effective_to < day:
            continue
        out.append(a.site)
    return out


def _as_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def verify_location(*, employment, latitude, longitude, accuracy_m=None):
    """
    يتحقق أن الموظف داخل أحد مواقعه (ق-62).

    يرجع (الموقع المطابق، المسافة). ويرفع GeofenceError عند
    الخروج — **فالمنع تام، والباب المفتوح هو طلب تصحيح البصمة.**
    """
    sites = sites_for(employment)
    if not sites:
        raise GeofenceError(
            "لا موقع عمل مُسند إليك — راجع مدير الموارد البشرية",
            code="no_site", en="No work site is assigned to you — contact HR")

    # المواقع التي لا تفرض التحقق تُقبل مباشرةً
    open_sites = [s for s in sites if not s.enforce_geofence]
    if open_sites:
        return open_sites[0], None

    geo_sites = [s for s in sites if s.has_coordinates]
    if not geo_sites:
        raise GeofenceError(
            "مواقعك بلا إحداثيات مضبوطة — راجع مدير الموارد البشرية",
            code="no_coordinates", en="Your work sites have no coordinates set — contact HR")

    if latitude is None or longitude is None:
        raise GeofenceError(
            "تعذّر تحديد موقعك — فعّل خدمة الموقع وحاول مجددًا",
            code="no_location", en="Could not determine your location — enable location services and try again")

    best = None
    best_distance = None

    for site in geo_sites:
        d = distance_meters(latitude, longitude,
                            site.latitude, site.longitude)
        if best_distance is None or d < best_distance:
            best, best_distance = site, d

        if d <= site.effective_radius:
            # ق-233: \u26a0\u26a0 **والدقّة كانت تُستقبل ولا تُستعمل** — فموقعٌ
            # بدقّة ±٨٠٠م يقع مركزه صدفةً داخل النطاق **كان يُقبل**. والحدّ
            # نصف قطر الموقع نفسه: الجوال لا يُثبت أنه داخله بأسوأ من ذلك.
            acc = _as_float(accuracy_m)
            if acc is not None and acc > site.effective_radius:
                raise GeofenceError(
                    f"موقعك غير دقيق (±{round(acc)} م) — اخرج لمكانٍ مكشوف "
                    "وانتظر ثوانيَ ثم حاول مجددًا",
                    code="low_accuracy",
                    en=f"Your location is not precise (±{round(acc)} m) — move to "
                       "an open area, wait a few seconds and try again")
            logger.info("geofence_ok", extra={
                "site": site.code, "distance": round(d)})
            return site, round(d)

    # الخروج عن النطاق — نذكر أقرب موقع والمسافة ليفهم الموظف
    over = round(best_distance - best.effective_radius)
    raise GeofenceError(
        f"أنت خارج نطاق «{best.name_ar}» بـ{over} مترًا. "
        "إن كنت في موقعك فعلًا، قدّم طلب تصحيح بصمة من «خدماتي»",
        code="outside_geofence",
        en=f"You are {over} m outside «{getattr(best, 'name_en', '') or best.name_ar}». "
           "If you are on site, submit a punch correction request")



def _mobile_punch_allowed(employment):
    """
    هل يبصم هذا الموظف بجواله؟ (ق-96)

    ثلاثة مستويات، والأخصّ يغلب الأعمّ: الموظف ثم فترة عمله ثم
    شركته. فمن فُتحت بصمته في ملفه يبصم ولو أُقفلت في فترته
    وشركته — والاستثناء الفردي هو الغرض من وجوده.

    وفارغ يعني «اتبع الأعمّ» لا «مسموح»: فرقٌ بين من لم يُقرَّر
    له ومن قُرِّر له صراحةً.
    """
    if employment.allow_mobile_punch is not None:
        return employment.allow_mobile_punch

    from apps.attendance.models import ShiftAssignment

    # معزول ذاتيًا: مقيَّد بالارتباط المقروء بالبوابة
    a = (ShiftAssignment.objects
         .filter(employment=employment)
         .select_related("shift")
         .order_by("-id").first())
    if a and a.shift and a.shift.allow_mobile_punch is not None:
        return a.shift.allow_mobile_punch

    from apps.payroll.models import PayrollSettings

    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    return st.allow_mobile_punch if st else True


def record_punch(*, employment, latitude=None, longitude=None,
                 method="mobile_gps", device_code="", accuracy_m=None,
                 punched_at=None, skip_geofence=False, direction="",
                 mocked=False):
    """
    يسجّل بصمة بعد التحقق.

    الجهاز في موقع ثابت لا يحتاج GPS — فبصمته موثوقة بمكانه.
    """
    from apps.attendance.models import AttendancePunch
    from apps.attendance.models_sites import PunchDevice, PunchMethod

    # ق-96: من أُلغيت بصمة جواله يبصم بالجهاز وحده — وبعض
    # المواقع تشترط الحضور الفعلي للجهاز
    if (method == PunchMethod.MOBILE_GPS
            and not _mobile_punch_allowed(employment)):
        raise MobilePunchDisabled(
            "بصمة الجوال معطّلة لك — استخدم جهاز البصمة")

    # ق-233: \u26a0\u26a0 **الموقع المزيَّف يُرفض دائمًا** (قرار جواد) — فتطبيقات
    # تزييف الـGPS مجّانيّة، وموظفٌ في بيته كان يبصم «في الموقع».
    # وأندرويد يُعلِم التطبيق بالتزييف؛ والمحاولة تُسجَّل بمن حاول.
    if method == PunchMethod.MOBILE_GPS and mocked:
        logger.warning("mock_location_rejected", extra={
            "employment_id": employment.id, "company_id": employment.company_id})
        raise GeofenceError(
            "موقعك مزيَّف — أوقف تطبيق تزييف الموقع وحاول مجددًا",
            code="mock_location",
            en="Your location is spoofed — turn off the fake-location app and try again")

    site = None
    distance = None

    if method == PunchMethod.DEVICE and device_code:
        device = PunchDevice.objects.filter(
            company_id=employment.company_id, device_code=device_code,
            is_active=True).select_related("site").first()
        if device is None:
            raise GeofenceError(f"جهاز غير معروف: {device_code}")
        site = device.site
        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at", "updated_at"])

    elif method == PunchMethod.MANUAL or skip_geofence:
        pass      # الإدخال اليدوي من الموارد — استثناء موثّق

    else:
        site, distance = verify_location(
            employment=employment, latitude=latitude, longitude=longitude,
            accuracy_m=accuracy_m)

    punch = AttendancePunch.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        employment=employment,
        punched_at=punched_at or timezone.now(),
        source=method,
        device_id=device_code or "",
        latitude=latitude,
        longitude=longitude,
        raw_payload={
            "site_id": site.id if site else None,
            "site_code": site.code if site else "",
            "distance_m": distance,
            "accuracy_m": accuracy_m,
            # الاتجاه كما صرّح به الموظف: الزرّان في الويب
            # والتطبيق يقولان دخولًا وخروجًا، فيُحفظ ما قاله.
            # والاحتساب يبقى على استنتاجه من التسلسل — فهذا
            # للمراجعة حين يختلفان.
            "direction": direction or "",
        })

    logger.info("punch_recorded", extra={
        "employment_id": employment.id, "method": method,
        "site": site.code if site else ""})

    # ق-235: ويومها يُحتسب فورًا — فيظهر في جدول الموظف قبل أن يغلق الشاشة
    from apps.attendance.services.processing import process_punch_day
    process_punch_day(punch)
    return punch, site, distance
