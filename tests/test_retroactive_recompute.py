"""
حارس: ما يُدخَل عن الماضي يُعيد احتساب أيّامه (ق-٢٦٢).

⚠️⚠️ **الاحتساب يقرأ الماضي مرّةً ولا يعود إليه.** يُبنى يومُ الحضور من العطل
والإجازات المعتمدة والإعفاءات، **وتُقرأ كلُّها لحظةَ الاحتساب** — فكلّ ما
يُدخَل بعدُ عن يومٍ مضى لا يُغيّر حالته:
- عطلةٌ تُضاف لاحقًا → اليوم يبقى **غيابًا** (اليوم الوطني: ١٤ موظفًا)
- ⭐ **إجازةٌ تُعتمد بعد يومين** → أيّامها تبقى غيابًا، **وهو الأشيع**

⚠️ **والأثر ماليّ**: اليوم الغائب يُنشئ خصمًا ويُقترح عليه جزاء — ووُجد فعلًا
١٤ خصمًا بـ٢٧٨٤ ريالًا على يومٍ هو عطلة رسميّة.
"""
from pathlib import Path

SIG = Path("apps/attendance/signals.py")
REC = Path("apps/attendance/services/recompute.py")


def test_signals_are_registered_on_ready():
    """⭐ بلا `ready()` لا تُسجَّل الإشارات، فلا يُعاد احتساب شيء."""
    s = Path("apps/attendance/apps.py").read_text(encoding="utf-8")
    assert "def ready" in s and "signals.register()" in s, (
        "⚠️ الإشارات غير مربوطة — فما يُدخَل عن الماضي لا يُعيد الاحتساب")


def test_every_retroactive_source_has_a_signal():
    """⚠️ المصادر الثلاثة: العطل · الإجازات المعتمدة · الإعفاءات."""
    s = SIG.read_text(encoding="utf-8")
    for model in ("Holiday", "Request", "AttendanceExemption"):
        assert f"sender={model}" in s, f"⚠️ لا إشارة لـ{model}"


def test_cancelled_leave_also_recomputes():
    """
    ⚠️ **الإلغاء كالاعتماد**: إجازةٌ تُلغى بعد تطبيقها تترك أيّامها «إجازة»
    وهي ليست كذلك — فلا يُخصم عمّا يستحقّ الخصم.
    """
    assert "RequestStatus.CANCELLED" in SIG.read_text(encoding="utf-8"), (
        "⚠️ الإلغاء لا يُعيد الاحتساب")


def test_recompute_runs_in_background():
    """⚠️ إعادةُ احتساب شركةٍ لشهرٍ لا تُنفَّذ داخل الطلب — فتُعلّق الواجهة."""
    assert "apply_async" in SIG.read_text(encoding="utf-8"), (
        "⚠️ تُنفَّذ في الطلب لا في الخلفية")


def test_stale_deductions_are_dropped():
    """
    ⚠️⚠️ **الخصم يتبع اليوم لا يسبقه**: إعادةُ الاحتساب تُصحّح حالة اليوم،
    والخصمُ المُنشأ عليه يبقى — ١٤ خصمًا على يومٍ صار عطلةً رسميّة.
    """
    s = REC.read_text(encoding="utf-8")
    assert "_drop_stale_deductions" in s, "⚠️ الخصم الساقط يبقى"


def test_applied_deductions_are_never_deleted_silently():
    """
    ⚠️ **المعتمد لا يُمسّ**: قرارٌ بشريٌّ قد يكون دخل مسيرًا معتمدًا —
    فيُسجَّل تحذيرٌ ويُترك لقرارٍ بشريّ، لا يُمحى بصمت.
    """
    s = REC.read_text(encoding="utf-8")
    assert "exclude(status=AttendanceDeductionStatus.APPLIED)" in s, (
        "⚠️ الخصم المعتمد يُحذف بصمت")
    assert "logger.warning" in s, "⚠️ لا تحذير عند وجود معتمدٍ ساقط"


def test_one_employee_failure_does_not_stop_the_rest():
    """⚠️ فشلُ موظفٍ لا يُوقف إعادة احتساب الشركة كلّها."""
    s = REC.read_text(encoding="utf-8")
    assert "logger.exception" in s, "⚠️ الفشل يمرّ صامتًا أو يُوقف البقيّة"
