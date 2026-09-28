"""
حرّاس دورة الفوترة والخروج (ق-٢٧٨ · ٢٨٠ · ٢٨٤ · ٢٩١).

⚠️⚠️ كلّها **علل وقعت فعلًا** في تجربة سدرة يوم ٢٨ سبتمبر — لا فرضيّات.
"""
from pathlib import Path

BILLING_API = Path("apps/accounts/api_billing.py")
BILLING_SVC = Path("apps/accounts/services/billing_v2.py")
SETTLEMENT = Path("apps/payroll/services/settlement.py")
JOB_CHANGES = Path("apps/employees/services/job_changes.py")
EMP_API = Path("apps/employees/api.py")
ENGINE = Path("apps/payroll/services/engine.py")


def test_zero_custom_price_never_saved():
    """
    ⚠️⚠️ ق-٢٧٨: **سعرٌ خاصٌّ بصفرٍ يُلغي الاشتراك ماليًّا.**

    حقلٌ فارغٌ في الشاشة يصل `"0"`، و`Decimal("0")` تمرّ من
    `is not None` **فتُحفظ سعرًا**: كل فواتير الحساب بصفر.
    (وقع لسدرة: ثلاثة إيصالات بصفر ريال.)
    """
    s = BILLING_SVC.read_text(encoding="utf-8")
    assert "custom_price is not None and custom_price > 0" in s, (
        "⚠️ سعرٌ خاصٌّ بصفر يُحفظ — ولا يُحصَّل ريال")


def test_pending_invoice_matches_cycle():
    """
    ⚠️⚠️ ق-٢٨٠: **كل ضغطةٍ كانت تُنشئ إيصالًا** — ومن بدّل الشهريّ
    بالسنويّ كان يُعاد له **إيصالُه الشهريّ**.
    """
    s = BILLING_API.read_text(encoding="utf-8")
    assert "def _pending_invoice" in s, "⚠️ لا منعَ لتكرار الإيصالات"
    i = s.index("def _pending_invoice")
    body = s[i:i + 1200]
    assert "cycle=sub.cycle" in body, (
        "⚠️ الإيصال يُعاد بلا مطابقة الدورة — فيرى العميل سعرًا آخر")


def test_no_invoice_issued_before_payment():
    """
    ⭐ ق-٢٨٤: **لا إيصالَ يراه العميل قبل دفعٍ حقيقيّ** (قرار جواد).

    يبقى **مسودّةً** حتى الدفع أو التفعيل من اللوحة — فلا تتراكم
    إيصالاتٌ ميّتة، **ولا يستهلك كودُ الخصم عدّاده بلا دفع**.
    """
    api = BILLING_API.read_text(encoding="utf-8")
    i = api.index("def start_checkout")
    j = api.index("\ndef ", i + 10)
    assert "billing.issue_invoice" not in api[i:j], (
        "⚠️ الإيصال يُصدر عند الضغط — فتتراكم إيصالاتٌ لم تُدفع")

    assert "status=InvoiceStatus.DRAFT" in api, (
        "⚠️ المسودّة تظهر للعميل — وهي ليست إيصالًا بعد")

    svc = BILLING_SVC.read_text(encoding="utf-8")
    k = svc.index("def mark_paid")
    assert "issue_invoice(invoice)" in svc[k:k + 900], (
        "⚠️ الدفع لا يُصدر المسودّة — فلا إيصالَ لمن دفع")


def test_dismissal_terminates_employment():
    """
    ⚠️⚠️⚠️ ق-٢٩٠: **اعتماد الفصل يُنهي الخدمة فورًا** (قرار جواد).

    كان يُعلّم الملف وحده فيبقى «على رأس العمل»: **راتبه يُصرف في
    المسير التالي، ورصيد إجازاته ينمو**. و`TERMINATED` كانت تُقرأ في
    خمسة مواضع **ولا أحد يكتبها** — نمطٌ تكرّر: حقلٌ يُقرأ ولا يُكتب.
    """
    s = JOB_CHANGES.read_text(encoding="utf-8")
    assert "EmploymentStatus.TERMINATED" in s, (
        "⚠️ الفصل المعتمَد لا يُنهي الخدمة — والمفصول يبقى في المسير")


def test_terminated_hidden_from_employee_list():
    """
    ⚠️ ق-٢٨٩: **المنتهية خدمته يختفي من القائمة** — ولا يُحذف شيء.
    فقائمةٌ تخلط العامل بالمنتهي **تُربك كل عملية**.
    """
    s = EMP_API.read_text(encoding="utf-8")
    assert "exclude(status=EmploymentStatus.TERMINATED)" in s, (
        "⚠️ المنتهون يظهرون في قائمة الموظفين")


def test_no_settlement_for_active_employee():
    """
    ⚠️⚠️ ق-٢٩١: **لا مخالصةَ لعاملٍ على رأس العمل** (قرار جواد).

    فالمخالصة تصفيةُ حسابٍ **بعد** انتهاء الخدمة: إصدارها لعاملٍ
    **يُنشئ مستحقّاتٍ وهميّة**، ويُدخل مكافأةً لمن لم يخرج.
    """
    s = SETTLEMENT.read_text(encoding="utf-8")
    i = s.index("def create_settlement_run")
    body = s[i:i + 1600]
    assert "EmploymentStatus.TERMINATED" in body, (
        "⚠️ المخالصة تُصدر لعاملٍ قائم — فمستحقّاتٌ وهميّة")


def test_settlement_approval_terminates_too():
    """⭐ ق-٢٨٨: واعتماد مخالصةٍ يُنهي الخدمة كذلك — طبقةٌ ثانية."""
    s = ENGINE.read_text(encoding="utf-8")
    assert "_terminate_on_settlement" in s, (
        "⚠️ اعتماد المخالصة لا يُنهي الخدمة")
