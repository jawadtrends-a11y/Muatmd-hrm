"""
منح الإعفاء من البصمة — موضعٌ واحد (ق-229).

**قرار جواد**: مدير الموارد يُعفي مباشرةً — **بجوار** مسار الطلب
(ق-104) لا بدلًا منه. فمديرٌ يعرف أنّ موظفه ميدانيّ **لا ينتظر
الموظف ليطلب إعفاءه**.

⚠️⚠️ **وموضعٌ واحدٌ للإنشاء**: الطلب المعتمد والزرّ كلاهما يناديان
هنا — فلا طريقان يختلفان في قاعدةٍ (كإلغاء السابق الساري).
"""
from django.db import transaction
from django.utils import timezone

from apps.attendance.models_exemption import AttendanceExemption


class ExemptionError(Exception):
    """رسالةٌ تُسمّي المطلوب."""


@transaction.atomic
def grant_exemption(*, employment, start, end, reason, by_person_id,
                    request=None):
    if end and end < start:
        raise ExemptionError("تاريخ النهاية قبل تاريخ البداية")
    # والإعفاء السابق الساري يُلغى لا يُحذف — فلا إعفاءان لشخصٍ واحد
    AttendanceExemption.objects.filter(
        employment=employment, is_active=True
    ).update(is_active=False, revoked_at=timezone.now())
    return AttendanceExemption.objects.create(
        account_id=employment.account_id, company_id=employment.company_id,
        employment=employment, start_date=start, end_date=end,
        reason=str(reason or "")[:255], request=request,
        granted_by_person_id=by_person_id)
