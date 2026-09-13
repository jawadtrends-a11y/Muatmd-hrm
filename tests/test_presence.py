"""
حرّاس تتبّع التواجد (ق-144).

⚠️⚠️ **ولا تُحفظ الإحداثيّات**: حفظُ مسار الموظف تتبّعٌ لا مراقبة
حضور — **فالمحفوظ حكمٌ ثنائيّ** (قرار جواد).

⚠️⚠️ **والخصم يُقترَح ولا يقع**: فساعة البريك مرنة — والموارد
تعتمد أو تترك.
"""
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.attendance.models import (
    PresenceDay, PresencePing, PresenceState, Shift, ShiftAssignment,
    SiteAssignment, WorkSite)
from apps.attendance.services import presence as svc
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent, PayrollSettings

LAT, LON = Decimal("21.5000"), Decimal("39.2000")


@pytest.fixture
def env(db):
    r = provision_account(slug="pr-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")
        p, _ = create_person(
            account=acc, first_name_ar="فيصل", family_name_ar="الزهراني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="P-7",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("9000"))])

        st = PayrollSettings.objects.get(company=comp)
        st.presence_tracking_enabled = True
        st.presence_tolerance_minutes = 60
        st.save()

        site = WorkSite.objects.create(
            account=acc, company=comp, code="HQ", name_ar="المقرّ",
            latitude=LAT, longitude=LON, radius_meters=100,
            tolerance_meters=20, enforce_geofence=True)
        SiteAssignment.objects.create(
            account=acc, company=comp, employment=emp, site=site,
            is_primary=True)

        sh = Shift.objects.create(
            account=acc, company=comp, code="ALLDAY",
            name_ar="طوال اليوم", start_time=time(0, 1),
            end_time=time(23, 59))
        ShiftAssignment.objects.create(
            account=acc, company=comp, employment=emp, shift=sh,
            effective_from=date(2024, 1, 1))

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "site": site, "settings": st}


def _ping(env, lat=LAT, lon=LON):
    return svc.record(employment=env["emp"], latitude=lat, longitude=lon)


def test_disabled_blocks_tracking(env):
    """والتتبّع يُفعَّل من الإعدادات — لا يعمل بلا قرار."""
    with account_scope(env["account_id"]):
        env["settings"].presence_tracking_enabled = False
        env["settings"].save(update_fields=["presence_tracking_enabled"])
        with pytest.raises(svc.PresenceError):
            _ping(env)


def test_no_coordinates_are_stored(env):
    """
    ⚠️⚠️ الأهمّ: **لا إحداثيّات في الجدول**.

    فحفظُ مسار الموظف تتبّعٌ لا مراقبة حضور — وله بُعدٌ قانونيّ.
    """
    fields = {f.name for f in PresencePing._meta.get_fields()}
    assert "latitude" not in fields, "الإحداثيّات تُحفظ!"
    assert "longitude" not in fields, "الإحداثيّات تُحفظ!"

    with account_scope(env["account_id"]):
        p = _ping(env)
        assert p.state == PresenceState.INSIDE


def test_outside_is_detected(env):
    """والخارج يُكشف بالمسافة."""
    with account_scope(env["account_id"]):
        p = _ping(env, lat=Decimal("21.6000"), lon=Decimal("39.3000"))
        assert p.state == PresenceState.OUTSIDE
        assert p.distance_meters > 100


def test_unguarded_site_is_not_tracked(env):
    """
    ⚠️ **والمحروس وحده يُتتبَّع**: فموقعٌ بلا `enforce_geofence`
    لا يُراقَب.
    """
    with account_scope(env["account_id"]):
        env["site"].enforce_geofence = False
        env["site"].save(update_fields=["enforce_geofence"])
        assert svc.active_site(env["emp"]) is None
        with pytest.raises(svc.PresenceError):
            _ping(env)


