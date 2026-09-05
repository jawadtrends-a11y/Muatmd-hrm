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
                      "exclude_zero_net_from_wps",
                      "variance_threshold_percent",
                      # حدود السلف — كانت في الشاشة ولا تُحفظ،
                      # فيمرّ طلب يتجاوز الحد بلا مانع (ق-69)
                      "advances_enabled", "advance_max_amount",
                      "advance_max_months_of_salary",
                      "advance_block_if_outstanding",
                      "advance_max_installments",
                      "retro_method", "retro_reopen_hours"):
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

        # حدود السلف والتسويات — تُعرض وتُحفظ من الشاشة نفسها
        "advances_enabled": s.advances_enabled,
        "advance_max_amount": (str(s.advance_max_amount)
                               if s.advance_max_amount is not None else None),
        "advance_max_months_of_salary": (
            str(s.advance_max_months_of_salary)
            if s.advance_max_months_of_salary is not None else None),
        "advance_block_if_outstanding": s.advance_block_if_outstanding,
        "advance_max_installments": s.advance_max_installments,
        "retro_method": s.retro_method,
        "retro_reopen_hours": s.retro_reopen_hours,
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
    """
    قائمة أسباب انتهاء العلاقة — من المرجع الحكومي حرفيًا (ق-26).

    متاحة لكل مصادَق: الموظف يحتاجها ليختار سبب استقالته (ق-59)،
    وهي قائمة نظامية عامة لا بيانات رواتب.
    """
    from apps.payroll.services.eosb import (
        ALL_REASONS, FULL_ENTITLEMENT, NO_ENTITLEMENT, PRORATED_ENTITLEMENT,
        TERMINATION_INITIATOR, notice_days_for,
    )

    # ق-60: الموظف يرى ما يبادر به هو فقط
    wanted = request.GET.get("initiator", "")

    return Response({
        "source": "حاسبة مكافأة نهاية الخدمة الرسمية — وزارة الموارد البشرية",
        "reasons": [
            {
                "code": code, "label": label,
                "name_ar": label,
                "initiator": TERMINATION_INITIATOR.get(code, ("employer", 0))[0],
                "notice_days": notice_days_for(code),
                "entitlement": ("full" if code in FULL_ENTITLEMENT
                                else "none" if code in NO_ENTITLEMENT
                                else "prorated"),
                "requires_compensation_77": code == "unlawful_termination",
            }
            for code, label in ALL_REASONS.items()
            if not wanted or TERMINATION_INITIATOR.get(
                code, ("employer", 0))[0] == wanted
        ],
        "total": len(ALL_REASONS),
        "initiator_filter": wanted or "all",
    })


