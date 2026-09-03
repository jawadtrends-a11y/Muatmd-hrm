"""
سجل أحداث الإشعارات.

كل حدث مسجّل هنا وله قوالب بالثلاث لغات — حارس آلي يفرض ذلك.
الحد الأدنى لكل موديول محدد في الوثيقة المعمارية (2) القسم 5.1.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EventSpec:
    key: str
    module: str
    name_ar: str
    channels: tuple = ("in_app",)
    is_mandatory: bool = False


def _e(key, module, name_ar, channels=("in_app",), mandatory=False):
    return EventSpec(key, module, name_ar, tuple(channels), mandatory)


EVENTS = [
    # ══ الموظفون ══
    _e("employee.hired", "employees", "تعيين موظف جديد", ("in_app", "email")),
    _e("employee.document_expiring", "employees", "قرب انتهاء وثيقة",
       ("in_app", "email", "whatsapp"), mandatory=True),
    _e("employee.terminated", "employees", "إنهاء خدمة موظف",
       ("in_app", "email"), mandatory=True),

    # ══ الحضور ══
    _e("attendance.absent", "attendance", "غياب بلا إذن", ("in_app",)),
    _e("attendance.missing_punch", "attendance", "نسيان بصمة انصراف",
       ("in_app", "whatsapp")),

    # ══ الإجازات ══
    _e("leave.submitted", "leaves", "تقديم طلب إجازة", ("in_app",)),
    _e("leave.approved", "leaves", "اعتماد إجازة", ("in_app", "whatsapp")),
    _e("leave.rejected", "leaves", "رفض إجازة", ("in_app", "whatsapp")),
    _e("leave.balance_low", "leaves", "رصيد إجازات منخفض", ("in_app",)),

    # ══ الطلبات ══
    _e("request.submitted", "requests", "تقديم طلب", ("in_app",)),
    _e("request.pending_approval", "requests", "طلب بانتظار اعتمادك",
       ("in_app", "email")),
    _e("request.approved", "requests", "اعتماد طلب", ("in_app", "whatsapp")),
    _e("request.rejected", "requests", "رفض طلب", ("in_app", "whatsapp")),
    _e("request.sla_breached", "requests", "تأخر اعتماد عن المدة المحددة",
       ("in_app", "email")),

    # الإنابة أثناء الغياب (ق-75)
    _e("delegation.requested", "requests", "طلب إنابة عنك أثناء غيابه",
       ("in_app", "email")),
    _e("delegation.accepted", "requests", "قبول الإنابة", ("in_app",)),
    _e("delegation.declined", "requests", "الاعتذار عن الإنابة",
       ("in_app",)),

    # ══ الرواتب ══
    _e("payroll.calculation_started", "payroll", "بدء احتساب المسير", ("in_app",)),
    _e("payroll.calculation_completed", "payroll", "اكتمال احتساب المسير",
       ("in_app", "email")),
    _e("payroll.variance_detected", "payroll", "فروقات تحتاج مراجعة",
       ("in_app", "email"), mandatory=True),
    _e("payroll.submitted", "payroll", "رفع المسير للاعتماد", ("in_app", "email")),
    _e("payroll.approved", "payroll", "اعتماد المسير",
       ("in_app", "email"), mandatory=True),
    _e("payslip.available", "payroll", "إتاحة قسيمة الراتب",
       ("in_app", "whatsapp")),
    # ══ الاشتراك والفوترة (ق-48) ══
    _e("subscription.renewal_due", "billing",
       "تنبيه قرب انتهاء الاشتراك",
       ("in_app", "email"), mandatory=True),
    _e("subscription.renewal_failed", "billing",
       "فشل التجديد التلقائي",
       ("in_app", "email"), mandatory=True),
    _e("subscription.expired", "billing",
       "انتهاء الاشتراك",
       ("in_app", "email"), mandatory=True),

    # ══ التوطين والامتثال ══
    _e("nitaqat.band_changed", "compliance", "تغيّر نطاق المنشأة",
       ("in_app", "email"), mandatory=True),
    _e("nitaqat.at_risk", "compliance", "تحذير قبل الهبوط لنطاق أدنى",
       ("in_app", "email"), mandatory=True),

    # ══ النظام والاشتراك ══
    _e("subscription.trial_ending", "account", "قرب انتهاء التجربة",
       ("in_app", "email"), mandatory=True),
    _e("subscription.past_due", "account", "تأخر السداد",
       ("in_app", "email"), mandatory=True),
    _e("subscription.downgraded", "account", "تنزيل الباقة",
       ("in_app", "email"), mandatory=True),
    _e("access.role_changed", "access", "تغيير صلاحياتك",
       ("in_app", "email"), mandatory=True),
]

EVENT_KEYS = {e.key for e in EVENTS}
EVENTS_BY_KEY = {e.key: e for e in EVENTS}
MANDATORY_KEYS = {e.key for e in EVENTS if e.is_mandatory}


def validate_event_key(key):
    if key not in EVENT_KEYS:
        raise ValueError(f"حدث غير مسجّل: {key}")
    return True
