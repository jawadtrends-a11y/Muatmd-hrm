"""مسارات أنواع الطلبات المخصّصة (ق-142)."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import Employment, EmploymentStatus
from apps.leaves.models import (
    CustomRequestField, CustomRequestType, FieldKind)
from apps.leaves.services import custom_types as svc


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


def _json(t, with_fields=True):
    out = {
        "id": t.id, "code": t.code, "name_ar": t.name_ar,
        "hint_ar": t.hint_ar,
        "requires_attachment": t.requires_attachment,
        "daily_unique": t.daily_unique,
        "is_active": t.is_active,
        "field_count": t.fields.count(),
    }
    if with_fields:
        out["fields"] = [{
            "id": f.id, "key": f.key, "label_ar": f.label_ar,
            "kind": f.kind, "kind_label": f.get_kind_display(),
            "is_required": f.is_required,
            "options": f.option_list,
            "sort_order": f.sort_order,
        } for f in t.fields.all()]
    return out


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def custom_types(request):
    """أنواع الطلبات المخصّصة — عرضًا وإنشاءً."""
    Features.require(_company_id(request), "req_custom")

    if request.method == "GET":
        Gate.require(request.user, "requests.view")
        qs = CustomRequestType.objects.filter(
            company_id=_company_id(request))
        return Response({
            "types": [_json(t) for t in qs],
            "kinds": [{"value": v, "label": lbl}
                      for v, lbl in FieldKind.choices],
        })

    Gate.require(request.user, "requests.manage")
    from apps.accounts.models import Company

    # مقيَّد بشركة المنفّذ النشطة
    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    code = str(d.get("code") or "").strip().upper()
    if not code or not str(d.get("name_ar") or "").strip():
        return Response({"detail": "الرمز والاسم مطلوبان"}, status=400)
    if CustomRequestType.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    t = CustomRequestType.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=d.get("name_ar", ""), name_en=d.get("name_en", ""),
        hint_ar=str(d.get("hint_ar") or "")[:255],
        requires_attachment=bool(d.get("requires_attachment", False)),
        daily_unique=bool(d.get("daily_unique", False)))
    return Response(_json(t), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def custom_type_detail(request, type_id):
    """
    تعديل نوعٍ أو تعطيله.

    ⚠️ **والمستعمل لا يُحذف**: طلباتٌ قائمة تشير إليه.
    """
    from apps.leaves.models import Request

    Gate.require(request.user, "requests.manage")
    Features.require(_company_id(request), "req_custom")

    t = CustomRequestType.objects.filter(
        id=type_id, company_id=_company_id(request)).first()
    if t is None:
        return Response({"detail": "غير موجود"}, status=404)

    if request.method == "DELETE":
        used = Request.objects.filter(
            payload__custom_type_code=t.code).exists()
        if used:
            t.is_active = False
            t.save(update_fields=["is_active"])
            return Response({"deactivated": True,
                             "detail": "مستعمل — عُطّل ولم يُحذف"})
        t.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "name_en", "hint_ar"):
        if f in d:
            setattr(t, f, str(d[f] or ""))
    for f in ("requires_attachment", "daily_unique", "is_active"):
        if f in d:
            setattr(t, f, bool(d[f]))
    t.save()
    return Response(_json(t))


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def custom_type_fields(request, type_id):
    """إضافة حقلٍ لنوع أو حذفه."""
    Gate.require(request.user, "requests.manage")
    Features.require(_company_id(request), "req_custom")

    t = CustomRequestType.objects.filter(
        id=type_id, company_id=_company_id(request)).first()
    if t is None:
        return Response({"detail": "النوع غير موجود"}, status=404)

    if request.method == "DELETE":
        CustomRequestField.objects.filter(
            request_type=t, id=request.data.get("field_id")).delete()
        return Response({"deleted": True})

    d = request.data
    try:
        key = svc.validate_key(d.get("key"))
    except svc.CustomTypeError as e:
        return Response({"detail": str(e)}, status=400)

    if CustomRequestField.objects.filter(request_type=t,
                                         key=key).exists():
        return Response({"detail": "المفتاح مستعمل في هذا النوع"},
                        status=409)

    last = t.fields.order_by("-sort_order").first()
    f = CustomRequestField.objects.create(
        account_id=t.account_id, company_id=t.company_id,
        request_type=t, key=key,
        label_ar=str(d.get("label_ar") or key)[:120],
        kind=d.get("kind") or FieldKind.TEXT,
        is_required=bool(d.get("is_required", True)),
        options=str(d.get("options") or "")[:500],
        sort_order=(last.sort_order + 10) if last else 10)
    return Response({"id": f.id, "key": f.key},
                    status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_custom_types(request):
    """الأنواع المتاحة لي — المفعّلة وحدها."""
    Features.require(_company_id(request), "req_custom")

    qs = CustomRequestType.objects.filter(
        company_id=_company_id(request), is_active=True)
    return Response([_json(t) for t in qs])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_custom(request, type_id):
    """تقديم طلبٍ من نوعٍ مخصّص."""
    Features.require(_company_id(request), "req_custom")

    me = _me(request)
    if me is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    t = CustomRequestType.objects.filter(
        id=type_id, company_id=_company_id(request),
        is_active=True).first()
    if t is None:
        return Response({"detail": "الطلب غير متاح"}, status=404)

    try:
        out = svc.submit(employment=me, request_type=t,
                         payload=request.data.get("payload") or {},
                         note=request.data.get("note", ""))
    except svc.CustomTypeError as e:
        return Response({"detail": str(e)}, status=400)
    except Exception as e:                      # noqa: BLE001
        return Response({"detail": str(e)}, status=400)

    return Response({"request_no": out.request.request_no,
                     "status": out.request.status},
                    status=status.HTTP_201_CREATED)
