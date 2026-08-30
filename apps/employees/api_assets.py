"""
API السلف والعهد والوثائق (ق-41).

كل نقطة تمر بالبوابات: الصلاحية ← النطاق ← العزل.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.employees.models import Employment
from apps.employees.models_assets import (
    Advance, AdvanceStatus, Asset, AssetStatus, DocumentType,
    EmployeeDocument, RepaymentMethod,
)
from apps.employees.services.advances import (
    AdvanceError, AdvancesDisabled, approve_advance, check_eligibility,
    create_advance, outstanding_advances, total_outstanding,
)
from apps.employees.services.assets import (
    AssetError, add_document, assets_settlement, assign_asset,
    expiring_documents, return_asset,
)


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _settings(request):
    from apps.payroll.models import PayrollSettings
    return PayrollSettings.objects.filter(
        company_id=_company_id(request)).first()


def _get_employment(request, employment_id, permission):
    qs = Gate.filter_queryset(request.user, permission,
                              Employment.objects.all())
    return qs.filter(id=employment_id,
                     company_id=_company_id(request)).first()


def _dec(v, field):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValueError(f"قيمة غير صالحة في {field}: {v}")


# ══════════════════ السلف ══════════════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def advances(request):
    """قائمة السلف وإنشاؤها."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    settings_obj = _settings(request)
    if settings_obj and not settings_obj.advances_enabled:
        return Response({
            "detail": "نظام السلف غير مفعّل في هذه الشركة",
            "code": "advances_disabled",
            "settings_url": "/settings/payroll"}, status=409)

    if request.method == "GET":
        Gate.require(request.user, "payroll.view")
        qs = Gate.filter_queryset(request.user, "payroll.view",
                                  Advance.objects.all())
        qs = qs.filter(company_id=company_id).select_related(
            "employment__person")
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])

        return Response([
            {
                "id": a.id, "advance_no": a.advance_no,
                "employee_no": a.employment.employee_no,
                "name": a.employment.person.display_name,
                "amount": str(a.amount),
                "repaid": str(a.repaid_amount),
                "outstanding": str(a.outstanding),
                "repayment_method": a.repayment_method,
                "repayment_label": a.get_repayment_method_display(),
                "installments_count": a.installments_count,
                "installment_amount": (str(a.installment_amount)
                                       if a.installment_amount else None),
                "start": f"{a.start_year}-{a.start_month:02d}",
                "status": a.status,
                "status_label": a.get_status_display(),
            }
            for a in qs
        ])

    Gate.require(request.user, "payroll.structures")
    emp = _get_employment(request, request.data.get("employment_id"),
                          "payroll.structures")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    try:
        adv = create_advance(
            employment=emp,
            amount=_dec(request.data.get("amount"), "amount"),
            settings_obj=settings_obj,
            start_year=int(request.data["start_year"]),
            start_month=int(request.data["start_month"]),
            repayment_method=request.data.get("repayment_method"),
            installments_count=int(request.data.get("installments_count", 1)),
            installment_amount=request.data.get("installment_amount"),
            reason=request.data.get("reason", ""))
    except AdvancesDisabled as e:
        return Response({"detail": str(e), "code": "advances_disabled"},
                        status=409)
    except AdvanceError as e:
        return Response({"detail": str(e), "code": "not_eligible"}, status=400)
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات ناقصة: {e}"}, status=400)

    return Response({"id": adv.id, "advance_no": adv.advance_no,
                     "installment_amount": (str(adv.installment_amount)
                                            if adv.installment_amount else None),
                     "status": adv.status}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def advance_eligibility(request, employment_id):
    """فحص الأهلية قبل الطلب — يعرض الحد الأقصى والموانع."""
    Gate.require(request.user, "payroll.view")
    emp = _get_employment(request, employment_id, "payroll.view")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    settings_obj = _settings(request)
    try:
        amount = _dec(request.GET.get("amount", "0"), "amount")
        check = check_eligibility(employment=emp, amount=amount,
                                  settings_obj=settings_obj)
    except AdvancesDisabled as e:
        return Response({"detail": str(e), "code": "advances_disabled"},
                        status=409)
    except ValueError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({
        "allowed": check.allowed,
        "max_allowed": (str(check.max_allowed)
                        if check.max_allowed is not None else None),
        "reasons": check.reasons,
        "current_outstanding": str(total_outstanding(emp)),
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def advance_approve(request, advance_id):
    """اعتماد السلفة — تبدأ بالخصم من الشهر المحدد."""
    Gate.require(request.user, "payroll.approve")
    qs = Gate.filter_queryset(request.user, "payroll.approve",
                              Advance.objects.all())
    adv = qs.filter(id=advance_id, company_id=_company_id(request)).first()
    if adv is None:
        return Response({"detail": "السلفة غير موجودة"}, status=404)

    person = getattr(request.user, "person", None)
    try:
        approve_advance(advance=adv, approved_by_person=person)
    except AdvanceError as e:
        return Response({"detail": str(e)}, status=400)

    adv.refresh_from_db()
    return Response({"id": adv.id, "status": adv.status,
                     "status_label": adv.get_status_display()})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def advance_schedule(request, advance_id):
    """جدول الأقساط — المسدَّد والمتبقي."""
    Gate.require(request.user, "payroll.view")
    qs = Gate.filter_queryset(request.user, "payroll.view",
                              Advance.objects.all())
    adv = qs.filter(id=advance_id,
                    company_id=_company_id(request)).first()
    if adv is None:
        return Response({"detail": "السلفة غير موجودة"}, status=404)

    return Response({
        "advance_no": adv.advance_no,
        "amount": str(adv.amount),
        "repaid": str(adv.repaid_amount),
        "outstanding": str(adv.outstanding),
        "status": adv.get_status_display(),
        "installments": [
            {"period": f"{i.period_year}-{i.period_month:02d}",
             "amount": str(i.amount), "deducted": i.is_deducted,
             "payslip_id": i.payslip_id}
            for i in adv.installments.order_by("period_year", "period_month")
        ],
    })


# ══════════════════ العهد ══════════════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def assets(request):
    """قائمة العهد وتسليمها."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = Gate.filter_queryset(request.user, "employees.view",
                                  Asset.objects.all())
        qs = qs.filter(company_id=company_id).select_related(
            "employment__person")
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])

        return Response([
            {
                "id": a.id, "asset_no": a.asset_no, "name_ar": a.name_ar,
                "category": a.category,
                "category_label": a.get_category_display(),
                "serial_number": a.serial_number, "value": str(a.value),
                "employee_no": a.employment.employee_no,
                "name": a.employment.person.display_name,
                "assigned_date": a.assigned_date,
                "returned_date": a.returned_date,
                "status": a.status, "status_label": a.get_status_display(),
                "is_outstanding": a.is_outstanding,
            }
            for a in qs
        ])

    Gate.require(request.user, "employees.edit")
    emp = _get_employment(request, request.data.get("employment_id"),
                          "employees.edit")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    try:
        a = assign_asset(
            employment=emp, name_ar=request.data.get("name_ar", ""),
            value=_dec(request.data.get("value", 0), "value"),
            category=request.data.get("category", "other"),
            serial_number=request.data.get("serial_number", ""),
            assigned_date=(date.fromisoformat(request.data["assigned_date"])
                           if request.data.get("assigned_date") else None),
            expected_return_date=(
                date.fromisoformat(request.data["expected_return_date"])
                if request.data.get("expected_return_date") else None),
            handover_document=request.data.get("handover_document", ""),
            condition_note=request.data.get("condition_note", ""))
    except (AssetError, ValueError) as e:
        return Response({"detail": str(e)}, status=400)

    return Response({"id": a.id, "asset_no": a.asset_no}, status=201)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def asset_return(request, asset_id):
    """
    استرجاع عهدة.

    status: returned · damaged · lost — التالفة والمفقودة تبقى
    ضمن مخالصة نهاية الخدمة (ق-41).
    """
    Gate.require(request.user, "employees.edit")
    qs = Gate.filter_queryset(request.user, "employees.edit",
                              Asset.objects.all())
    a = qs.filter(id=asset_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "العهدة غير موجودة"}, status=404)

    try:
        return_asset(
            asset=a,
            returned_date=(date.fromisoformat(request.data["returned_date"])
                           if request.data.get("returned_date") else None),
            condition_note=request.data.get("condition_note", ""),
            status=request.data.get("status", AssetStatus.RETURNED))
    except (AssetError, ValueError) as e:
        return Response({"detail": str(e)}, status=400)

    a.refresh_from_db()
    return Response({"id": a.id, "status": a.status,
                     "status_label": a.get_status_display(),
                     "is_outstanding": a.is_outstanding})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_settlement_preview(request, employment_id):
    """كشف السلف والعهد القائمة — قبل نهاية الخدمة."""
    Gate.require(request.user, "employees.view")
    emp = _get_employment(request, employment_id, "employees.view")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    settings_obj = _settings(request)
    advances_data = {"count": 0, "total_outstanding": "0.00", "advances": []}
    if settings_obj and settings_obj.advances_enabled:
        from apps.employees.services.advances import settle_on_termination
        advances_data = settle_on_termination(employment=emp)

    return Response({
        "employee_no": emp.employee_no,
        "name": emp.person.display_name,
        "advances": advances_data,
        "assets": assets_settlement(emp),
    })


# ══════════════════ الوثائق ══════════════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def documents(request):
    """وثائق الموظفين وإضافتها."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = Gate.filter_queryset(request.user, "employees.view",
                                  EmployeeDocument.objects.all())
        qs = qs.filter(company_id=company_id).select_related(
            "employment__person")
        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])

        return Response([
            {
                "id": d.id,
                "employee_no": d.employment.employee_no,
                "name": d.employment.person.display_name,
                "document_type": d.document_type,
                "type_label": d.get_document_type_display(),
                "document_number": d.document_number,
                "expiry_date": d.expiry_date,
                "expiry_hijri": d.expiry_hijri,
                "days_to_expiry": d.days_to_expiry,
                "is_expired": d.is_expired,
                "needs_alert": d.needs_alert,
            }
            for d in qs
        ])

    Gate.require(request.user, "employees.documents")
    emp = _get_employment(request, request.data.get("employment_id"),
                          "employees.documents")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    try:
        d = add_document(
            employment=emp,
            document_type=request.data.get("document_type",
                                           DocumentType.OTHER),
            document_number=request.data.get("document_number", ""),
            issue_date=(date.fromisoformat(request.data["issue_date"])
                        if request.data.get("issue_date") else None),
            expiry_date=(date.fromisoformat(request.data["expiry_date"])
                         if request.data.get("expiry_date") else None),
            expiry_hijri=request.data.get("expiry_hijri", ""),
            issuing_authority=request.data.get("issuing_authority", ""),
            file_url=request.data.get("file_url", ""),
            alert_days_before=int(request.data.get("alert_days_before", 60)),
            note=request.data.get("note", ""))
    except (AssetError, ValueError) as e:
        return Response({"detail": str(e)}, status=400)

    return Response({"id": d.id, "type": d.get_document_type_display()},
                    status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def expiring_documents_view(request):
    """
    الوثائق المنتهية والقريبة — التنبيه الاستباقي.

    انتهاء إقامة أو رخصة عمل يوقف الموظف ويعرّض الشركة لغرامات.
    """
    Gate.require(request.user, "employees.view")
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    from apps.accounts.models import Company
    comp = Gate.filter_queryset(
        request.user, "employees.view", Company.objects.all()
    ).filter(id=company_id).first()
    if comp is None:
        return Response({"detail": "الشركة غير متاحة"}, status=404)

    try:
        within = int(request.GET.get("within_days", 60))
    except ValueError:
        within = 60

    rows = expiring_documents(comp, within_days=within)
    by_severity = {}
    for r in rows:
        by_severity.setdefault(r["severity"], 0)
        by_severity[r["severity"]] += 1

    return Response({
        "within_days": within,
        "total": len(rows),
        "by_severity": by_severity,
        "documents": rows,
    })


# ══════════════════ مسير المستحقات ══════════════════

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def settlement_preview(request, employment_id):
    """
    معاينة تسوية نهاية الخدمة قبل حفظها.

    تعرض كل بند بشرح احتسابه — فيراجعها مدير الموارد قبل الاعتماد.
    """
    Gate.require(request.user, "payroll.view")
    emp = _get_employment(request, employment_id, "payroll.view")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    from apps.payroll.services.eosb import ALL_REASONS, EOSBBasisNotSet
    from apps.payroll.services.settlement import (
        SettlementError, compute_settlement,
    )

    settings_obj = _settings(request)
    if settings_obj is None:
        return Response({"detail": "لا إعدادات رواتب"}, status=404)

    try:
        end = date.fromisoformat(request.data["termination_date"])
    except (KeyError, ValueError):
        return Response({"detail": "تاريخ انتهاء الخدمة مطلوب"}, status=400)

    try:
        result = compute_settlement(
            employment=emp, termination_date=end,
            reason_code=request.data.get("reason_code", ""),
            settings_obj=settings_obj,
            agreed_compensation=(
                _dec(request.data["agreed_compensation"], "agreed")
                if request.data.get("agreed_compensation") else None),
            remaining_contract_months=(
                _dec(request.data["remaining_contract_months"], "months")
                if request.data.get("remaining_contract_months") else None),
            include_month_salary=bool(
                request.data.get("include_month_salary", True)),
            leave_balance_days=(
                _dec(request.data["leave_balance_days"], "leave_days")
                if request.data.get("leave_balance_days") is not None
                else None))
    except EOSBBasisNotSet as e:
        return Response({"detail": str(e), "code": "eosb_basis_not_set",
                         "settings_url": "/settings/payroll"}, status=409)
    except SettlementError as e:
        return Response({
            "detail": str(e), "code": "invalid_input",
            "available_reasons": [{"code": k, "label": v}
                                  for k, v in ALL_REASONS.items()]},
            status=400)
    except ValueError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({
        "employee_no": result.employee_no,
        "name": result.name,
        "termination_date": str(result.termination_date),
        "reason_code": result.reason_code,
        "reason_label": result.reason_label,
        "service_days": result.service_days,
        "service_years": str(result.service_years),
        "lines": [
            {"code": l.code, "name_ar": l.name_ar, "kind": l.kind,
             "amount": str(l.amount), "explanation": l.explanation}
            for l in sorted(result.lines, key=lambda x: x.order)
        ],
        "total_earnings": str(result.total_earnings),
        "total_deductions": str(result.total_deductions),
        "net_due": str(result.net_due),
        "warnings": result.warnings,
        "trace": result.trace,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def settlement_create(request, employment_id):
    """ينشئ مسير المستحقات ويحفظ قسيمته."""
    Gate.require(request.user, "payroll.create")
    emp = _get_employment(request, employment_id, "payroll.create")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    from apps.payroll.services.eosb import EOSBBasisNotSet
    from apps.payroll.services.settlement import (
        SettlementError, create_settlement_run,
    )

    settings_obj = _settings(request)
    try:
        end = date.fromisoformat(request.data["termination_date"])
        run, slip, result = create_settlement_run(
            employment=emp, termination_date=end,
            reason_code=request.data.get("reason_code", ""),
            settings_obj=settings_obj,
            agreed_compensation=(
                _dec(request.data["agreed_compensation"], "agreed")
                if request.data.get("agreed_compensation") else None),
            include_month_salary=bool(
                request.data.get("include_month_salary", True)),
            leave_balance_days=(
                _dec(request.data["leave_balance_days"], "leave_days")
                if request.data.get("leave_balance_days") is not None
                else None))
    except EOSBBasisNotSet as e:
        return Response({"detail": str(e), "code": "eosb_basis_not_set"},
                        status=409)
    except SettlementError as e:
        return Response({"detail": str(e)}, status=409)
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات ناقصة: {e}"}, status=400)

    return Response({
        "run_id": run.id, "run_no": run.run_no,
        "payslip_id": slip.id,
        "net_due": str(result.net_due),
        "warnings": result.warnings,
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def termination_reasons_list(request):
    """قائمة أسباب انتهاء العلاقة — من المرجع الحكومي (ق-26)."""
    Gate.require(request.user, "payroll.view")
    from apps.payroll.services.eosb import (
        ALL_REASONS, FULL_ENTITLEMENT, NO_ENTITLEMENT,
    )
    return Response([
        {
            "code": code, "label": label,
            "entitlement": ("full" if code in FULL_ENTITLEMENT
                            else "none" if code in NO_ENTITLEMENT
                            else "prorated"),
            "requires_compensation_77": code == "unlawful_termination",
        }
        for code, label in ALL_REASONS.items()
    ])
