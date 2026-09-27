"""
حارس: تغييرُ الباقة أو الميزة يُبطل ذاكرة المزايا فورًا (ق-٢٧٣).

⚠️⚠️ **حزمة المزايا مخزّنة خمس دقائق** (`Features.bundle`). فتفعيلُ اشتراكٍ
أو تعديلُ باقةٍ **بلا إبطالها لا يظهر أثره**: العميل يدفع ويبقى محجوبًا، ومن
فعّل من اللوحة يظنّ أن التفعيل فشل — **وهو نجح**.

**كُشفت في ق-٢٧٢**: أُضيفت `work_sites` للباقات الأربع، وبقيت `sites.*`
مقفلةً حتى مُسحت الذاكرة يدويًّا.
"""
from pathlib import Path

GATE = Path("apps/core/features/gate.py")
ADMIN = Path("apps/accounts/api_admin.py")
PLANS = Path("apps/accounts/api_plans.py")


def test_account_and_global_invalidation_exist():
    s = GATE.read_text(encoding="utf-8")
    assert "def invalidate_account" in s, (
        "⚠️ الاشتراك للحساب والذاكرة للشركة — فلا سبيل لمسح كل شركاته")
    assert "def invalidate_all" in s, (
        "⚠️ تعديلُ باقةٍ يمسّ كل مشتركيها ولا سبيل لمعرفتهم")


def test_activation_invalidates_the_whole_account():
    """
    ⚠️⚠️ **الاشتراك للحساب والذاكرة للشركة** — فمسحُ شركةٍ واحدة يترك
    البقيّة على باقتها القديمة حتى تنقضي المهلة.
    """
    assert "invalidate_account" in ADMIN.read_text(encoding="utf-8"), (
        "⚠️ التفعيل لا يُبطل الذاكرة — فالعميل يدفع ويبقى محجوبًا")


def test_plan_and_feature_edits_invalidate_everything():
    """⚠️ **تعديلُ باقةٍ أو ميزةٍ يمسّ كل عملائها** لا شركةً بعينها."""
    s = PLANS.read_text(encoding="utf-8")
    assert s.count("invalidate_all") >= 3, (
        "⚠️ موضعٌ من مواضع التعديل لا يُبطل الذاكرة")


def test_clear_failure_never_breaks_the_save():
    """⚠️ فشلُ المسح لا يُسقط الحفظ — والمهلة تُصلحه خلال خمس دقائق."""
    s = GATE.read_text(encoding="utf-8")
    i = s.index("def invalidate_all")
    body = s[i:i + 900]
    assert "except Exception" in body, "⚠️ فشلُ المسح يُسقط العملية"


def test_sites_permissions_are_not_a_tracking_feature():
    """
    ⚠️⚠️⚠️ ق-٢٧٢: **مواقع العمل أساسٌ للبصمة لا ميزةَ تتبّع.** كانت
    `sites.*` على `employee_tracking` (باقتان عُليا) و`mobile_punch` في
    الأربع — **فمن اشترى الأساسية اشترى بصمةً لا تعمل**.
    """
    cat = Path("apps/core/access/catalog.py").read_text(encoding="utf-8")
    i = cat.index('_p("sites.view"')
    assert 'feature="work_sites"' in cat[i:i + 400], (
        "⚠️ المواقع رُبطت بميزةٍ مدفوعة — فالبصمة تُباع ولا تعمل")
