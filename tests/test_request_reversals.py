"""
حارس: إلغاء أيّ طلبٍ معتمد وعكس أثره (ق-٢٦٨).

⚠️⚠️ **الاعتماد يُحدث أثرًا، والإلغاء كان يُغيّر حالةً فقط.** فالطلب المعتمد
يُنشئ سلفةً، أو يُعفي من البصمة، أو يعتمد ساعات إضافي — **وإلغاؤه بلا عكس
أثره يترك النظام مناقضًا لنفسه**: طلبٌ «ملغى» وسلفتُه تُخصم من المسير.

⭐ **قرار جواد: موظّف الموارد يُلغي أيّ طلبٍ بعد اعتماده.**
"""
from pathlib import Path

REV = Path("apps/leaves/services/reversals.py")
REQ = Path("apps/leaves/services/requests.py")
API = Path("apps/leaves/api.py")


def _body(name, span=2200):
    s = REV.read_text(encoding="utf-8")
    i = s.index(f"def {name}")
    return s[i:i + span]


def test_every_effect_with_state_has_a_reversal():
    """⭐ كل أثرٍ يُغيّر بياناتٍ محفوظة له عكسُه."""
    s = REV.read_text(encoding="utf-8")
    for t in ("ADVANCE", "ATTENDANCE_EXEMPTION", "OVERTIME", "PERMISSION",
              "SALARY_FIX"):
        assert f"RequestType.{t}" in s, f"⚠️ لا عكس لـ{t}"


def test_advance_with_partial_repayment_is_refused():
    """
    ⚠️⚠️ **سلفةٌ بدأ سدادها لا تُلغى** (قرار جواد): المال خرج ولم يُستردّ
    كلُّه. لم تُستلم أقساط → إلغاء؛ سُدّدت كاملةً → `SETTLED`؛ جزئيًّا → يُمنع.
    """
    b = _body("revert_advance")
    assert "AdvanceStatus.CANCELLED" in b
    assert "AdvanceStatus.SETTLED" in b
    assert "لا تُلغى سلفةٌ بدأ سدادها" in b, "⚠️ تُلغى سلفةٌ صُرف بعضها"


def test_advance_is_found_by_link_not_by_text():
    """
    ⚠️⚠️ **`request` كان يسقط**: الحقل موجودٌ في `Advance` و`create_advance`
    يحفظه، **لكنّ الأثر لم يمرّره** — فكل سلفةٍ لا تعرف طلبها. (نمط ق-٢٥٨.)
    """
    assert "request=req," in REQ.read_text(encoding="utf-8"), (
        "⚠️ السلفة لا تُربط بطلبها")
    assert "Advance.objects.filter(request=req)" in _body("revert_advance"), (
        "⚠️ يُبحث عنها في النصّ لا بالربط")


def test_exemption_is_deactivated_not_deleted():
    """⚠️ الإعفاء يُعطَّل لا يُحذف — فسجلّ من أُعفي ومتى يبقى."""
    b = _body("revert_attendance_exemption")
    assert "is_active=False" in b
    assert ".delete()" not in b, "⚠️ يُحذف — والسجلّ يضيع"


def test_overtime_keeps_computed_minutes():
    """⚠️ **المحتسب بالبصمة يبقى** — المعتمد وحده يعود صفرًا."""
    b = _body("revert_overtime")
    assert "approved_overtime_minutes = 0" in b
    # ⚠️ **البصمة هي الحقيقة** (ق-١٨٤): `day.overtime_minutes` محتسبٌ منها،
    # فلا يُمسّ. والعكس يمحو **المعتمد** وحده.
    assert "day.overtime_minutes" not in b, "⚠️ يمحو ما احتسبته البصمة"


def test_permission_never_goes_below_zero():
    """⚠️ طرحُ الدقائق لا ينزل تحت الصفر."""
    assert "max(0," in _body("revert_permission")


def test_salary_fix_never_guesses_probation():
    """
    ⚠️⚠️ **لا يُعاد ما لا نعرف أصله**: فترة التجربة مدّةٌ لها أثرٌ في الفصل
    والحقوق — فإن لم تُحفظ السابقة، يُرفض ولا يُخمَّن تاريخ.
    """
    b = _body("revert_salary_fix")
    assert "previous_probation_end" in b
    assert "لا تُعرف فترة التجربة السابقة" in b


def test_reversal_failure_aborts_the_revocation():
    """
    ⚠️⚠️ **الفشل يُوقف الإلغاء** — بخلاف `apply_effect` حيث الاعتماد قرارٌ
    إداريٌّ تمّ. **فطلبٌ يُعلَن ملغىً وأثرُه قائم أسوأ من طلبٍ لم يُلغَ**.
    """
    b = _body("revoke_any_request", 2600)
    i_rev = b.index("revert_effect(request_obj)")
    i_status = b.index("RequestStatus.CANCELLED")
    assert i_rev < i_status, "⚠️ الحالة تتغيّر قبل نجاح العكس"
    assert "@transaction.atomic" in REV.read_text(encoding="utf-8")


def test_reason_is_required():
    assert "اكتب سبب الإلغاء" in _body("revoke_any_request", 2600)


def test_unknown_types_fall_through_safely():
    """⭐ ما لا أثر له يُلغى بتغيير الحالة — بلا استثناءٍ يدويّ لكل نوع."""
    b = _body("revert_effect")
    assert "لا أثر تلقائي لهذا النوع" in b
