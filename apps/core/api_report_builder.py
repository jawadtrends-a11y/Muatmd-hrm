"""
مسارات باني التقارير المخصّصة (ق-126).
"""
from datetime import date

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.core.models import CustomReport, ReportSource
from apps.core.reports.base import ReportError
from apps.core.reports.builder import available_fields, run_custom_report


def _company(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


# ق-126: صلاحية كل مصدر — كنمط التقارير القائمة، فلا صلاحية
# عامّة للتقارير عندنا: من يرى الحضور يبني تقرير حضور، ومن يرى
# الرواتب يبني تقرير رواتب.
SOURCE_PERMISSION = {
    "employees": "employees.view",
    "attendance": "attendance.view",
    "requests": "requests.view",
    "payroll": "payroll.view",
}


def _require(request, source=None):
    """الصلاحية أوّلًا ثم الميزة (ق-123)."""
    if source:
        Gate.require(request.user, SOURCE_PERMISSION.get(
            source, "employees.view"))
    else:
        # القوائم العامّة: يكفي أن يرى الموظفين
        Gate.require(request.user, "employees.view")
    Features.require(_company(request), "custom_report_builder")


def _json(r):
    return {
        "id": r.id, "name_ar": r.name_ar, "description": r.description,
        "source": r.source, "source_label": r.get_source_display(),
        "fields": r.fields, "filters": r.filters, "sort_by": r.sort_by,
        "is_shared": r.is_shared,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def builder_sources(request):
    """المصادر وحقول كلٍّ — الواجهة تبني منها المُنشئ."""
    _require(request)
    perms = Gate.accessible_permissions(request.user)
    return Response({
        "sources": [
            {"value": v, "label": lbl,
             "fields": available_fields(v, request.user)}
            for v, lbl in ReportSource.choices
            # لا يُعرض مصدرٌ لا يستحقّه — فبناء تقرير رواتب بلا
            # صلاحيتها يُرفض عند التشغيل، وعرضه إغراءٌ بلا فائدة
            if SOURCE_PERMISSION.get(v, "") in perms
        ],
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def custom_reports(request):
    """تقاريره المحفوظة — عرضًا وإنشاءً."""
    _require(request)
    company_id = _company(request)

    if request.method == "GET":
        person = getattr(request.user, "person", None)
        qs = CustomReport.objects.filter(company_id=company_id)
        # ⚠️ غير المشترك يراه بانيه وحده — فتقريرٌ بناه غيره لغرضه
        # لا يزحم قائمة الجميع.
        rows = [r for r in qs
                if r.is_shared
                or (person and r.created_by_person_id == person.id)]
        return Response([_json(r) for r in rows])

    d = request.data
    name = str(d.get("name_ar") or "").strip()
    source = d.get("source")
    if source in SOURCE_PERMISSION:
        Gate.require(request.user, SOURCE_PERMISSION[source])
    fields = d.get("fields") or []
    if not name:
        return Response({"detail": "اسم التقرير مطلوب"}, status=400)
    if source not in ReportSource.values:
        return Response({"detail": "مصدر غير معروف"}, status=400)
    if not isinstance(fields, list) or not fields:
        return Response({"detail": "اختر حقلًا واحدًا على الأقلّ"},
                        status=400)

    from apps.accounts.models import Company

    comp = Company.objects.filter(id=company_id).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    person = getattr(request.user, "person", None)
    r = CustomReport.objects.create(
        account=comp.account, company=comp,
        name_ar=name, description=str(d.get("description") or "")[:255],
        source=source, fields=fields,
        filters=d.get("filters") or {},
        sort_by=str(d.get("sort_by") or "")[:60],
        is_shared=bool(d.get("is_shared", False)),
        created_by_person_id=person.id if person else None)
    return Response(_json(r), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def custom_report_detail(request, report_id):
    """تعديل تقرير أو حذفه — وبانيه أو من يملك تعديله."""
    _require(request)
    r = CustomReport.objects.filter(
        id=report_id, company_id=_company(request)).first()
    if r is None:
        return Response({"detail": "غير موجود"},
                        status=status.HTTP_404_NOT_FOUND)

    person = getattr(request.user, "person", None)
    mine = person and r.created_by_person_id == person.id
    if not mine and not Gate.check(request.user, "reports.manage").allowed:
        return Response({"detail": "لا تملك تعديل تقرير غيرك"}, status=403)

    if request.method == "DELETE":
        r.delete()
        return Response({"deleted": True})

    d = request.data
    for f in ("name_ar", "description", "sort_by"):
        if f in d:
            setattr(r, f, str(d[f] or ""))
    if isinstance(d.get("fields"), list) and d["fields"]:
        r.fields = d["fields"]
    if isinstance(d.get("filters"), dict):
        r.filters = d["filters"]
    if "is_shared" in d:
        r.is_shared = bool(d["is_shared"])
    r.save()
    return Response(_json(r))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_custom(request, report_id):
    """
    يشغّل تقريرًا محفوظًا — أو تعريفًا مؤقّتًا للمعاينة.

    فالمستخدم يرى نتيجته قبل أن يحفظه.
    """
    _require(request)
    from apps.accounts.models import Company

    comp = Company.objects.filter(id=_company(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if report_id:
        r = CustomReport.objects.filter(
            id=report_id, company=comp).first()
        if r is None:
            return Response({"detail": "غير موجود"}, status=404)
    else:
        d = request.data
        if d.get("source") not in ReportSource.values:
            return Response({"detail": "مصدر غير معروف"}, status=400)
        r = CustomReport(
            account=comp.account, company=comp, name_ar="معاينة",
            source=d["source"], fields=d.get("fields") or [],
            filters=d.get("filters") or {},
            sort_by=str(d.get("sort_by") or ""))

    def _d(key):
        try:
            return date.fromisoformat(str(request.data[key]))
        except (KeyError, TypeError, ValueError):
            return None

    try:
        cols, rows = run_custom_report(
            report=r, user=request.user, company=comp,
            date_from=_d("date_from"), date_to=_d("date_to"),
            extra_filters=request.data.get("filters") or {})
    except ReportError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({
        "title_ar": r.name_ar,
        "columns": [{"key": c.key, "label_ar": c.label_ar,
                     "kind": c.kind, "total": c.total} for c in cols],
        "rows": rows,
        "count": len(rows),
        "truncated": len(rows) >= 5000,
    })
