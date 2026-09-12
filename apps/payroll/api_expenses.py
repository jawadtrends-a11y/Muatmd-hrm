"""مسارات المصروفات (ق-139)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import Employment, EmploymentStatus
from apps.payroll.models import (
    ExpenseCategory, ExpenseClaim, ExpenseStatus)
from apps.payroll.services import expenses as svc


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


def _cat_json(c):
    return {
        "id": c.id, "code": c.code, "name_ar": c.name_ar,
        "description": c.description,
        "max_per_claim": (str(c.max_per_claim)
                          if c.max_per_claim is not None else None),
        "max_per_month": (str(c.max_per_month)
                          if c.max_per_month is not None else None),
        "component_code": c.component_code,
        "is_active": c.is_active,
    }


def _claim_json(c):
    return {
        "id": c.id, "claim_no": c.claim_no,
        "employment_id": c.employment_id,
        "employee": c.employment.person.display_name,
        "employee_no": c.employment.employee_no,
        "category": c.category.name_ar,
        "spent_on": c.spent_on, "amount": str(c.amount),
        "description": c.description,
        "receipt_url": c.receipt_url,
        "status": c.status, "status_label": c.get_status_display(),
        "decision_note": c.decision_note,
        "method": c.method, "paid_on": c.paid_on,
    }


# ══════════ الفئات ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def categories(request):
    """فئات المصروفات — عرضًا وإضافة."""
    Features.require(_company_id(request), "expenses")

    if request.method == "GET":
        Gate.require(request.user, "payroll.view")
        qs = ExpenseCategory.objects.filter(
            company_id=_company_id(request))
        return Response([_cat_json(c) for c in qs])

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
    if ExpenseCategory.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    def _dec(key):
        v = d.get(key)
        if v in (None, ""):
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, TypeError):
            return None

    c = ExpenseCategory.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=d.get("name_ar", ""),
        description=str(d.get("description") or "")[:255],
        max_per_claim=_dec("max_per_claim"),
        max_per_month=_dec("max_per_month"),
        component_code=str(d.get("component_code") or ""))
    return Response(_cat_json(c), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def category_detail(request, category_id):
    """
    تعديل فئة أو تعطيلها.

    ⚠️ **والمستعملة لا تُحذف**: مطالباتٌ تشير إليها، وحذفها يترك
    صرفًا بلا فئة.
    """
    Gate.require(request.user, "payroll.create")
    Features.require(_company_id(request), "expenses")

    c = ExpenseCategory.objects.filter(
        id=category_id, company_id=_company_id(request)).first()
    if c is None:
        return Response({"detail": "غير موجودة"}, status=404)

    if request.method == "DELETE":
        if c.claims.exists():
            c.is_active = False
            c.save(update_fields=["is_active"])
            return Response({"deactivated": True,
                             "detail": "مستعملة — عُطّلت ولم تُحذف"})
        c.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "description", "component_code"):
        if f in d:
            setattr(c, f, str(d[f] or ""))
    for f in ("max_per_claim", "max_per_month"):
        if f in d:
            v = d[f]
            try:
                setattr(c, f, Decimal(str(v)) if v not in (None, "")
                        else None)
            except (InvalidOperation, TypeError):
                return Response({"detail": "مبلغ غير صالح"}, status=400)
    if "is_active" in d:
        c.is_active = bool(d["is_active"])
    c.save()
    return Response(_cat_json(c))


# ══════════ المطالبات ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def claims(request):
    """مطالباتي أو مطالبات الفريق — وتقديمٌ جديد."""
    Features.require(_company_id(request), "expenses")

    me = _me(request)
    if me is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    if request.method == "GET":
        qs = (ExpenseClaim.objects
              .filter(company_id=_company_id(request))
              .select_related("employment__person", "category"))

        # ⚠️ من يرى الرواتب يرى الجميع، وغيره يرى مطالباته وحده
        if not Gate.check(request.user, "payroll.view").allowed:
            qs = qs.filter(employment=me)

        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])

        cats = ExpenseCategory.objects.filter(
            company_id=_company_id(request), is_active=True)
        return Response({
            "claims": [_claim_json(c) for c in qs[:300]],
            "categories": [_cat_json(c) for c in cats],
            "statuses": [{"value": v, "label": lbl}
                         for v, lbl in ExpenseStatus.choices],
        })

    d = request.data
    cat = ExpenseCategory.objects.filter(
        id=d.get("category_id"), company_id=_company_id(request)).first()
    if cat is None:
        return Response({"detail": "الفئة غير موجودة"}, status=404)

    try:
        spent = date.fromisoformat(str(d.get("spent_on")))
    except (TypeError, ValueError):
        return Response({"detail": "تاريخ غير صالح"}, status=400)

    try:
        c = svc.submit(employment=me, category=cat, spent_on=spent,
                       amount=d.get("amount"),
                       description=d.get("description", ""),
                       receipt_url=d.get("receipt_url", ""))
    except svc.ExpenseError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_claim_json(c), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def decide_claim(request, claim_id):
    """اعتماد مطالبةٍ أو رفضها."""
    Gate.require(request.user, "payroll.create")
    Features.require(_company_id(request), "expenses")

    c = ExpenseClaim.objects.filter(
        id=claim_id, company_id=_company_id(request)).first()
    if c is None:
        return Response({"detail": "غير موجودة"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.decide(claim=c, approve=bool(request.data.get("approve")),
                   by_person_id=actor.id if actor else None,
                   note=request.data.get("note", ""))
    except svc.ExpenseError as e:
        return Response({"detail": str(e)}, status=409)
    return Response(_claim_json(c))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def settle_claim(request, claim_id):
    """تسجيل صرف مطالبةٍ معتمدة."""
    Gate.require(request.user, "payroll.create")
    Features.require(_company_id(request), "expenses")

    c = ExpenseClaim.objects.filter(
        id=claim_id, company_id=_company_id(request)).first()
    if c is None:
        return Response({"detail": "غير موجودة"}, status=404)

    paid_on = None
    if request.data.get("paid_on"):
        try:
            paid_on = date.fromisoformat(str(request.data["paid_on"]))
        except ValueError:
            return Response({"detail": "تاريخ غير صالح"}, status=400)

    try:
        svc.settle(claim=c, method=request.data.get("method"),
                   payroll_run_type=request.data.get(
                       "payroll_run_type", ""),
                   paid_on=paid_on,
                   paid_note=request.data.get("paid_note", ""))
    except svc.ExpenseError as e:
        return Response({"detail": str(e)}, status=409)
    return Response(_claim_json(c))
