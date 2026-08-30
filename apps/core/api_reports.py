"""
API التقارير (ق-40).

نقطتان: قائمة التقارير — تبني الواجهة تلقائيًا من المعايير المُعلَنة،
وتشغيل تقرير بصيغة json أو xlsx أو pdf.
"""
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.reports import ReportError, catalog, get_report, load_reports

# حدود التصدير — PDF يبني كل صفحة فهو أثقل بكثير
PDF_ROW_LIMIT = 10_000
JSON_ROW_LIMIT = 5_000

load_reports()


def _company(request):
    from apps.accounts.models import Company
    company_id = getattr(getattr(request, "account_ctx", None),
                         "active_company_id", None)
    if company_id is None:
        return None
    return Gate.filter_queryset(
        request.user, "company.view", Company.objects.all()
    ).filter(id=company_id).first()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def reports_catalog(request):
    """
    قائمة التقارير المتاحة للمستخدم.

    تُخفى التقارير التي لا يملك صلاحيتها — فلا يرى ما لا يستطيع
    تشغيله.
    """
    groups = []
    for g in catalog():
        allowed = [
            r for r in g["reports"]
            if Gate.check(request.user, r["permission"]).allowed
        ]
        if allowed:
            groups.append({**g, "reports": allowed})

    return Response({
        "groups": groups,
        "export_param": "export",
        "formats": [
            {"value": "json", "label": "عرض"},
            {"value": "xlsx", "label": "إكسل"},
            {"value": "pdf", "label": "PDF"},
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_report(request, key):
    """
    يشغّل تقريرًا بالصيغة المطلوبة.

    المعايير تأتي في الاستعلام: ?as_of=2026-08-31&branch_id=3
    """
    try:
        cls = get_report(key)
    except ReportError as e:
        return Response({"detail": str(e), "code": "unknown_report"},
                        status=404)

    Gate.require(request.user, cls.permission)

    comp = _company(request)
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    # جمع المعايير المُعلَنة فقط — لا يمر شيء غير معرّف
    options = {}
    for p in cls.params:
        raw = request.GET.get(p.key)
        if raw in (None, ""):
            if p.default is not None:
                options[p.key] = p.default
            continue
        if p.kind == "bool":
            options[p.key] = raw.lower() in ("1", "true", "yes", "نعم")
        else:
            options[p.key] = raw

    try:
        result = cls(company=comp, **options).run()
    except ReportError as e:
        return Response({
            "detail": str(e), "code": "missing_params",
            "params": [{"key": p.key, "label_ar": p.label_ar,
                        "required": p.required} for p in cls.params],
        }, status=400)
    except Exception as e:  # noqa: BLE001
        return Response({"detail": f"تعذّر تشغيل التقرير: {e}",
                         "code": "report_failed"}, status=500)

    # ملاحظة: لا نستخدم "format" لأنه محجوز في DRF ويعترضه قبل
    # وصوله للدالة، فيرد 404 على أي قيمة لا يعرفها
    fmt = (request.GET.get("export") or "json").lower()

    if fmt == "xlsx":
        from apps.core.reports.excel import excel_filename, export_to_excel
        data = export_to_excel(result, company_name=comp.legal_name_ar)
        response = HttpResponse(
            data,
            content_type=("application/vnd.openxmlformats-officedocument"
                          ".spreadsheetml.sheet"))
        response["Content-Disposition"] = (
            f'attachment; filename="{excel_filename(result)}"')
        return response

    if fmt == "pdf":
        if result.row_count > PDF_ROW_LIMIT:
            return Response({
                "detail": (f"التقرير يحوي {result.row_count} صفًا — الحد "
                           f"الأقصى لـPDF {PDF_ROW_LIMIT}. ضيّق الفترة أو "
                           "صدّر إكسل."),
                "code": "too_many_rows",
                "row_count": result.row_count,
            }, status=413)
        from apps.core.reports.pdf import export_to_pdf, pdf_filename
        data = export_to_pdf(result, company_name=comp.legal_name_ar)
        response = HttpResponse(data, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{pdf_filename(result)}"')
        return response

    if fmt != "json":
        return Response({"detail": f"صيغة غير مدعومة: {fmt}",
                         "supported": ["json", "xlsx", "pdf"]}, status=400)

    truncated = result.row_count > JSON_ROW_LIMIT
    rows = result.rows[:JSON_ROW_LIMIT] if truncated else result.rows

    return Response({
        "key": result.key,
        "title_ar": result.title_ar,
        "subtitle_ar": result.subtitle_ar,
        "company": comp.legal_name_ar,
        "columns": [
            {"key": c.key, "label_ar": c.label_ar, "kind": c.kind,
             "total": c.total}
            for c in result.columns
        ],
        "rows": rows,
        "totals": result.totals,
        "row_count": result.row_count,
        "truncated": truncated,
        "notes": result.notes,
        "meta": result.meta,
    })
