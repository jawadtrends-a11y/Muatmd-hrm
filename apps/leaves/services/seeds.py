"""
بذرة أنواع الإجازات وسلاسل الاعتماد.

⚠️ المدد بذرة أولية من النظام السعودي — الشركة تعدّل كل شيء (ق-32).
الحد النظامي الأدنى وحده يُمنع النزول عنه (ق-34).
"""
from decimal import Decimal as D

from django.db import transaction

from apps.leaves.models import (
    AccrualMethod, ApprovalChain, ApprovalStep, ApproverType,
    CarryForwardPolicy, GenderRestriction, HolidayTreatment, LeaveTier,
    LeaveType, RequestType,
)

# (code, name_ar, name_en, name_ur, spec)
DEFAULT_LEAVE_TYPES = [
    ("ANNUAL", "إجازة سنوية", "Annual Leave", "سالانہ چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.MONTHLY,
        "days_per_year": D("21"), "days_after_five_years": D("30"),
        "statutory_min": D("21"),
        "carry": CarryForwardPolicy.CAPPED, "max_carry": D("21"),
        "holiday": HolidayTreatment.EXTENDS,
        "weekend": HolidayTreatment.COUNTED,
        "order": 10,
    }),
    ("SICK", "إجازة مرضية", "Sick Leave", "بیماری کی چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.ANNUAL,
        "days_per_year": D("120"), "requires_attachment": True,
        "carry": CarryForwardPolicy.EXPIRE,
        "holiday": HolidayTreatment.COUNTED,
        "weekend": HolidayTreatment.COUNTED,
        "tiers": [(1, 30, D("100")), (31, 90, D("75")), (91, 120, D("0"))],
        "order": 20,
    }),
    ("MARRIAGE", "إجازة زواج", "Marriage Leave", "شادی کی چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.PER_EVENT,
        "days_per_event": D("5"), "statutory_min": D("5"),
        "carry": CarryForwardPolicy.EXPIRE, "order": 30,
    }),
    ("NEWBORN", "إجازة مولود", "Newborn Leave", "بچے کی پیدائش کی چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.PER_EVENT,
        "days_per_event": D("3"), "statutory_min": D("3"),
        "gender": GenderRestriction.MALE,
        "carry": CarryForwardPolicy.EXPIRE, "order": 40,
    }),
    ("BEREAVEMENT", "إجازة وفاة", "Bereavement Leave", "سوگ کی چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.PER_EVENT,
        "days_per_event": D("5"), "statutory_min": D("5"),
        "carry": CarryForwardPolicy.EXPIRE, "order": 50,
    }),
    ("HAJJ", "إجازة حج", "Hajj Leave", "حج کی چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.PER_EVENT,
        "days_per_event": D("10"), "statutory_min": D("10"),
        "muslim_only": True, "min_service_months": 24,
        "once_per_service": True,
        "carry": CarryForwardPolicy.EXPIRE, "order": 60,
    }),
    ("IDDAH", "إجازة عدّة", "Iddah Leave", "عدت کی چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.PER_EVENT,
        "days_per_event": D("130"), "gender": GenderRestriction.FEMALE,
        "muslim_only": True, "carry": CarryForwardPolicy.EXPIRE,
        "order": 70,
    }),
    ("MATERNITY", "إجازة وضع", "Maternity Leave", "زچگی کی چھٹی", {
        "is_paid": True, "accrual": AccrualMethod.PER_EVENT,
        "days_per_event": D("84"), "gender": GenderRestriction.FEMALE,
        "requires_attachment": True, "carry": CarryForwardPolicy.EXPIRE,
        "order": 80,
    }),
    ("UNPAID", "إجازة بلا أجر", "Unpaid Leave", "بلا معاوضہ چھٹی", {
        "is_paid": False, "pay_percentage": D("0"),
        "accrual": AccrualMethod.NONE,
        "carry": CarryForwardPolicy.EXPIRE,
        "holiday": HolidayTreatment.COUNTED,
        "weekend": HolidayTreatment.COUNTED,
        "order": 90,
    }),
]


