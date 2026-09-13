"""
تتبّع التواجد في موقع العمل (ق-144).

⚠️⚠️ **بلا إحداثيّات** — والمحفوظ حكمٌ ثنائيّ: داخل أو خارج.

⚠️⚠️ **والخصم يُقترَح ولا يقع** — فالموارد تعتمد أو تترك.
"""
import logging
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ZERO = Decimal("0")

#: كل نبضةٍ تمثّل هذه المدّة
PING_MINUTES = 15

#: ⚠️ تنبيهٌ نظاميّ يُحمَل مع كل اقتراح خصم
DEDUCTION_WARNING = (
    "⚠️ الحسم من الأجر لا يكون نظامًا إلا وفق لائحة الجزاءات "
    "(المادة ٧١). وهذا اقتراحٌ يُراجَع — لا يقع بذاته."
)


class PresenceError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def _distance_m(lat1, lon1, lat2, lon2):
    """المسافة بالأمتار — صيغة هافرساين."""
    r = 6371000.0
    p1, p2 = radians(float(lat1)), radians(float(lat2))
    dp = radians(float(lat2) - float(lat1))
    dl = radians(float(lon2) - float(lon1))
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return int(2 * r * asin(sqrt(a)))


def active_site(employment, at=None):
    """
    الموقع المُسنَد له الآن — **والمحروس وحده يُتتبَّع**.

    فمن لا موقع له، أو موقعُه بلا `enforce_geofence`، لا يُتتبَّع.
    """
    from apps.attendance.models import SiteAssignment

    at = at or timezone.localdate()
    from django.db.models import Q

    # ⚠️ **والفارغ سارٍ**: إسنادٌ بلا تاريخ بدء يعني «من الأصل»
    # — وإسقاطُه يُعطّل التتبّع لمن أُسند إليه بلا تواريخ.
    a = (SiteAssignment.objects
         .filter(employment=employment)
         .filter(Q(effective_from__isnull=True)
                 | Q(effective_from__lte=at))
         .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=at))
         .select_related("site")
         .order_by("-is_primary", "-effective_from").first())
    if a is None or a.site is None:
        return None
    if not a.site.enforce_geofence:
        return None
    return a.site


def is_within_shift(employment, at=None):
    """
    ⚠️ **أثناء الفترة فقط** — فخارجها وقتُه ملكُه.
    """
    from apps.attendance.models import ShiftAssignment

    at = at or timezone.localtime()
    sa = (ShiftAssignment.objects
          .filter(employment=employment, effective_from__lte=at.date())
          .exclude(effective_to__lt=at.date())
          .select_related("shift").order_by("-effective_from").first())
    if sa is None or sa.shift is None:
        return False

    sh = sa.shift
    start, end = sh.start_time, sh.end_time
    now = at.time()
    if start <= end:
        return start <= now <= end
    # فترةٌ تعبر منتصف الليل
    return now >= start or now <= end


@transaction.atomic
def record(*, employment, latitude, longitude, at=None):
    """
    يسجّل نبضةً — **بحكمها لا بموقعها**.

    ⚠️ **ولا تُحفظ الإحداثيّات**: فحفظُ المسار تتبّعٌ لا مراقبة
    حضور.
    """
    from apps.attendance.models import (
        PresencePing, PresenceState)
    from apps.payroll.models import PayrollSettings

    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    if st is None or not st.presence_tracking_enabled:
        raise PresenceError("تتبّع التواجد غير مفعَّل")

    at = at or timezone.localtime()
    site = active_site(employment, at.date())
    if site is None:
        raise PresenceError("لا موقع محروسٌ مُسنَدٌ لك")
    if not is_within_shift(employment, at):
        raise PresenceError("خارج وقت فترتك — ولا تتبّع خارجها")

    if latitude is None or longitude is None:
        state, dist = PresenceState.NO_SIGNAL, None
    else:
        dist = _distance_m(latitude, longitude,
                           site.latitude, site.longitude)
        allowed = (site.radius_meters or 0) + (site.tolerance_meters or 0)
        state = (PresenceState.INSIDE if dist <= allowed
                 else PresenceState.OUTSIDE)

    ping = PresencePing.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        employment=employment, site=site,
        work_date=at.date(), at=at, state=state,
        distance_meters=dist)

    _roll_up(employment, at.date())
    return ping


