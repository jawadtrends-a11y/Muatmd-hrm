"""
مسارات الجزاءات التأديبية (ق-119، ق-121).

اللائحة تُدار من الإعدادات، والسجلّ يعرض المقترح ويُوقَّع منه.
"""
from datetime import date, timedelta

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.employees.models_penalties import (
    Penalty, PenaltyDegree, PenaltyKind, PenaltyStatus,
    ViolationCategory, ViolationType)
from apps.employees.services import penalties as svc


def _company(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _dates(request):
    """المدى — افتراضه الشهر الجاري."""
    today = date.today()
    try:
        start = date.fromisoformat(request.GET.get("from")
                                   or str(today.replace(day=1)))
        end = date.fromisoformat(request.GET.get("to") or str(today))
    except ValueError:
        start, end = today.replace(day=1), today
    return start, end


def _violation_json(v):
    return {
        "id": v.id, "code": v.code,
        "name_ar": v.name_ar, "name_en": v.name_en,
        "category": v.category, "category_label": v.get_category_display(),
        "reset_days": v.reset_days,
        "financial_effect": v.financial_effect,
        "is_active": v.is_active,
        "degrees": [{
            "id": d.id, "occurrence": d.occurrence,
            "kind": d.kind, "kind_label": d.get_kind_display(),
            "days": str(d.days), "note": d.note,
        } for d in v.degrees.order_by("occurrence")],
    }


# ══════════ اللائحة ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def violations(request):
    """لائحة الجزاءات — عرضًا وإضافة."""
    from apps.accounts.models import Company

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = ViolationType.objects.filter(
            company_id=_company(request)).prefetch_related("degrees")
        return Response({
            "violations": [_violation_json(v) for v in qs],
            "kinds": [{"value": k, "label": lbl}
                      for k, lbl in PenaltyKind.choices],
            "categories": [{"value": c, "label": lbl}
                           for c, lbl in ViolationCategory.choices],
        })

    Gate.require(request.user, "employees.edit")
    d = request.data
    comp = Company.objects.filter(id=_company(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)
    code = str(d.get("code") or "").strip()
    if not code or not str(d.get("name_ar") or "").strip():
        return Response({"detail": "الرمز والاسم مطلوبان"}, status=400)
    if ViolationType.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    v = ViolationType.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=d.get("name_ar", ""), name_en=d.get("name_en", ""),
        category=d.get("category") or ViolationCategory.OTHER,
        reset_days=int(d.get("reset_days") or 180),
        financial_effect=bool(d.get("financial_effect", True)))
    return Response(_violation_json(v), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def violation_detail(request, violation_id):
    """تعديل بند أو تعطيله — والموقَّع عليه لا يُحذف."""
    Gate.require(request.user, "employees.edit")
    v = ViolationType.objects.filter(
        id=violation_id, company_id=_company(request)).first()
    if v is None:
        return Response({"detail": "غير موجود"},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        # ما وُقّع به جزاء يُعطَّل ولا يُحذف: السجلّ التأديبيّ
        # يُراجَع، ومحوُ بنده يجعل جزاءً قائمًا بلا سند.
        if Penalty.objects.filter(violation=v).exists():
            v.is_active = False
            v.save(update_fields=["is_active"])
            return Response({"deactivated": True,
                             "detail": "وُقّعت به جزاءات — عُطّل ولم يُحذف"})
        v.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "name_en", "category"):
        if f in d:
            setattr(v, f, str(d[f] or ""))
    if "reset_days" in d:
        v.reset_days = int(d["reset_days"] or 180)
    for f in ("financial_effect", "is_active"):
        if f in d:
            setattr(v, f, bool(d[f]))
    v.save()

    # الدرجات تُستبدل كاملةً — أبسط من مطابقة صفّ بصفّ
    if isinstance(d.get("degrees"), list):
        v.degrees.all().delete()
        for row in d["degrees"]:
            try:
                PenaltyDegree.objects.create(
                    violation=v,
                    occurrence=int(row.get("occurrence") or 1),
                    kind=row.get("kind") or PenaltyKind.WARNING,
                    days=row.get("days") or 0,
                    note=str(row.get("note") or "")[:255])
            except (TypeError, ValueError):
                continue
    return Response(_violation_json(v))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def seed_violations(request):
    """بذر اللائحة الاسترشادية — لمن بدأ بلا لائحة."""
    from apps.accounts.models import Company

    Gate.require(request.user, "employees.edit")
    comp = Company.objects.filter(id=_company(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)
    made = svc.provision_default_violations(comp)
    return Response({"created": made, "count": len(made)})


# ══════════ السجلّ والتوقيع ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def board(request):
    """
    سجلّ الجزاءات المقترحة — من خالف ولم يُوقَّع عليه.

    ويمرّ بالبوابة: من نطاقه إدارتُه يرى مخالفي إدارته وحدها.
    """
    # ق-123: المخالفات والجزاءات ميزةٌ تُشترى.
    from apps.core.features.gate import Features

    Features.require(_company(request), "penalties")
    from apps.accounts.models import Company
    from apps.employees.models import Employment

    Gate.require(request.user, "attendance.view")
    comp = Company.objects.filter(id=_company(request)).first()
    if comp is None:
        return Response({"rows": []})

    start, end = _dates(request)
    allowed = list(Gate.filter_queryset(
        request.user, "attendance.view", Employment.objects.all()
    ).filter(company=comp).values_list("id", flat=True))

    return Response({
        "from": start, "to": end,
        "rows": svc.pending_board(comp, start, end,
                                  employment_ids=allowed),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_penalty(request):
    """معاينة قبل التوقيع — الدرجة والمبلغ وما بقي من السقف."""
    from apps.employees.models import Employment

    Gate.require(request.user, "employees.edit")
    emp = Gate.filter_queryset(
        request.user, "employees.edit", Employment.objects.all()
    ).filter(id=request.data.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    v = ViolationType.objects.filter(
        id=request.data.get("violation_id"),
        company_id=_company(request)).first()
    if v is None:
        return Response({"detail": "المخالفة غير معروفة"}, status=404)

    try:
        on = date.fromisoformat(str(request.data.get("occurred_on")
                                    or date.today()))
    except ValueError:
        return Response({"detail": "تاريخ غير صالح"}, status=400)

    try:
        return Response(svc.preview(
            emp, v, on, occurrence=request.data.get("occurrence")))
    except svc.PenaltyError as e:
        return Response({"detail": str(e)}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def issue_penalty(request):
    """توقيع جزاء على موظف."""
    # ق-123: المخالفات والجزاءات ميزةٌ تُشترى.
    from apps.core.features.gate import Features

    Features.require(_company(request), "penalties")
    from apps.employees.models import Employment

    Gate.require(request.user, "employees.edit")
    emp = Gate.filter_queryset(
        request.user, "employees.edit", Employment.objects.all()
    ).filter(id=request.data.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    v = ViolationType.objects.filter(
        id=request.data.get("violation_id"),
        company_id=_company(request), is_active=True).first()
    if v is None:
        return Response({"detail": "المخالفة غير معروفة"}, status=404)

    try:
        on = date.fromisoformat(str(request.data.get("occurred_on")
                                    or date.today()))
    except ValueError:
        return Response({"detail": "تاريخ غير صالح"}, status=400)

    actor = getattr(request.user, "person", None)
    try:
        pen = svc.issue(
            employment=emp, violation=v, occurred_on=on,
            description=request.data.get("description", ""),
            employee_statement=request.data.get("employee_statement", ""),
            issued_by_person_id=actor.id if actor else None,
            apply_deduction=bool(request.data.get("apply_deduction", True)),
            count_occurrence=bool(request.data.get("count_occurrence", True)),
            occurrence=request.data.get("occurrence"))
    except svc.PenaltyError as e:
        return Response({"detail": str(e), "code": "penalty_refused"},
                        status=400)

    return Response({
        "id": pen.id, "occurrence": pen.occurrence,
        "kind": pen.kind, "kind_label": pen.get_kind_display(),
        "days": str(pen.days), "amount": str(pen.amount),
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def issue_batch(request):
    """
    توقيع جماعيّ على صفوف السجلّ (ق-121).

    فمن راجع سجلّ الشهر لا يفتح نافذةً لكل صفّ.
    """
    # ق-123: الاحتساب الآليّ للمخالفات ميزةٌ تُشترى.
    from apps.core.features.gate import Features

    Features.require(_company(request), "auto_attendance_penalties")
    from apps.accounts.models import Company

    Gate.require(request.user, "employees.edit")
    comp = Company.objects.filter(id=_company(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    rows = request.data.get("rows")
    if not isinstance(rows, list) or not rows:
        return Response({"detail": "لا صفوف"}, status=400)

    clean = []
    for r in rows:
        try:
            clean.append({**r, "date": date.fromisoformat(str(r["date"]))})
        except (KeyError, TypeError, ValueError):
            continue

    v = None
    if request.data.get("violation_id"):
        v = ViolationType.objects.filter(
            id=request.data["violation_id"], company=comp).first()

    actor = getattr(request.user, "person", None)
    out = svc.issue_batch(
        company=comp, rows=clean, violation=v,
        apply_deduction=bool(request.data.get("apply_deduction", True)),
        count_occurrence=bool(request.data.get("count_occurrence", True)),
        issued_by_person_id=actor.id if actor else None,
        employee_statement=request.data.get("employee_statement", ""))
    return Response(out)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def penalty_list(request):
    """
    صحيفة الجزاءات — للشركة أو لموظف بعينه.

    والنموذج يوجب صحيفةً لكل عامل تُدوَّن فيها مخالفاته.
    """
    from apps.employees.models import Employment

    Gate.require(request.user, "employees.view")
    qs = Penalty.objects.filter(
        employment__in=Gate.filter_queryset(
            request.user, "employees.view", Employment.objects.all())
    ).select_related("employment__person", "violation")

    if request.GET.get("employment_id"):
        qs = qs.filter(employment_id=request.GET["employment_id"])
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])

    return Response([{
        "id": p.id,
        "employment_id": p.employment_id,
        "employee_no": p.employment.employee_no,
        "name": p.employment.person.display_name,
        "violation": p.violation.name_ar,
        "occurred_on": p.occurred_on,
        "occurrence": p.occurrence,
        "kind": p.kind, "kind_label": p.get_kind_display(),
        "days": str(p.days), "amount": str(p.amount),
        "applied": p.apply_deduction,
        "counted": p.count_occurrence,
        "status": p.status, "status_label": p.get_status_display(),
        "description": p.description,
        "deducted": bool(p.deducted_in_run_id),
    } for p in qs.order_by("-occurred_on", "-id")[:300]])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_penalty(request, penalty_id):
    """إلغاء جزاء — لا حذفه."""
    Gate.require(request.user, "employees.edit")
    p = Penalty.objects.filter(
        id=penalty_id, company_id=_company(request)).first()
    if p is None:
        return Response({"detail": "غير موجود"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.cancel(penalty=p, reason=request.data.get("reason", ""),
                   by_person_id=actor.id if actor else None)
    except svc.PenaltyError as e:
        return Response({"detail": str(e)}, status=400)
    return Response({"cancelled": True})
