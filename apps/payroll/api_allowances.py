"""
مسارات كتالوج المخصّصات واستحقاقاتها (ق-134).
"""
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import Employment, EmploymentStatus
from apps.payroll.models import (
    AllowanceEligibility, AmountMode, ClaimableAllowance)


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _me(request):
    person = getattr(request.user, "person", None)
    if person is None:
        return None
    return Employment.objects.filter(
        person=person, company_id=_company_id(request),
        status=EmploymentStatus.ACTIVE).first()


def _json(a):
    return {
        "id": a.id, "code": a.code, "name_ar": a.name_ar,
        "description": a.description,
        "mode": a.mode, "mode_label": a.get_mode_display(),
        "amount": str(a.amount),
        "requires_attachment": a.requires_attachment,
        "component_code": a.component_code,
        "is_active": a.is_active,
        "eligible_count": a.eligibilities.count(),
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def allowances(request):
    """كتالوج المخصّصات — عرضًا وإضافة."""
    Features.require(_company_id(request), "req_custom_payment")

    if request.method == "GET":
        Gate.require(request.user, "payroll.view")
        qs = ClaimableAllowance.objects.filter(
            company_id=_company_id(request))
        return Response({
            "allowances": [_json(a) for a in qs],
            "modes": [{"value": v, "label": lbl}
                      for v, lbl in AmountMode.choices],
        })

    Gate.require(request.user, "payroll.create")
    from apps.accounts.models import Company

    # مقيَّد بشركة المنفّذ النشطة
    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    code = str(d.get("code") or "").strip().upper()
    if not code or not str(d.get("name_ar") or "").strip():
        return Response({"detail": "الرمز والاسم مطلوبان"}, status=400)
    if ClaimableAllowance.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    try:
        amount = Decimal(str(d.get("amount", "0")))
    except (InvalidOperation, TypeError):
        return Response({"detail": "مبلغ غير صالح"}, status=400)
    if amount <= 0:
        return Response({"detail": "المبلغ مطلوب"}, status=400)

    a = ClaimableAllowance.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=d.get("name_ar", ""),
        description=str(d.get("description") or "")[:255],
        mode=d.get("mode") or AmountMode.FIXED, amount=amount,
        requires_attachment=bool(d.get("requires_attachment", False)),
        component_code=str(d.get("component_code") or ""))
    return Response(_json(a), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def allowance_detail(request, allowance_id):
    """
    تعديل مخصّص أو حذفه.

    ⚠️ **والمطلوب منه لا يُحذف**: طلباتٌ قائمة تشير إليه، وحذفه
    يترك صرفًا بلا بند. فيُعطَّل بدل ذلك.
    """
    Gate.require(request.user, "payroll.create")
    Features.require(_company_id(request), "req_custom_payment")

    a = ClaimableAllowance.objects.filter(
        id=allowance_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "غير موجود"}, status=404)

    if request.method == "DELETE":
        from apps.leaves.models import Request, RequestType

        used = Request.objects.filter(
            request_type=RequestType.CUSTOM_PAYMENT,
            payload__allowance_id=a.id).exists()
        if used or a.eligibilities.exists():
            a.is_active = False
            a.save(update_fields=["is_active"])
            return Response({"deactivated": True,
                             "detail": "مستعمل — عُطّل ولم يُحذف"})
        a.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "description", "component_code"):
        if f in d:
            setattr(a, f, str(d[f] or ""))
    if d.get("mode") in AmountMode.values:
        a.mode = d["mode"]
    if "amount" in d:
        try:
            a.amount = Decimal(str(d["amount"]))
        except (InvalidOperation, TypeError):
            return Response({"detail": "مبلغ غير صالح"}, status=400)
    if "requires_attachment" in d:
        a.requires_attachment = bool(d["requires_attachment"])
    if "is_active" in d:
        a.is_active = bool(d["is_active"])
    a.save()
    return Response(_json(a))


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def allowance_eligibility(request, allowance_id):
    """من يستحقّ هذا المخصّص — إسنادًا ونزعًا."""
    Gate.require(request.user, "payroll.view")
    Features.require(_company_id(request), "req_custom_payment")

    a = ClaimableAllowance.objects.filter(
        id=allowance_id, company_id=_company_id(request)).first()
    if a is None:
        return Response({"detail": "غير موجود"}, status=404)

    if request.method == "GET":
        rows = (a.eligibilities
                .select_related("employment__person",
                                "employment__department"))
        return Response([{
            "employment_id": e.employment_id,
            "employee_no": e.employment.employee_no,
            "name": e.employment.person.display_name,
            "department": getattr(e.employment.department,
                                  "name_ar", "") or "",
            "custom_amount": (str(e.custom_amount)
                              if e.custom_amount is not None else None),
        } for e in rows])

    Gate.require(request.user, "payroll.create")
    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=request.data.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    if request.method == "DELETE":
        AllowanceEligibility.objects.filter(
            allowance=a, employment=emp).delete()
        return Response({"removed": True})

    custom = request.data.get("custom_amount")
    actor = getattr(request.user, "person", None)
    AllowanceEligibility.objects.update_or_create(
        allowance=a, employment=emp,
        defaults={"account_id": a.account_id, "company_id": a.company_id,
                  "custom_amount": (Decimal(str(custom))
                                    if custom not in (None, "") else None),
                  "granted_by_person_id": actor.id if actor else None})
    return Response({"assigned": True}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_allowances(request):
    """
    مخصّصاتي — **وما طلبتُه اليوم معلَّم**.

    فالشاشة تمنع التكرار قبل الإرسال، ولا يصطدم الموظف برفضٍ كان
    يمكن تفاديه.
    """
    from datetime import date

    from apps.leaves.models import Request, RequestStatus, RequestType

    Features.require(_company_id(request), "req_custom_payment")

    emp = _me(request)
    if emp is None:
        return Response([])

    today = str(request.GET.get("date") or date.today())
    claimed = set(
        Request.objects.filter(
            employment=emp, request_type=RequestType.CUSTOM_PAYMENT,
            status__in=[RequestStatus.PENDING, RequestStatus.APPROVED],
            payload__work_date=today
        ).values_list("payload__allowance_id", flat=True))

    rows = (AllowanceEligibility.objects
            .filter(employment=emp, allowance__is_active=True)
            .select_related("allowance"))
    return Response([{
        "allowance_id": e.allowance_id,
        "name_ar": e.allowance.name_ar,
        "description": e.allowance.description,
        "mode": e.allowance.mode,
        "amount": str(e.effective_amount),
        "requires_attachment": e.allowance.requires_attachment,
        "claimed_today": e.allowance_id in claimed,
    } for e in rows])


# ══════════ صرف المخصّصات المعتمدة (ق-134) ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def claims(request):
    """
    المخصّصات المعتمدة — **وما لم يُصرف أوّلًا**.

    فالقائمة عملٌ ينتظر لا سجلٌّ يُقرأ.
    """
    from apps.payroll.models import AllowanceClaim, DisbursementMethod

    Gate.require(request.user, "payroll.view")
    Features.require(_company_id(request), "req_custom_payment")

    qs = (AllowanceClaim.objects
          .filter(company_id=_company_id(request))
          .select_related("employment__person", "allowance"))
    if request.GET.get("settled") != "1":
        qs = qs.filter(is_settled=False)

    # ⚠️ اختيار المسير يظهر لمن يفصل مسيراته فقط — ومن له مسيرٌ
    # واحد لا يُسأل سؤالًا بلا معنى.
    multi = Features.enabled(_company_id(request), "payroll_types")

    return Response({
        "claims": [{
            "id": c.id, "request_id": c.request_id,
            "employment_id": c.employment_id,
            "employee_no": c.employment.employee_no,
            "employee": c.employment.person.display_name,
            "allowance": c.allowance.name_ar,
            "claim_date": c.claim_date,
            "amount": str(c.amount),
            "method": c.method,
            "method_label": c.get_method_display() if c.method else "",
            "payroll_run_type": c.payroll_run_type,
            "paid_on": c.paid_on,
            "is_settled": c.is_settled,
        } for c in qs[:300]],
        "methods": [{"value": v, "label": lbl}
                    for v, lbl in DisbursementMethod.choices],
        "multi_payroll": multi,
        "run_types": ([{"value": "regular", "label": "المسير العام"},
                       {"value": "supplementary",
                        "label": "مسير الإضافي والإضافات"}]
                      if multi else []),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def settle_claim(request, claim_id):
    """
    يحدّد طريقة صرف مخصّصٍ معتمد.

    ⚠️ **ولا يُصرف مرّتين**: بندٌ في المسير ثم صرفٌ نقديّ يُضاعف
    المبلغ.

    **وخارج المسير تنتهي مسؤوليتنا بالتوثيق** — كاش أو حوالة أو
    غيرها، ولا نُجبر العميل على طريقةٍ لا نعرفها.
    """
    from datetime import date as _date

    from apps.payroll.models import AllowanceClaim, DisbursementMethod

    Gate.require(request.user, "payroll.create")
    Features.require(_company_id(request), "req_custom_payment")

    c = AllowanceClaim.objects.filter(
        id=claim_id, company_id=_company_id(request)).first()
    if c is None:
        return Response({"detail": "غير موجود"}, status=404)
    if c.is_settled:
        return Response({
            "detail": "صُرف بالفعل — ولا يُصرف مرّتين",
            "code": "already_settled"}, status=409)

    method = request.data.get("method")
    if method not in DisbursementMethod.values:
        return Response({"detail": "حدّد طريقة الصرف"}, status=400)

    actor = getattr(request.user, "person", None)
    c.method = method

    if method == DisbursementMethod.PAYROLL:
        run_type = request.data.get("payroll_run_type") or "regular"
        # من له مسيرٌ واحد لا يختار
        if not Features.enabled(_company_id(request), "payroll_types"):
            run_type = "regular"
        c.payroll_run_type = run_type
    else:
        try:
            c.paid_on = (_date.fromisoformat(str(request.data["paid_on"]))
                         if request.data.get("paid_on")
                         else _date.today())
        except ValueError:
            return Response({"detail": "تاريخ غير صالح"}, status=400)
        c.paid_by_person_id = actor.id if actor else None
        c.paid_note = str(request.data.get("paid_note") or "")[:255]
        c.is_settled = True

    c.save()
    return Response({"id": c.id, "method": c.method,
                     "settled": c.is_settled,
                     "run_type": c.payroll_run_type})


# ══════════ مخالصة الإجازة (ق-138) ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def leave_cashout(request, employment_id):
    """
    بدل الإجازة — معاينةً وصرفًا.

    ⚠️ **والتنبيه النظاميّ يُعرض دائمًا**: الصرف أثناء الخدمة
    مخالفةٌ مسؤوليتها على صاحب العمل.
    """
    from apps.payroll.services import leave_cashout as svc

    Gate.require(request.user, "payroll.view")

    emp = Gate.filter_queryset(
        request.user, "payroll.view", Employment.objects.all()
    ).filter(id=employment_id).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    if request.method == "GET":
        days = request.GET.get("days") or "1"
        try:
            calc = svc.preview(employment=emp, days=days)
        except svc.CashoutError as e:
            return Response({"detail": str(e)}, status=400)
        calc["available_days"] = str(svc.available_days(emp))
        return Response(calc)

    Gate.require(request.user, "payroll.create")
    actor = getattr(request.user, "person", None)
    try:
        out = svc.cash_out(
            employment=emp, days=request.data.get("days"),
            reason=request.data.get("reason", ""),
            by_person_id=actor.id if actor else None)
    except svc.CashoutError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(out, status=status.HTTP_201_CREATED)
