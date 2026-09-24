"""
حارس: الدوام المرن يحسب النقص (ق-٢٥١).

⚠️⚠️ **المرن لا يعني بلا حساب.** كان من بصم ودخل وخرج بعد ساعتين يُردّ
`PRESENT` ونقصًا صفرًا — **فيأخذ أجر يومٍ كامل**. وفي أول حسابٍ حقيقيّ
(١٤ موظفًا · ٤ أشهر) كان الضائع **٣٥٧ ساعة**: نصف أيام «الحضور» ناقصة.
وقتُ الحضور حرٌّ في المرن، **وإكمال الساعات لازم**.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apps.attendance.services.rules import compute_day

TZ = ZoneInfo("Asia/Riyadh")
DAY = date(2026, 9, 1)


class _Shift:
    """فترة مرنة ٨ ساعات — بلا قاعدة بيانات، فالحساب دالّةٌ صافية."""
    is_flexible = True
    crosses_midnight = False
    start_time = time(8, 0)
    end_time = time(16, 0)
    break_minutes = 0
    grace_in_minutes = 15
    grace_out_minutes = 15
    # ⚠️ ١ سبتمبر ٢٠٢٦ ثلاثاء — والترقيم 0=الأحد، فالثلاثاء 2
    working_days = [0, 1, 2, 3, 4, 6]


def _punches(start_h, hours):
    a = datetime.combine(DAY, time(start_h, 0), tzinfo=TZ)
    return [a, a + timedelta(hours=hours)]


def test_flexible_short_day_records_shortfall():
    """ساعتان من ثمانٍ ← نقصٌ ٣٦٠ دقيقة، واليوم جزئيّ لا كامل."""
    r = compute_day(work_date=DAY, punches=_punches(9, 2), shift=_Shift())
    assert r.worked_minutes == 120
    assert r.early_out_minutes == 360, "⚠️ النقص أُهمل — أجرُ يومٍ كامل لساعتين"
    assert r.status != "present", "⚠️ يومٌ ناقصٌ عُدّ حضورًا كاملًا"


def test_flexible_full_day_has_no_shortfall():
    """ثماني ساعاتٍ كاملة ← لا نقص، ولو بدأ متأخرًا (فالوقت حرّ)."""
    r = compute_day(work_date=DAY, punches=_punches(11, 8), shift=_Shift())
    assert r.early_out_minutes == 0
    assert r.late_minutes == 0, "⚠️ المرن لا يحاسب على وقت الحضور"
    assert r.status == "present"


def test_flexible_overtime_still_counted():
    """عشر ساعاتٍ ← ساعتان إضافيتان، ولا نقص."""
    r = compute_day(work_date=DAY, punches=_punches(8, 10), shift=_Shift())
    assert r.overtime_minutes == 120
    assert r.early_out_minutes == 0
