"""
حارس: إلغاء إجازةٍ معتمدة (ق-٢٦٧).

⚠️⚠️ **لم يكن له سبيل.** `cancel_request` لمقدّم الطلب وما دام معلَّقًا فقط،
ولا شاشةَ لتسوية الرصيد — **فإجازةٌ اعتُمدت لا رجعةَ فيها**. وهي حالةٌ
واقعيّةٌ يوميّة: الموظف يعود مبكّرًا، أو تستدعيه الشركة، أو يمرض فتتحوّل
لمرضيّة. **ورصيدُه مخصومٌ وأيّامه مسجّلةٌ إجازةً.**
"""
from pathlib import Path

SVC = Path("apps/leaves/services/leave_requests.py")
API = Path("apps/leaves/api.py")


def _body(name, span=2800):
    s = SVC.read_text(encoding="utf-8")
    i = s.index(f"def {name}")
    return s[i:i + span]


def test_revoke_exists():
    assert "def revoke_approved_leave" in SVC.read_text(encoding="utf-8")


def test_balance_is_restored():
    """⭐ الرصيد يُردّ — عكس `consume` بالضبط."""
    assert "bal.consumed -= days" in _body("revoke_approved_leave"), (
        "⚠️ الرصيد لا يعود — مالٌ ضائع")


def test_applied_flag_is_cleared():
    """
    ⚠️⚠️ **`applied=False` هو المفتاح**: `leave_dates_in_range` تشترطه،
    فبدونه تبقى الأيّام «إجازة» مهما فعلنا.
    """
    assert 'payload["applied"] = False' in _body("revoke_approved_leave"), (
        "⚠️ الأيّام تبقى إجازةً بعد الإلغاء")


def test_reason_is_required():
    """⚠️ قرارٌ يمسّ رصيدًا ومالًا — فيُعلَّل ليُراجَع."""
    assert "اكتب سبب الإلغاء" in _body("revoke_approved_leave")


def test_retro_adjustment_is_reversed():
    """
    ⚠️⚠️ **وللإجازة أثرٌ ماليٌّ ثانٍ**: `_retro_leave` (ق-٦٩) تردّ للموظف خصمَ
    أيّامٍ كانت غيابًا في مسيرٍ أُغلق. فإلغاؤها بلا عكسها **يتركه قابضًا
    تعويضًا عن إجازةٍ لم تعد قائمة**.
    """
    s = SVC.read_text(encoding="utf-8")
    assert "_revoke_retro" in s, "⚠️ التسوية المالية لا تُعكس"
    b = _body("_revoke_retro")
    assert "RetroStatus.CANCELLED" in b, "⚠️ المعلَّقة لا تُلغى"
    assert "record_adjustment" in b, "⚠️ المصروفة بلا قيدٍ مضادّ"


def test_merged_retro_is_never_deleted():
    """⚠️ **المصروف لا يُمحى** — قيدٌ مضادّ يستردّه في المسير التالي."""
    b = _body("_revoke_retro")
    assert ".delete()" not in b, "⚠️ تسويةٌ مصروفةٌ تُحذف — والسجلّ يضيع"


def test_permission_is_not_a_paid_feature():
    """
    ⚠️ **`leaves.approve_all` لا `leaves.manage`**: الثانية مقيَّدة بميزةٍ
    مدفوعة — **وإلغاءُ إجازةٍ تصحيحٌ لازم لا ميزةٌ تُباع**.
    """
    s = API.read_text(encoding="utf-8")
    i = s.index("def revoke_leave_view")
    body = s[i - 400:i + 1400]
    assert 'Gate.require(request.user, "leaves.approve_all")' in body
