"""مسارات البنود المكرّرة (ق-135)."""
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import Employment
from apps.payroll.models import (
    PayComponent, RecurringAdjustment, RecurringKind)


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _json(r):
    return {
        "id": r.id,
        "employment_id": r.employment_id,
        "employee_no": r.employment.employee_no,
        "employee": r.employment.person.display_name,
        "component_id": r.component_id,
        "component": r.component.name_ar,
        "kind": r.kind, "kind_label": r.get_kind_display(),
        "amount": str(r.amount),
        "start": f"{r.start_year}-{r.start_month:02d}",
        "end": (f"{r.end_year}-{r.end_month:02d}" if r.end_year else ""),
        "max_occurrences": r.max_occurrences,
        "applied_count": r.applied_count,
        "remaining": r.remaining,
        "reason": r.reason,
        "is_active": r.is_active,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def recurring(request):
    """البنود المكرّرة — عرضًا وإنشاءً."""
    Gate.require(request.user, "payroll.view")
    Features.require(_company_id(request), "recurring_adjustments")

    if request.method == "GET":
        qs = (RecurringAdjustment.objects
              .filter(company_id=_company_id(request))
              .select_related("employment__person", "component"))
        if request.GET.get("active") != "0":
            qs = qs.filter(is_active=True)
        if request.GET.get("employment_id"):
            qs = qs.filter(employment_id=request.GET["employment_id"])

        comps = PayComponent.objects.filter(
            company_id=_company_id(request), is_active=True)
        return Response({
            "rows": [_json(r) for r in qs[:300]],
            "kinds": [{"value": v, "label": lbl}
                      for v, lbl in RecurringKind.choices],
            "components": [{"id": c.id, "code": c.code,
                            "name_ar": c.name_ar} for c in comps],
        })

    Gate.require(request.user, "payroll.create")
    d = request.data

    # ⚠️ ولا يُنشأ لمن لا يراه
    emp = Gate.filter_queryset(
        request.user, "payroll.view", Employment.objects.all()
    ).filter(id=d.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    comp = PayComponent.objects.filter(
        id=d.get("component_id"), company_id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "بند الأجر غير موجود"}, status=404)

    try:
        amount = Decimal(str(d.get("amount", "0")))
    except (InvalidOperation, TypeError):
        return Response({"detail": "مبلغ غير صالح"}, status=400)
    if amount <= 0:
        return Response({"detail": "المبلغ مطلوب"}, status=400)

    end_year = d.get("end_year") or None
    max_occ = d.get("max_occurrences") or None

    # ⚠️ **نهايةٌ دائمًا**: بتاريخٍ أو بعدد مرّات — فبندٌ بلا نهاية
    # يُحسم من الموظف سنين، ومن أدخله نسيه.
    if not end_year and not max_occ:
        return Response({
            "detail": "حدّد نهايةً: تاريخًا أو عدد مرّات",
            "code": "no_end"}, status=400)

    r = RecurringAdjustment.objects.create(
        account_id=emp.account_id, company_id=emp.company_id,
        employment=emp, component=comp,
        kind=d.get("kind") or RecurringKind.DEDUCTION,
        amount=amount,
        start_year=int(d.get("start_year")),
        start_month=int(d.get("start_month")),
        end_year=int(end_year) if end_year else None,
        end_month=int(d.get("end_month")) if end_year else None,
        max_occurrences=int(max_occ) if max_occ else None,
        reason=str(d.get("reason") or "")[:255],
        created_by_person_id=getattr(
            getattr(request.user, "person", None), "id", None))
    return Response(_json(r), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def recurring_detail(request, recurring_id):
    """
    تعديل بندٍ أو إيقافه.

    ⚠️ **وما طُبّق لا يُحذف**: قسائم صدرت تشير إليه — فيُوقَف
    بدل ذلك، والماضي يبقى كما صُرف.
    """
    Gate.require(request.user, "payroll.create")
    Features.require(_company_id(request), "recurring_adjustments")

    r = RecurringAdjustment.objects.filter(
        id=recurring_id, company_id=_company_id(request)).first()
    if r is None:
        return Response({"detail": "غير موجود"}, status=404)

    if request.method == "DELETE":
        if r.applied_count:
            r.is_active = False
            r.save(update_fields=["is_active"])
            return Response({
                "stopped": True,
                "detail": f"طُبّق {r.applied_count} مرّة — أُوقف ولم يُحذف"})
        r.delete()
        return Response({"deleted": True})

    d = request.data
    if "amount" in d:
        try:
            r.amount = Decimal(str(d["amount"]))
        except (InvalidOperation, TypeError):
            return Response({"detail": "مبلغ غير صالح"}, status=400)
    if "reason" in d:
        r.reason = str(d["reason"] or "")[:255]
    if "is_active" in d:
        r.is_active = bool(d["is_active"])
    if d.get("end_year"):
        r.end_year = int(d["end_year"])
        r.end_month = int(d.get("end_month") or 12)
    if d.get("max_occurrences"):
        r.max_occurrences = int(d["max_occurrences"])
    r.save()
    return Response(_json(r))


# ══════════ تأجيل بنود القسيمة (ق-136) ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def deferrals(request):
    """
    البنود المؤجَّلة — عرضًا وتأجيلًا.

    ⚠️ **والراتب لا يُؤجَّل**: أجرٌ مستحقٌّ في موعده.
    """
    from apps.payroll.models import DeferralStatus, Payslip, PayslipDeferral
    from apps.payroll.services import deferral as dsvc

    Gate.require(request.user, "payroll.view")
    Features.require(_company_id(request), "payslip_defer")

    if request.method == "GET":
        qs = (PayslipDeferral.objects
              .filter(company_id=_company_id(request))
              .select_related("employment__person"))
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        else:
            qs = qs.filter(status=DeferralStatus.PENDING)

        return Response({
            "rows": [{
                "id": d.id,
                "employee": d.employment.person.display_name,
                "employee_no": d.employment.employee_no,
                "component_code": d.component_code,
                "name_ar": d.name_ar,
                "amount": str(d.amount),
                "from": f"{d.from_year}-{d.from_month:02d}",
                "to": f"{d.to_year}-{d.to_month:02d}",
                "reason": d.reason,
                "status": d.status,
                "status_label": d.get_status_display(),
            } for d in qs[:300]],
        })

    Gate.require(request.user, "payroll.create")
    slip = Payslip.objects.filter(
        id=request.data.get("payslip_id"),
        company_id=_company_id(request)).first()
    if slip is None:
        return Response({"detail": "القسيمة غير موجودة"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        d = dsvc.defer(
            payslip=slip,
            component_code=request.data.get("component_code", ""),
            to_year=request.data.get("to_year"),
            to_month=request.data.get("to_month"),
            reason=request.data.get("reason", ""),
            by_person_id=actor.id if actor else None)
    except (dsvc.DeferralError, TypeError, ValueError) as e:
        return Response({"detail": str(e)}, status=400)

    return Response({"id": d.id, "component_code": d.component_code,
                     "to": f"{d.to_year}-{d.to_month:02d}"},
                    status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payslip_deferrable(request, payslip_id):
    """بنود القسيمة التي يجوز تأجيلها — والراتب خارجها."""
    from apps.payroll.models import Payslip
    from apps.payroll.services import deferral as dsvc

    Gate.require(request.user, "payroll.view")
    Features.require(_company_id(request), "payslip_defer")

    slip = Payslip.objects.filter(
        id=payslip_id, company_id=_company_id(request)).first()
    if slip is None:
        return Response({"detail": "غير موجودة"}, status=404)

    return Response({
        "payslip_id": slip.id,
        "employee": slip.employment.person.display_name,
        "period": f"{slip.run.period_year}-{slip.run.period_month:02d}",
        "locked": slip.run.is_locked,
        "lines": [{
            "component_code": l.component_code,
            "name_ar": l.name_ar,
            "line_type": l.line_type,
            "amount": str(l.amount),
        } for l in dsvc.deferrable_lines(slip)],
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def deferral_detail(request, deferral_id):
    """إلغاء تأجيلٍ لم يُطبَّق — فيعود البند لشهره."""
    from apps.payroll.models import PayslipDeferral
    from apps.payroll.services import deferral as dsvc

    Gate.require(request.user, "payroll.create")
    Features.require(_company_id(request), "payslip_defer")

    d = PayslipDeferral.objects.filter(
        id=deferral_id, company_id=_company_id(request)).first()
    if d is None:
        return Response({"detail": "غير موجود"}, status=404)
    try:
        dsvc.cancel(deferral=d)
    except dsvc.DeferralError as e:
        return Response({"detail": str(e)}, status=409)
    return Response({"cancelled": True})
