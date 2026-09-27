"""
حارس: موقع العمل في الملفّ يُنشئ إسناد البصمة (ق-٢٦٩).

⚠️⚠️ **حقلان لغرضٍ واحد، والبصمة تقرأ الفارغ منهما.** الموارد تُسنِد
`Employment.primary_site` من ملفّ الموظف فيظهر «موقع العمل» — **والبصمة تقرأ
`SiteAssignment`**، جدولًا آخر. فظنّ المالك أن موظفيه مُسنَدون، **ولا أحد
منهم يستطيع البصم**: «لا موقع عمل مُسند إليك».

**سدرة عند الكشف:** ٤ مواقع · ٥ موظفين بموقعٍ في الملفّ · **صفر إسناد**.
(نمط ق-٢٥٨ — السادسة: اسمان لشيءٍ واحد، أو حقلٌ يُملأ ولا يُقرأ.)
"""
from pathlib import Path

API = Path("apps/employees/api.py")


def test_sync_exists_and_runs_on_save():
    """⭐ حفظُ موقع العمل يُنشئ الإسناد — فلا خطوة ثانية يُنساها أحد."""
    s = API.read_text(encoding="utf-8")
    assert "_sync_site_assignment" in s, "⚠️ الملفّ والبصمة لا يلتقيان"
    assert "emp.save()\n        _sync_site_assignment" in s, (
        "⚠️ المزامنة لا تعمل بعد الحفظ")


def test_existing_assignments_are_kept():
    """
    ⚠️ **الفنيّ يزور ثلاثة مواقع** (ق-٦٢) — فالمزامنة تُضيف الأساسيّ
    ولا تحذف ما أسندته شاشة المواقع.
    """
    s = API.read_text(encoding="utf-8")
    i = s.index("def _sync_site_assignment")
    body = s[i:i + 1800]
    assert "get_or_create" in body, "⚠️ يُنشئ مكرّرًا"
    assert ".delete()" not in body, "⚠️ يمحو إسنادات الفنيّ الأخرى"


def test_sync_failure_never_blocks_the_profile_save():
    """⚠️ فشلُ المزامنة لا يُسقط حفظ الملفّ — لكنّه يُسجَّل."""
    s = API.read_text(encoding="utf-8")
    i = s.index("def _sync_site_assignment")
    body = s[i:i + 1800]
    assert "except Exception" in body and "logger" in body.lower()