def test_outside_shift_is_refused(env):
    """
    ⚠️ **وأثناء الفترة فقط** — فخارجها وقتُه ملكُه.
    """
    with account_scope(env["account_id"]):
        sh = Shift.objects.filter(company=env["comp"]).first()
        sh.start_time = time(3, 0)
        sh.end_time = time(3, 30)
        sh.save()

        now = timezone.localtime()
        if time(3, 0) <= now.time() <= time(3, 30):
            pytest.skip("الوقت الحاليّ داخل الفترة")
        with pytest.raises(svc.PresenceError) as e:
            _ping(env)
        assert "فترتك" in str(e.value)


def test_tolerance_absorbs_short_absence(env):
    """
    ⚠️ **والتسامح يُطرح**: فساعة البريك مرنة، وخروجٌ قصير لا
    يستحقّ اقتراح حسم (قرار جواد).
    """
    with account_scope(env["account_id"]):
        for _ in range(3):                     # 45 دقيقة
            _ping(env, lat=Decimal("21.6"), lon=Decimal("39.3"))
        d = PresenceDay.objects.get(employment=env["emp"],
                                    work_date=timezone.localdate())
        assert d.outside_minutes == 45
        assert d.deductible_minutes == 0
        assert (d.suggested_amount or 0) == 0


def test_beyond_tolerance_suggests_an_amount(env):
    """وما تجاوزه يُقترَح خصمه — **اقتراحًا لا قرارًا**."""
    with account_scope(env["account_id"]):
        env["settings"].presence_tolerance_minutes = 0
        env["settings"].save(
            update_fields=["presence_tolerance_minutes"])
        for _ in range(4):                     # 60 دقيقة
            _ping(env, lat=Decimal("21.6"), lon=Decimal("39.3"))

        d = PresenceDay.objects.get(employment=env["emp"],
                                    work_date=timezone.localdate())
        assert d.deductible_minutes == 60
        assert d.suggested_amount > 0
        assert d.is_reviewed is False
        assert d.approved_amount is None, "وقع الخصم بلا مراجعة"


def test_review_is_what_decides(env):
    """
    ⚠️⚠️ **والمراجعة هي الضابط**: فالموارد تعتمد المقترَح أو
    تتركه صفرًا.
    """
    with account_scope(env["account_id"]):
        env["settings"].presence_tolerance_minutes = 0
        env["settings"].save(
            update_fields=["presence_tolerance_minutes"])
        for _ in range(4):
            _ping(env, lat=Decimal("21.6"), lon=Decimal("39.3"))

        d = PresenceDay.objects.get(employment=env["emp"],
                                    work_date=timezone.localdate())
        svc.review(presence_day=d, approved_amount=0,
                   note="بريك متّفقٌ عليه")
        d.refresh_from_db()
        assert d.is_reviewed is True
        assert d.approved_amount == Decimal("0")


def test_reviewed_day_is_not_recomputed(env):
    """والمراجَع لا يُعاد حسابه — فالقرار وقع."""
    with account_scope(env["account_id"]):
        _ping(env)
        d = PresenceDay.objects.get(employment=env["emp"],
                                    work_date=timezone.localdate())
        svc.review(presence_day=d, approved_amount=0)

        _ping(env, lat=Decimal("21.6"), lon=Decimal("39.3"))
        d.refresh_from_db()
        assert d.outside_minutes == 0, "أُعيد حساب يومٍ رُوجع"


def test_double_review_refused(env):
    """ولا يُراجَع مرّتين."""
    with account_scope(env["account_id"]):
        _ping(env)
        d = PresenceDay.objects.get(employment=env["emp"],
                                    work_date=timezone.localdate())
        svc.review(presence_day=d, approved_amount=0)
        with pytest.raises(svc.PresenceError):
            svc.review(presence_day=d, approved_amount=50)


def test_old_pings_are_purged(env):
    """
    ⚠️ **والنبضات تُحذف بعد مدّة الاحتفاظ** — فبيانات موقعٍ بلا
    حدّ تصير أرشيف تتبّع.
    """
    with account_scope(env["account_id"]):
        _ping(env)
        old = timezone.localdate() - timedelta(days=200)
        PresencePing.objects.filter(employment=env["emp"]).update(
            work_date=old)

        svc.purge_old_pings(company_id=env["comp"].id)
        assert PresencePing.objects.filter(
            employment=env["emp"]).count() == 0
