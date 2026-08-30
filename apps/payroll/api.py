"""
API الرواتب: المكوّنات، الإعدادات، وحاسبة نهاية الخدمة.

كل نقطة تمر بالبوابات الثلاث: الميزة ← الصلاحية ← النطاق.
"""
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.payroll.models import (
    ComponentType, EOSBWageBasis, OvertimeBasis, PayComponent, PayrollSettings,
)


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _dec(value, field):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError(f"قيمة غير صالحة في {field}: {value}")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def components(request):
    """مكوّنات الأجر بأعلامها الأربعة."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "payroll.view")
        qs = Gate.filter_queryset(request.user, "payroll.view",
                                  PayComponent.objects.all())
        return Response([
            {
                "id": c.id, "code": c.code, "name_ar": c.name_ar,
                "component_type": c.component_type,
                "is_gosi_subject": c.is_gosi_subject,
                "is_eosb_subject": c.is_eosb_subject,
                "is_overtime_base": c.is_overtime_base,
                "is_wps_subject": c.is_wps_subject,
                "is_system": c.is_system, "is_active": c.is_active,
                "display_order": c.display_order,
            }
            for c in qs.filter(company_id=company_id)
        ])

    Gate.require(request.user, "payroll.structures")
    from apps.accounts.models import Company
    comp_qs = Gate.filter_queryset(request.user, "company.view",
                                   Company.objects.all())
    company = comp_qs.filter(id=company_id).first()
    code = (request.data.get("code") or "").strip().upper()
    if not code:
        return Response({"detail": "الرمز مطلوب"}, status=400)
    # فحص التكرار عبر البوابة — لا يكشف وجود مكوّن خارج نطاق المستخدم
    existing = Gate.filter_queryset(
        request.user, "payroll.structures", PayComponent.objects.all())
    if existing.filter(company_id=company_id, code=code).exists():
        return Response({"detail": f"الرمز مستخدم: {code}"}, status=409)

    c = PayComponent.objects.create(
        account=company.account, company=company, code=code,
        name_ar=request.data.get("name_ar", ""),
        name_en=request.data.get("name_en", ""),
        name_ur=request.data.get("name_ur", ""),
        component_type=request.data.get("component_type",
                                        ComponentType.EARNING),
        is_gosi_subject=request.data.get("is_gosi_subject", False),
        is_eosb_subject=request.data.get("is_eosb_subject", False),
        is_overtime_base=request.data.get("is_overtime_base", False),
        is_wps_subject=request.data.get("is_wps_subject", True),
        display_order=request.data.get("display_order", 50),
    )
    return Response({"id": c.id, "code": c.code}, status=201)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def component_flags(request, component_id):
    """
    تعديل الأعلام الأربعة — يُرجع تحذيرات الاستثناء (ق-23).
    النظام ينبّه ولا يمنع.
    """
    Gate.require(request.user, "payroll.structures")
    company_id = _company_id(request)
    qs = Gate.filter_queryset(request.user, "payroll.structures",
                              PayComponent.objects.all())
    comp = qs.filter(id=component_id, company_id=company_id).first()
    if comp is None:
        return Response({"detail": "المكوّن غير موجود"}, status=404)

    from apps.payroll.services.components import set_component_flags
    warnings = set_component_flags(
        comp,
        is_gosi_subject=request.data.get("is_gosi_subject"),
        is_eosb_subject=request.data.get("is_eosb_subject"),
        is_overtime_base=request.data.get("is_overtime_base"),
        is_wps_subject=request.data.get("is_wps_subject"),
    )
    comp.refresh_from_db()
    return Response({
        "id": comp.id, "code": comp.code,
        "is_gosi_subject": comp.is_gosi_subject,
        "is_eosb_subject": comp.is_eosb_subject,
        "is_overtime_base": comp.is_overtime_base,
        "is_wps_subject": comp.is_wps_subject,
        "warnings": warnings,
    })


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def payroll_settings(request):
    """إعدادات الرواتب — تقود كل الحسابات."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    perm = "payroll.view" if request.method == "GET" else "payroll.structures"
    Gate.require(request.user, perm)
    qs = Gate.filter_queryset(request.user, perm, PayrollSettings.objects.all())
    s = qs.filter(company_id=company_id).first()
    if s is None:
        return Response({"detail": "لا إعدادات لهذه الشركة"}, status=404)

    if request.method == "PUT":
        for field in ("payroll_days_per_month", "working_hours_per_day",
                      "ramadan_hours_per_day", "overtime_basis",
                      "eosb_wage_basis", "exclude_unpaid_leave_from_service",
                      "company_bears_employee_gosi",
                      "merge_supplementary_into_regular",
                      "terminated_pay_in_regular_run",
                      "exclude_zero_net_from_wps", "variance_threshold_percent"):
            if field in request.data:
                setattr(s, field, request.data[field])
        s.save()

    return Response({
        "payroll_days_per_month": s.payroll_days_per_month,
        "working_hours_per_day": str(s.working_hours_per_day),
        "ramadan_hours_per_day": str(s.ramadan_hours_per_day),
        "overtime_basis": s.overtime_basis,
        "overtime_basis_options": [
            {"value": v, "label": str(l)} for v, l in OvertimeBasis.choices],
        "eosb_wage_basis": s.eosb_wage_basis,
        "eosb_wage_basis_options": [
            {"value": v, "label": str(l)} for v, l in EOSBWageBasis.choices],
        "eosb_basis_required": s.eosb_wage_basis == EOSBWageBasis.NOT_SET,
        "exclude_unpaid_leave_from_service": s.exclude_unpaid_leave_from_service,
        "company_bears_employee_gosi": s.company_bears_employee_gosi,
        "merge_supplementary_into_regular": s.merge_supplementary_into_regular,
        "terminated_pay_in_regular_run": s.terminated_pay_in_regular_run,
        "exclude_zero_net_from_wps": s.exclude_zero_net_from_wps,
        "variance_threshold_percent": str(s.variance_threshold_percent),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def eosb_calculator(request):
    """
    حاسبة مكافأة نهاية الخدمة — مطابقة للحاسبة الحكومية (ق-25).
    تُرجع شرح الاحتساب كاملًا ليعيد الموظف الحساب بورقة وقلم.
    """
    from datetime import date

    Gate.require(request.user, "payroll.view")
    company_id = _company_id(request)
    qs = Gate.filter_queryset(request.user, "payroll.view",
                              PayrollSettings.objects.all())
    settings_obj = qs.filter(company_id=company_id).first()
    if settings_obj is None:
        return Response({"detail": "لا إعدادات لهذه الشركة"}, status=404)

    from apps.payroll.services.eosb import (
        ALL_REASONS, EOSBBasisNotSet, EOSBError, calculate_eosb,
        calculate_unlawful_termination_compensation,
    )

    try:
        join = date.fromisoformat(request.data["join_date"])
        end = date.fromisoformat(request.data["end_date"])
        wage = _dec(request.data["eosb_wage"], "eosb_wage")
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات ناقصة أو غير صالحة: {e}"},
                        status=400)

    reason = request.data.get("reason_code", "")
    try:
        result = calculate_eosb(
            join_date=join, end_date=end, eosb_wage=wage,
            reason_code=reason,
            unpaid_leave_days=int(request.data.get("unpaid_leave_days", 0)),
            exclude_unpaid_leave=settings_obj.exclude_unpaid_leave_from_service,
            wage_basis_set=(settings_obj.eosb_wage_basis
                            != EOSBWageBasis.NOT_SET),
        )
    except EOSBBasisNotSet as e:
        return Response({"detail": str(e), "code": "eosb_basis_not_set",
                         "settings_url": "/settings/payroll"}, status=409)
    except EOSBError as e:
        return Response({"detail": str(e), "code": "invalid_input",
                         "available_reasons": [
                             {"code": k, "label": v}
                             for k, v in ALL_REASONS.items()]},
                        status=400)

    payload = {
        "service_days": result.service_days,
        "service_years": str(result.service_years),
        "eosb_wage": str(result.eosb_wage),
        "gross_award": str(result.gross_award),
        "entitlement_ratio": str(result.entitlement_ratio),
        "net_award": str(result.net_award),
        "reason_code": result.reason_code,
        "reason_label": result.reason_label,
        "explanation": result.explanation,
        "warnings": result.warnings,
        "compensation_article_77": None,
    }

    # تعويض المادة 77 — بند مستقل (ق-26)
    if reason == "unlawful_termination":
        agreed = request.data.get("agreed_compensation")
        comp = calculate_unlawful_termination_compensation(
            monthly_wage=wage, service_days=result.service_days,
            contract_type=request.data.get("contract_type", "indefinite"),
            remaining_contract_months=(
                _dec(request.data["remaining_contract_months"],
                     "remaining_contract_months")
                if request.data.get("remaining_contract_months") else None),
            agreed_amount=_dec(agreed, "agreed_compensation") if agreed else None,
        )
        payload["compensation_article_77"] = {
            "amount": str(comp.amount),
            "months_equivalent": str(comp.months_equivalent),
            "minimum_applied": comp.minimum_applied,
            "explanation": comp.explanation,
            "note": "بند مستقل يُصرف بالإضافة إلى المكافأة لا بدلًا عنها",
        }
        payload["total_due"] = str(result.net_award + comp.amount)

    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def termination_reasons(request):
    """قائمة أسباب انتهاء العلاقة — من المرجع الحكومي حرفيًا (ق-26)."""
    Gate.require(request.user, "payroll.view")
    from apps.payroll.services.eosb import (
        ALL_REASONS, FULL_ENTITLEMENT, NO_ENTITLEMENT, PRORATED_ENTITLEMENT,
    )
    return Response({
        "source": "حاسبة مكافأة نهاية الخدمة الرسمية — وزارة الموارد البشرية",
        "reasons": [
            {
                "code": code, "label": label,
                "entitlement": ("full" if code in FULL_ENTITLEMENT
                                else "none" if code in NO_ENTITLEMENT
                                else "prorated"),
                "requires_compensation_77": code == "unlawful_termination",
            }
            for code, label in ALL_REASONS.items()
        ],
        "total": len(ALL_REASONS),
    })