@transaction.atomic
def _roll_up(employment, day):
    """يجمّع نبضات اليوم في خلاصته."""
    from django.db.models import Count

    from apps.attendance.models import (
        PresenceDay, PresencePing, PresenceState)
    from apps.payroll.models import PayrollSettings

    counts = dict(PresencePing.objects.filter(
        employment=employment, work_date=day
    ).values_list("state").annotate(n=Count("id")))

    inside = counts.get(PresenceState.INSIDE, 0) * PING_MINUTES
    outside = counts.get(PresenceState.OUTSIDE, 0) * PING_MINUTES
    nosig = counts.get(PresenceState.NO_SIGNAL, 0) * PING_MINUTES

    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    tolerance = (st.presence_tolerance_minutes if st else 60) or 0

    # ⚠️ **التسامح يُطرح**: فساعة البريك مرنة، وخروجٌ لحظيّ لا
    # يستحقّ اقتراح حسم.
    deductible = max(outside - tolerance, 0)

    d, _ = PresenceDay.objects.get_or_create(
        employment=employment, work_date=day,
        defaults={"account_id": employment.account_id,
                  "company_id": employment.company_id})
    if d.is_reviewed:
        return d          # رُوجع — لا يُعاد حسابه

    d.inside_minutes = inside
    d.outside_minutes = outside
    d.no_signal_minutes = nosig
    d.deductible_minutes = deductible
    d.suggested_amount = suggest_amount(employment, deductible)
    d.save()
    return d


def suggest_amount(employment, minutes):
    """
    الخصم المقترَح — **بمعدّل أجر الساعة**.

    ⚠️ **واقتراحٌ لا قرار**: فالموارد تعتمد أو تترك.
    """
    from apps.employees.services.hiring import current_salary_structure
    from apps.payroll.models import PayrollSettings
    from apps.payroll.services.calculations import hourly_rate

    if not minutes:
        return ZERO

    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    structure = current_salary_structure(employment,
                                         timezone.localdate())
    if st is None or structure is None:
        return ZERO

    gross = sum((l[1] for l in structure.as_lines()), ZERO)
    rate = hourly_rate(gross, st.payroll_days_per_month or 30,
                       st.working_hours_per_day or Decimal("8"))
    return (rate * Decimal(minutes) / Decimal(60)).quantize(
        Decimal("0.01"))


@transaction.atomic
def review(*, presence_day, approved_amount=None, by_person_id=None,
           note=""):
    """
    قرار الموارد — **وبه وحده يقع الخصم**.

    ⚠️ فساعة البريك مرنةٌ في كثيرٍ من الشركات، **والاقتراح ليس
    حكمًا** (قرار جواد).
    """
    if presence_day.is_reviewed:
        raise PresenceError("رُوجع بالفعل")

    amount = (Decimal(str(approved_amount))
              if approved_amount not in (None, "") else ZERO)
    if amount < 0:
        raise PresenceError("المبلغ لا يكون سالبًا")

    presence_day.is_reviewed = True
    presence_day.approved_amount = amount
    presence_day.reviewed_by_person_id = by_person_id
    presence_day.reviewed_at = timezone.now()
    presence_day.review_note = (note or "")[:255]
    presence_day.save(update_fields=[
        "is_reviewed", "approved_amount", "reviewed_by_person_id",
        "reviewed_at", "review_note", "updated_at"])
    return presence_day


def purge_old_pings(company_id=None):
    """
    ⚠️ **يحذف النبضات بعد مدّة الاحتفاظ**.

    فبيانات موقعٍ تُحفظ بلا حدّ تصير أرشيف تتبّع — والخلاصة تكفي.
    """
    from datetime import timedelta

    from apps.attendance.models import PresencePing
    from apps.payroll.models import PayrollSettings

    qs = PayrollSettings.objects.all()
    if company_id:
        qs = qs.filter(company_id=company_id)

    total = 0
    for st in qs:
        days = st.presence_retention_days or 90
        cutoff = timezone.localdate() - timedelta(days=days)
        n, _ = PresencePing.objects.filter(
            company_id=st.company_id, work_date__lt=cutoff).delete()
        total += n
    logger.info("حُذفت %s نبضة تجاوزت مدّة الاحتفاظ", total)
    return total