# ══════════════════ إدارة المسيرات ══════════════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def payroll_runs(request):
    """قائمة المسيرات وإنشاؤها."""
    from apps.payroll.models import PayrollRun, PayrollRunType
    from apps.payroll.services.engine import PayrollError, create_run

    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "payroll.view")
        qs = Gate.filter_queryset(request.user, "payroll.view",
                                  PayrollRun.objects.all())
        qs = qs.filter(company_id=company_id)

        if request.GET.get("year"):
            qs = qs.filter(period_year=int(request.GET["year"]))
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        if request.GET.get("run_type"):
            qs = qs.filter(run_type=request.GET["run_type"])

        return Response([
            {
                "id": r.id,
                "run_no": r.run_no,
                "period": f"{r.period_year}-{r.period_month:02d}",
                "period_year": r.period_year,
                "period_month": r.period_month,
                "run_type": r.run_type,
                "run_type_label": r.get_run_type_display(),
                "status": r.status,
                "status_label": r.get_status_display(),
                "employee_count": r.employee_count,
                "total_gross": str(r.total_gross),
                "total_deductions": str(r.total_deductions),
                "total_net": str(r.total_net),
                "variance_count": r.variance_count,
                "error_count": len(r.error_log or []),
                "accrual_date": r.accrual_date,
                "payment_date": r.payment_date,
                "calculated_at": r.calculated_at,
                "approved_at": r.approved_at,
            }
            for r in qs.order_by("-period_year", "-period_month", "-id")[:100]
        ])

    # ── إنشاء مسير ──
    Gate.require(request.user, "payroll.create")
    from apps.accounts.models import Company
    comp = Gate.filter_queryset(
        request.user, "payroll.create", Company.objects.all()
    ).filter(id=company_id).first()
    if comp is None:
        return Response({"detail": "الشركة غير متاحة"}, status=404)

    run_type = request.data.get("run_type", PayrollRunType.REGULAR)
    if run_type not in PayrollRunType.values:
        return Response({"detail": f"نوع مسير غير معروف: {run_type}"},
                        status=400)

    try:
        run = create_run(
            company=comp, run_type=run_type,
            year=int(request.data["year"]),
            month=int(request.data["month"]))
    except PayrollError as e:
        return Response({"detail": str(e), "code": "run_exists"}, status=409)
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات ناقصة: {e}"}, status=400)

    return Response({
        "id": run.id, "run_no": run.run_no,
        "period": f"{run.period_year}-{run.period_month:02d}",
        "status": run.status,
    }, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_calculate(request, run_id):
    """
    احتساب المسير.

    فشل موظف لا يوقف الباقين — يُسجَّل في error_log.
    """
    from apps.payroll.models import PayrollRun
    from apps.payroll.services.eosb import EOSBBasisNotSet
    from apps.payroll.services.engine import PayrollError, calculate_run

    run = Gate.filter_queryset(
        request.user, "payroll.create", PayrollRun.objects.all()
    ).filter(id=run_id, company_id=_company_id(request)).first()
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)

    Gate.require(request.user, "payroll.create")
    try:
        res = calculate_run(run)
    except EOSBBasisNotSet as e:
        return Response({"detail": str(e), "code": "eosb_basis_not_set",
                         "settings_url": "/settings/payroll"}, status=409)
    except PayrollError as e:
        return Response({"detail": str(e), "code": "cannot_calculate"},
                        status=409)

    run.refresh_from_db()
    return Response({
        "run_no": run.run_no,
        "status": run.status,
        "calculated": res.calculated,
        "failed": res.failed,
        "errors": res.errors,
        "total_net": str(run.total_net),
        "variance_count": run.variance_count,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_submit(request, run_id):
    """رفع المسير للاعتماد."""
    from apps.payroll.models import PayrollRun
    from apps.payroll.services.engine import PayrollError, submit_run

    run = Gate.filter_queryset(
        request.user, "payroll.create", PayrollRun.objects.all()
    ).filter(id=run_id, company_id=_company_id(request)).first()
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)

    Gate.require(request.user, "payroll.create")
    person = getattr(request.user, "person", None)
    try:
        submit_run(run, person)
    except PayrollError as e:
        return Response({"detail": str(e), "code": "cannot_submit"},
                        status=409)

    run.refresh_from_db()
    return Response({"run_no": run.run_no, "status": run.status})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_approve(request, run_id):
    """
    اعتماد المسير — سجل مالي نهائي لا يُعاد احتسابه.
    """
    from apps.payroll.models import PayrollRun
    from apps.payroll.services.engine import PayrollError, approve_run

    Gate.require(request.user, "payroll.approve")
    run = Gate.filter_queryset(
        request.user, "payroll.approve", PayrollRun.objects.all()
    ).filter(id=run_id, company_id=_company_id(request)).first()
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)

    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=400)

    try:
        approve_run(run, person)
    except PayrollError as e:
        return Response({"detail": str(e), "code": "cannot_approve"},
                        status=409)

    run.refresh_from_db()
    return Response({
        "run_no": run.run_no, "status": run.status,
        "approved_at": run.approved_at,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_lookup(request):
    """
    اسم البنك من الآيبان (ق-57).

    عرض لا حكم: معروف → اسمه، غير معروف → «بنوك أخرى».
    ولا تحذير — مسؤولية صحة الآيبان على الشركة.
    """
    from apps.payroll.models_banks import Bank, label_for, lookup

    iban = request.GET.get("iban", "")
    if not iban:
        return Response([
            {"code": b.iban_code, "name_ar": b.name_ar,
             "short_ar": b.short_ar, "kind": b.kind}
            for b in Bank.objects.filter(is_active=True)
        ])

    bank = lookup(iban)
    return Response({
        "label": label_for(iban),
        "code": bank.iban_code if bank else "",
        "known": bank is not None,
        "supports_wps": bank.supports_wps if bank else True,
    })


# ══════════ التسويات الرجعية (ق-69) ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def retro_pending(request):
    """
    التسويات التي تنتظر الإدراج — تظهر لموظف الموارد عند إعداد
    المسير، فيدمجها أو يؤجّلها أو يلغيها (ق-69).
    """
    from apps.payroll.models import RetroAdjustment, RetroStatus

    Gate.require(request.user, "payroll.create")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    # المعلّقة والمختارة معًا — فمن أدرج تسوية يراها مختارة لا
    # تختفي عنه قبل أن يُحتسب المسير
    qs = RetroAdjustment.objects.filter(company_id=_company_id(request), status__in=[RetroStatus.PENDING, RetroStatus.SELECTED]).select_related(
        "employment__person")

    return Response([{
        "id": a.id,
        "employee_no": a.employment.employee_no,
        "employee_name": a.employment.person.display_name,
        "period": f"{a.period_year}-{a.period_month:02d}",
        "source": a.source,
        "source_label": a.get_source_display(),
        "amount_before": str(a.amount_before),
        "amount_after": str(a.amount_after),
        "amount": str(a.amount),
        "reason_ar": a.reason_ar,
        "status": a.status,
        "status_label": a.get_status_display(),
        "created_at": a.created_at,
    } for a in qs.order_by("-period_year", "-period_month")])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retro_decide(request, adjustment_id):
    """يؤجّل التسوية أو يلغيها — لموظف الموارد (ق-69)."""
    from apps.payroll.models import RetroAdjustment
    from apps.payroll.services.retro import RetroError, decide_adjustment

    Gate.require(request.user, "payroll.create")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    a = RetroAdjustment.objects.filter(id=adjustment_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "التسوية غير موجودة"}, status=404)

    # الإدراج يحتاج مسيرًا قيد الإعداد — والقرار صريح لا تلقائي
    run = None
    if request.data.get("run_id"):
        from apps.payroll.models import PayrollRun
        run = PayrollRun.objects.filter(
            id=request.data["run_id"],
            company_id=_company_id(request)).first()
        if run is None:
            return Response({"detail": "المسير غير موجود"}, status=400)

    try:
        a = decide_adjustment(
            adjustment=a, action=request.data.get("action", ""),
            actor=getattr(request.user, "person", None),
            note=request.data.get("note", ""), run=run)
    except RetroError as e:
        return Response({"detail": str(e), "code": "cannot_decide"},
                        status=409)

    return Response({"id": a.id, "status": a.status,
                     "status_label": a.get_status_display()})


# ══════════ تعديل بند الأجر وتعطيله ══════════

@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def component_detail(request, component_id):
    """
    تعديل بند أجر أو تعطيله.

    والبند النظامي (is_system) لا يُحذف: الاحتساب يستدعيه بالرمز —
    الأساسي والسكن أساس المكافأة والتأمينات وحماية الأجور. ويُعدَّل
    اسمه وأعلامه لا رمزه.

    والبند المستخدَم في هيكل راتب يُعطَّل لا يُحذف — فحذفه يترك
    هياكل تشير لبند لا وجود له.
    """
    from apps.payroll.models import PayComponent

    Gate.require(request.user, "payroll.structures")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    c = PayComponent.objects.filter(id=component_id, company_id=_company_id(request)).first()
    if c is None:
        return Response({"detail": "البند غير موجود"}, status=404)

    if request.method == "DELETE":
        if c.is_system:
            return Response(
                {"detail": "بند نظامي — الاحتساب يستدعيه، عطّله بدل حذفه",
                 "code": "system_component"}, status=409)

        from apps.employees.models import SalaryLine
        used = SalaryLine.objects.filter(component=c).exists()
        if used:
            c.is_active = False
            c.save(update_fields=["is_active", "updated_at"])
            from apps.core.services.audit import log_action
            log_action(instance=c, action="update",
                       actor=getattr(request.user, "person", None),
                       label=c.code,
                       summary=f"عُطّل البند {c.name_ar} (مستخدم في هياكل)",
                       channel="web")
            return Response({"deactivated": True,
                             "detail": "البند مستخدم في هياكل رواتب — "
                                       "عُطّل ولم يُحذف"})

        from apps.core.services.audit import log_delete
        log_delete(instance=c, actor=getattr(request.user, "person", None),
                   label=c.code, summary=f"حُذف بند الأجر {c.name_ar}",
                   channel="web")
        c.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "name_en", "name_ur", "component_type"):
        if f in d and d[f] not in (None, ""):
            setattr(c, f, d[f])
    for f in ("is_gosi_subject", "is_eosb_subject", "is_overtime_base",
              "is_wps_subject", "is_absence_base", "is_taxable",
              "is_active"):
        if f in d:
            setattr(c, f, bool(d[f]))
    if "display_order" in d:
        try:
            c.display_order = int(d["display_order"] or 0)
        except (TypeError, ValueError):
            pass
    c.save()

    from apps.core.services.audit import log_action
    log_action(instance=c, action="update",
               actor=getattr(request.user, "person", None),
               label=c.code, summary=f"عُدّل بند الأجر {c.name_ar}",
               channel="web")
    return Response({
        "id": c.id, "code": c.code, "name_ar": c.name_ar,
        "component_type": c.component_type,
        "is_gosi_subject": c.is_gosi_subject,
        "is_eosb_subject": c.is_eosb_subject,
        "is_overtime_base": c.is_overtime_base,
        "is_wps_subject": c.is_wps_subject,
        "is_absence_base": c.is_absence_base,
        "is_system": c.is_system, "is_active": c.is_active,
        "display_order": c.display_order,
    })
