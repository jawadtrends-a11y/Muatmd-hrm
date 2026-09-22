"""
الفترة الافتراضية للشركة (ق-235).

⚠️⚠️ **مبدأ النظام «لا موظف بلا فترة — ومن لم تُسند له يتبع الافتراضية»**
(effective_shift) **يفترض أن لكل شركةٍ فترةً افتراضية — والتأسيس لم يُنشئها**:
فكلّ شركةٍ جديدة بلا فترة ← **لا غياب ولا تأخير يُحسب لأحدٍ فيها**.

**قرار جواد**: ٨:٠٠–١٧:٠٠ · ساعة راحة · سماح ١٥ دقيقة · الأحد → الخميس.
⚠️ **والترقيم ترقيم النظام** (0=الأحد … 6=السبت) — لا ترقيم بايثون (الاثنين=0):
فالخلط يجعل الجمعة والسبت دوامًا.
"""
from datetime import time

SUN_TO_THU = [0, 1, 2, 3, 4]


def ensure_default_shift(company):
    """تُنشئ الافتراضية إن لم توجد — ولا تمسّ ما عدّلته الشركة."""
    from apps.attendance.models import Shift
    if Shift.objects.filter(company_id=company.id, is_default=True).exists():
        return None
    code = "DEFAULT" if not Shift.objects.filter(
        company_id=company.id, code="DEFAULT").exists() else "DEFAULT-2"
    return Shift.objects.create(
        account_id=company.account_id, company_id=company.id, code=code,
        name_ar="الدوام الرسمي", name_en="Standard shift",
        start_time=time(8, 0), end_time=time(17, 0), break_minutes=60,
        grace_in_minutes=15, working_days=SUN_TO_THU,
        is_default=True, is_active=True)