@transaction.atomic
def provision_leave_types(company):
    """ينشئ أنواع الإجازات لشركة جديدة. آمن للتكرار."""
    created = []
    for code, ar, en, ur, spec in DEFAULT_LEAVE_TYPES:
        lt, is_new = LeaveType.objects.get_or_create(
            company=company, code=code,
            defaults={
                "account": company.account,
                "name_ar": ar, "name_en": en, "name_ur": ur,
                "is_paid": spec.get("is_paid", True),
                "pay_percentage": spec.get("pay_percentage", D("100")),
                "accrual_method": spec.get("accrual", AccrualMethod.ANNUAL),
                "days_per_year": spec.get("days_per_year"),
                "days_after_five_years": spec.get("days_after_five_years"),
                "days_per_event": spec.get("days_per_event"),
                "statutory_min_days": spec.get("statutory_min"),
                "carry_forward_policy": spec.get(
                    "carry", CarryForwardPolicy.EXPIRE),
                "max_carry_forward_days": spec.get("max_carry"),
                "holiday_treatment": spec.get(
                    "holiday", HolidayTreatment.EXTENDS),
                "weekend_treatment": spec.get(
                    "weekend", HolidayTreatment.COUNTED),
                "gender_restriction": spec.get(
                    "gender", GenderRestriction.ANY),
                "muslim_only": spec.get("muslim_only", False),
                "min_service_months": spec.get("min_service_months", 0),
                "once_per_service": spec.get("once_per_service", False),
                "requires_attachment": spec.get("requires_attachment", False),
                "is_system": True,
                "display_order": spec.get("order", 0),
            })
        if is_new:
            created.append(code)
            for lo, hi, pct in spec.get("tiers", []):
                LeaveTier.objects.create(leave_type=lt, from_day=lo,
                                         to_day=hi, pay_percentage=pct)
    return created


# ── سلاسل الاعتماد الافتراضية (ق-9: تعدّلها الشركة) ──
DEFAULT_CHAINS = [
    (RequestType.LEAVE, "اعتماد الإجازات — درجة واحدة", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 48)]),
    (RequestType.LEAVE, "إجازة طويلة — درجتان", {"days_gt": 5}, 10,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 48),
      (2, ApproverType.ROLE, "hr_manager", True, 72)]),
    (RequestType.ADVANCE, "اعتماد السلف", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 48),
      (2, ApproverType.ROLE, "hr_manager", True, 72)]),
    (RequestType.PERMISSION, "الاستئذان — المدير المباشر", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 24)]),
    (RequestType.CERTIFICATE, "الشهادات والخطابات", {}, 0,
     [(1, ApproverType.ROLE, "hr_staff", True, 48)]),
    (RequestType.RESIGNATION, "الاستقالة", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 72),
      (2, ApproverType.ROLE, "hr_manager", True, 72),
      (3, ApproverType.ROLE, "owner", True, None)]),

    # ── الأنواع المضافة (ق-54) ──

    # تصحيح البصمة: المدير المباشر يعرف إن كان الموظف حاضرًا
    (RequestType.ATTENDANCE_FIX, "تصحيح البصمة — المدير المباشر", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 24)]),

    # العمل عن بُعد: المدير المباشر، ودرجة ثانية للمدد الطويلة
    (RequestType.REMOTE_WORK, "العمل عن بُعد — المدير المباشر", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 24)]),
    (RequestType.REMOTE_WORK, "عمل عن بُعد ممتد — درجتان",
     {"days_gt": 5}, 10,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 24),
      (2, ApproverType.ROLE, "hr_manager", True, 48)]),

    # الإضافي: المدير يعتمد، والموارد تراجع أثره المالي
    (RequestType.OVERTIME, "اعتماد العمل الإضافي", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 48),
      (2, ApproverType.ROLE, "hr_staff", True, 72)]),

    # العهدة: الموارد تسجّلها فهي مسؤولة عن جردها
    (RequestType.ASSET, "تسجيل العهدة", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 48),
      (2, ApproverType.ROLE, "hr_staff", True, 72)]),

    # التذكرة: استحقاق سنوي — الموارد ثم المالية عبر المالك
    (RequestType.TICKET, "تذكرة السفر السنوية", {}, 0,
     [(1, ApproverType.ROLE, "hr_manager", True, 72),
      (2, ApproverType.ROLE, "owner", True, None)]),

    # رحلة العمل: المدير ثم الموارد — والبدل بسياسة المنشأة
    (RequestType.BUSINESS_TRIP, "رحلة العمل", {}, 0,
     [(1, ApproverType.DIRECT_MANAGER, "", True, 48),
      (2, ApproverType.ROLE, "hr_manager", True, 72)]),
]


@transaction.atomic
def provision_approval_chains(company):
    """ينشئ السلاسل الافتراضية. الشركة تعدّلها بحرية (ق-9)."""
    created = []
    for req_type, name, cond, prio, steps in DEFAULT_CHAINS:
        chain, is_new = ApprovalChain.objects.get_or_create(
            company=company, request_type=req_type, name_ar=name,
            defaults={"account": company.account,
                      "condition_json": cond, "priority": prio})
        if is_new:
            created.append(name)
            for order, atype, role, mandatory, sla in steps:
                ApprovalStep.objects.create(
                    chain=chain, step_order=order, approver_type=atype,
                    approver_role_code=role, is_mandatory=mandatory,
                    sla_hours=sla)
    return created
