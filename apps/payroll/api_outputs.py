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
            "id": t.id, "code": t.code, "name_ar": t.name_ar, "name_en": getattr(t, "name_en", ""),
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


# ══════════ إدارة قوالب البنوك ══════════

def _template_json(t):
    return {
        "id": t.id, "code": t.code, "name_ar": t.name_ar, "name_en": getattr(t, "name_en", ""),
        "bank_name_ar": t.bank_name_ar,
        "swift_prefix": t.swift_prefix,
        "file_format": t.file_format,
        "delimiter": t.delimiter,
        "include_header": t.include_header,
        "encoding": t.encoding,
        "filename_pattern": t.filename_pattern,
        "note": t.note,
        "is_builtin": t.is_builtin,
        "is_active": t.is_active,
        "columns": [{
            "id": c.id, "position": c.position, "header": c.header,
            "source": c.source, "source_label": c.get_source_display(),
            "constant_value": c.constant_value,
            "number_format": c.number_format,
        } for c in t.columns.order_by("position")],
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bank_template_create(request):
    """
    قالب بنك جديد.

    فكل بنك له صيغة ملف رواتب خاصة، والشركة قد تتعامل مع بنك لم
    نبنِ قالبه — فتبنيه بنفسها.
    """
    from apps.accounts.models import Company
    from apps.payroll.models import BankTemplate

    Gate.require(request.user, "payroll.structures")
    company_id = _company_id(request)

    code = (request.data.get("code") or "").strip().upper()
    if not code or not request.data.get("name_ar"):
        return Response({"detail": "الرمز والاسم مطلوبان"}, status=400)

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    if BankTemplate.objects.filter(company_id=_company_id(request), code=code).exists():
        return Response({"detail": f"الرمز مستخدم: {code}"}, status=409)

    comp = Company.objects.filter(id=_company_id(request)).first()
    t = BankTemplate.objects.create(
        account_id=comp.account_id, company_id=company_id,
        code=code, name_ar=request.data["name_ar"],
        bank_name_ar=request.data.get("bank_name_ar", ""),
        swift_prefix=request.data.get("swift_prefix", ""),
        delimiter=request.data.get("delimiter", ","),
        include_header=bool(request.data.get("include_header", True)),
        note=request.data.get("note", ""))

    from apps.core.services.audit import log_create
    log_create(instance=t, actor=getattr(request.user, "person", None),
               label=t.code, summary=f"قالب بنك جديد: {t.name_ar}",
               channel="web")
    return Response(_template_json(t), status=201)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def bank_template_detail(request, template_id):
    """
    تعديل قالب أو حذفه.

    والقالب المدمج (is_builtin) لا يُحذف: نبنيه ونحدّثه بتغيّر
    متطلبات البنك. ويُعطَّل من لا يستعمله، ويُنسخ من يريد تعديله.
    """
    from apps.payroll.models import BankTemplate

    Gate.require(request.user, "payroll.structures")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    t = BankTemplate.objects.filter(id=template_id, company_id=_company_id(request)).first()
    if t is None:
        return Response({"detail": "القالب غير موجود"}, status=404)

    if request.method == "DELETE":
        # المدمج يُحذف كغيره: البنك يغيّر متطلباته، والشركة تواكبه
        # الآن لا حين نحدّث القالب (ق-88)
        t.delete()
        return Response({"deleted": True})

    d = request.data
    # المدمج المعدَّل يفقد وسمه: صار قالب الشركة لا قالبنا، فلا
    # يُستبدل بتحديث منّا
    if t.is_builtin:
        t.is_builtin = False
    for f in ("name_ar", "bank_name_ar", "swift_prefix", "delimiter",
              "encoding", "filename_pattern", "note"):
        if f in d:
            setattr(t, f, d[f] or "")
    for f in ("include_header", "is_active"):
        if f in d:
            setattr(t, f, bool(d[f]))
    t.save()
    return Response(_template_json(t))


@api_view(["POST", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def bank_template_columns(request, template_id):
    """أعمدة القالب — تُضاف وتُعدَّل وتُحذف."""
    from apps.payroll.models import BankColumn, BankTemplate

    Gate.require(request.user, "payroll.structures")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    t = BankTemplate.objects.filter(id=template_id, company_id=_company_id(request)).first()
    if t is None:
        return Response({"detail": "القالب غير موجود"}, status=404)

    # أعمدة المدمج تُعدَّل كغيرها: من يغيّر بنكه ترتيب الأعمدة
    # يحتاج تعديلها اليوم — و«مدمج» وسم لا قيد
    if request.method == "DELETE":
        cid = request.GET.get("column_id") or request.data.get("column_id")
        col = t.columns.filter(id=cid).first()
        if col is None:
            return Response({"detail": "العمود غير موجود"}, status=404)
        pos = col.position
        col.delete()
        for c in t.columns.filter(position__gt=pos).order_by("position"):
            c.position -= 1
            c.save(update_fields=["position"])
        return Response(_template_json(t))

    if t.is_builtin:
        t.is_builtin = False
        t.save(update_fields=["is_builtin"])

    if request.method == "POST":
        last = t.columns.order_by("-position").first()
        BankColumn.objects.create(
            template=t,
            position=(last.position + 1) if last else 1,
            header=request.data.get("header", ""),
            source=request.data.get("source", "constant"),
            constant_value=request.data.get("constant_value", ""),
            number_format=request.data.get("number_format", ""))
        return Response(_template_json(t), status=201)

    col = t.columns.filter(id=request.data.get("column_id")).first()
    if col is None:
        return Response({"detail": "العمود غير موجود"}, status=404)

    if "move" in request.data:
        delta = -1 if request.data["move"] == "up" else 1
        other = t.columns.filter(position=col.position + delta).first()
        if other is not None:
            # الترتيب فريد لكل قالب — نمرّ بموضع مؤقّت
            mine, theirs = col.position, other.position
            col.position = 0
            col.save(update_fields=["position"])
            other.position = mine
            other.save(update_fields=["position"])
            col.position = theirs
            col.save(update_fields=["position"])
    else:
        for f in ("header", "source", "constant_value", "number_format"):
            if f in request.data:
                setattr(col, f, request.data[f] or "")
        col.save()

    return Response(_template_json(t))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bank_template_clone(request, template_id):
    """
    ينسخ قالبًا — فمن يريد تعديل المدمج ينسخه ويعدّل نسخته.
    """
    from apps.payroll.models import BankColumn, BankTemplate

    Gate.require(request.user, "payroll.structures")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    src = BankTemplate.objects.filter(id=template_id, company_id=_company_id(request)).first()
    if src is None:
        return Response({"detail": "القالب غير موجود"}, status=404)

    code = (request.data.get("code") or f"{src.code}-COPY").upper()
    if BankTemplate.objects.filter(
            company_id=src.company_id, code=code).exists():
        return Response({"detail": f"الرمز مستخدم: {code}"}, status=409)

    new = BankTemplate.objects.create(
        account_id=src.account_id, company_id=src.company_id,
        code=code,
        name_ar=request.data.get("name_ar") or f"{src.name_ar} (نسخة)",
        name_en=request.data.get("name_en", ""),
        bank_name_ar=src.bank_name_ar, swift_prefix=src.swift_prefix,
        file_format=src.file_format, delimiter=src.delimiter,
        include_header=src.include_header, line_ending=src.line_ending,
        encoding=src.encoding, filename_pattern=src.filename_pattern,
        note=src.note, is_builtin=False)

    BankColumn.objects.bulk_create([
        BankColumn(template=new, position=c.position, header=c.header,
                   source=c.source, constant_value=c.constant_value,
                   number_format=c.number_format)
        for c in src.columns.order_by("position")])

    return Response(_template_json(new), status=201)
