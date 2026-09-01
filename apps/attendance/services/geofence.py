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


class GeofenceError(Exception):
    """رفض بصمة — رسالته تُعرض للموظف."""


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


def verify_location(*, employment, latitude, longitude, accuracy_m=None):
    """
    يتحقق أن الموظف داخل أحد مواقعه (ق-62).

    يرجع (الموقع المطابق، المسافة). ويرفع GeofenceError عند
    الخروج — **فالمنع تام، والباب المفتوح هو طلب تصحيح البصمة.**
    """
    sites = sites_for(employment)
    if not sites:
        raise GeofenceError(
            "لا موقع عمل مُسند إليك — راجع مدير الموارد البشرية")

    # المواقع التي لا تفرض التحقق تُقبل مباشرةً
    open_sites = [s for s in sites if not s.enforce_geofence]
    if open_sites:
        return open_sites[0], None

    geo_sites = [s for s in sites if s.has_coordinates]
    if not geo_sites:
        raise GeofenceError(
            "مواقعك بلا إحداثيات مضبوطة — راجع مدير الموارد البشرية")

    if latitude is None or longitude is None:
        raise GeofenceError(
            "تعذّر تحديد موقعك — فعّل خدمة الموقع وحاول مجددًا")

    best = None
    best_distance = None

    for site in geo_sites:
        d = distance_meters(latitude, longitude,
                            site.latitude, site.longitude)
        if best_distance is None or d < best_distance:
            best, best_distance = site, d

        if d <= site.effective_radius:
            logger.info("geofence_ok", extra={
                "site": site.code, "distance": round(d)})
            return site, round(d)

    # الخروج عن النطاق — نذكر أقرب موقع والمسافة ليفهم الموظف
    over = round(best_distance - best.effective_radius)
    raise GeofenceError(
        f"أنت خارج نطاق «{best.name_ar}» بـ{over} مترًا. "
        "إن كنت في موقعك فعلًا، قدّم طلب تصحيح بصمة من «خدماتي»")


def record_punch(*, employment, latitude=None, longitude=None,
                 method="mobile_gps", device_code="", accuracy_m=None,
                 punched_at=None, skip_geofence=False):
    """
    يسجّل بصمة بعد التحقق.

    الجهاز في موقع ثابت لا يحتاج GPS — فبصمته موثوقة بمكانه.
    """
    from apps.attendance.models import AttendancePunch
    from apps.attendance.models_sites import PunchDevice, PunchMethod

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
        })

    logger.info("punch_recorded", extra={
        "employment_id": employment.id, "method": method,
        "site": site.code if site else ""})

    return punch, site, distance
