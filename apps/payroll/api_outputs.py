"""
API المخرجات: شاشات المسير · ملفات البنوك · حماية الأجور · القسائم.

ق-40: شاشات المسير ترجع JSON للعرض، والملفات تُنزَّل.
"""
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.payroll.models import BankTemplate, PayrollRun, Payslip
from apps.payroll.services.outputs import run_screens as rs
from apps.payroll.services.outputs.bank_file import (
    BankFileError, build_bank_file,
)
from apps.payroll.services.outputs.payslip_doc import (
    build_payslip_document, to_dict,
)
from apps.payroll.services.outputs.wps import (
    WPSError, build_wps_file, to_csv, validation_report,
)


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _get_run(request, run_id, permission="payroll.view"):
    qs = Gate.filter_queryset(request.user, permission,
                              PayrollRun.objects.all())
    return qs.filter(id=run_id, company_id=_company_id(request)).first()


# ══════════ شاشات المسير (اطلاع فقط — ق-40) ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_tab(request, run_id, tab):
    """
    تبويب من تبويبات المسير الستة.

    summary · payslips · excluded · adjustments · gosi · comparison
    """
    Gate.require(request.user, "payroll.view")
    run = _get_run(request, run_id)
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)

    handler = rs.TABS.get(tab)
    if handler is None:
        return Response({"detail": f"تبويب غير معروف: {tab}",
                         "available": sorted(rs.TABS)}, status=400)

    if tab == "payslips":
        data = handler(run, search=request.GET.get("q"))
    elif tab == "adjustments":
        data = handler(run, kind=request.GET.get("kind"))
    else:
        data = handler(run)

    return Response({"tab": tab, "run_no": run.run_no, "data": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_overview(request, run_id):
    """نظرة عامة مع أعداد التبويبات — للواجهة عند فتح المسير."""
    Gate.require(request.user, "payroll.view")
    run = _get_run(request, run_id)
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)

    return Response({
        "summary": rs.summary_tab(run),
        "tab_counts": rs.tab_counts(run),
        "available_tabs": sorted(rs.TABS),
        "can_submit": run.status == "calculated",
        "can_approve": run.status == "submitted",
        "can_export": run.status in ("approved", "paid"),
    })


# ══════════ ملفات البنوك ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_templates(request):
    """قوالب البنوك المتاحة للشركة."""
    Gate.require(request.user, "payroll.export")
    qs = Gate.filter_queryset(request.user, "payroll.export",
                              BankTemplate.objects.all())
    return Response([
        {
            "id": t.id, "code": t.code, "name_ar": t.name_ar,
            "bank_name_ar": t.bank_name_ar, "swift_prefix": t.swift_prefix,
            "is_builtin": t.is_builtin, "is_active": t.is_active,
            "column_count": t.columns.count(),
            "columns": [
                {"position": c.position, "header": c.header,
                 "source": c.source,
                 "source_label": c.get_source_display()}
                for c in t.columns.order_by("position")
            ],
        }
        for t in qs.filter(company_id=_company_id(request), is_active=True)
    ])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_file_preview(request, run_id, template_id):
    """معاينة قبل التنزيل — من استُبعد ولماذا، وأي خطأ يمنع الإرسال."""
    Gate.require(request.user, "payroll.export")
    run = _get_run(request, run_id, "payroll.export")
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)

    tqs = Gate.filter_queryset(request.user, "payroll.export",
                               BankTemplate.objects.all())
    tpl = tqs.filter(id=template_id,
                     company_id=_company_id(request)).first()
    if tpl is None:
        return Response({"detail": "القالب غير موجود"}, status=404)

    try:
        res = build_bank_file(run, tpl)
    except BankFileError as e:
        return Response({"detail": str(e), "code": "not_exportable"},
                        status=409)

    return Response({
        "filename": res.filename,
        "row_count": res.row_count,
        "total_amount": str(res.total_amount),
        "ready": res.ready,
        "excluded": res.excluded,
        "errors": res.errors,
        "preview": res.content.splitlines()[:6],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_file_download(request, run_id, template_id):
    """تنزيل ملف البنك."""
    Gate.require(request.user, "payroll.export")
    run = _get_run(request, run_id, "payroll.export")
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)

    tqs = Gate.filter_queryset(request.user, "payroll.export",
                               BankTemplate.objects.all())
    tpl = tqs.filter(id=template_id,
                     company_id=_company_id(request)).first()
    if tpl is None:
        return Response({"detail": "القالب غير موجود"}, status=404)

    try:
        res = build_bank_file(run, tpl)
    except BankFileError as e:
        return Response({"detail": str(e)}, status=409)

    if res.errors:
        return Response({
            "detail": "الملف يحوي أخطاء تمنع الإرسال",
            "code": "validation_errors", "errors": res.errors}, status=409)

    response = HttpResponse(res.content.encode(tpl.encoding),
                            content_type="text/csv; charset=" + tpl.encoding)
    response["Content-Disposition"] = f'attachment; filename="{res.filename}"'
    return response


# ══════════ حماية الأجور ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wps_preview(request, run_id):
    """تقرير ما قبل الإرسال لمُدد."""
    Gate.require(request.user, "payroll.export")
    run = _get_run(request, run_id, "payroll.export")
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)
    try:
        return Response(validation_report(build_wps_file(run)))
    except WPSError as e:
        return Response({"detail": str(e), "code": "not_exportable"},
                        status=409)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def wps_download(request, run_id):
    Gate.require(request.user, "payroll.export")
    run = _get_run(request, run_id, "payroll.export")
    if run is None:
        return Response({"detail": "المسير غير موجود"}, status=404)
    try:
        wps = build_wps_file(run)
    except WPSError as e:
        return Response({"detail": str(e)}, status=409)

    if wps.errors:
        return Response({"detail": "الملف يحوي أخطاء", "errors": wps.errors},
                        status=409)

    filename = f"WPS_{run.period_year}{run.period_month:02d}.csv"
    response = HttpResponse(to_csv(wps).encode("utf-8"),
                            content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ══════════ القسائم ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payslip_detail(request, payslip_id):
    """
    قسيمة راتب بلغة الموظف أو بلغة مطلوبة.

    الموظف يرى قسيمته، ومن يملك payslips.view_all يرى الجميع.
    """
    company_id = _company_id(request)
    person = getattr(request.user, "person", None)

    qs = Payslip.objects.filter(company_id=company_id)
    own = qs.filter(employment__person=person) if person else qs.none()

    if Gate.check(request.user, "payslips.view_all").allowed:
        scoped = Gate.filter_queryset(request.user, "payslips.view_all", qs)
    elif Gate.check(request.user, "payslips.view_team").allowed:
        scoped = Gate.filter_queryset(request.user, "payslips.view_team", qs)
    else:
        Gate.require(request.user, "payslips.view_own")
        scoped = own

    slip = scoped.filter(id=payslip_id).select_related(
        "run", "employment__person").prefetch_related("lines").first()
    if slip is None:
        return Response({"detail": "القسيمة غير موجودة"}, status=404)

    if slip.run.status not in ("approved", "paid"):
        if not Gate.check(request.user, "payroll.view").allowed:
            return Response(
                {"detail": "القسيمة لا تُعرض قبل اعتماد المسير",
                 "code": "run_not_approved"}, status=409)

    locale = request.GET.get("locale")
    doc = build_payslip_document(slip, locale=locale)
    return Response(to_dict(doc))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_payslips(request):
    """قسائمي — للخدمة الذاتية."""
    Gate.require(request.user, "payslips.view_own")
    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    slips = Payslip.objects.filter(
        employment__person=person,
        run__status__in=["approved", "paid"],
    ).select_related("run").order_by("-run__period_year",
                                     "-run__period_month")[:24]

    return Response([
        {
            "payslip_id": s.id,
            "period": f"{s.run.period_year}-{s.run.period_month:02d}",
            "net_pay": str(s.net_pay),
            "payment_date": (str(s.run.payment_date)
                             if s.run.payment_date else None),
            "company": s.company.legal_name_ar,
        }
        for s in slips
    ])
