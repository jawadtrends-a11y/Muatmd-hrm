"""
واجهة العملاء البرمجية (ق-151).

⚠️ **قراءةٌ فقط**: فالكتابة خطؤها يُفسد بيانات، وتُفتح حين تُطلب.

⚠️⚠️ **وكل نداءٍ مقيَّدٌ بشركة المفتاح** — فمفتاحٌ يقرأ شركةً
أخرى تسريبٌ لا تكامل.
"""
import functools

from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.models import ApiScope
from apps.core.services import api_keys as svc
from apps.core.tenancy.context import account_scope


def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip()
            if fwd else request.META.get("REMOTE_ADDR", ""))


def api_key_required(scope):
    """
    يحرس مسارًا بمفتاحٍ ونطاقٍ وسقف.

    ⚠️ **والترتيب مقصود**: المفتاح، فالنطاق، فالسقف — فمن لا مفتاح
    له لا يُحسب عليه سقف.
    """
    def outer(fn):
        @functools.wraps(fn)
        def inner(request, *a, **kw):
            raw = (request.META.get("HTTP_X_API_KEY")
                   or request.headers.get("X-API-Key", ""))
            key, err = svc.authenticate(raw)
            if key is None:
                return Response({"detail": err or "مفتاح مطلوب",
                                 "code": "api_key"}, status=401)

            if not key.allows(scope):
                return Response({
                    "detail": f"المفتاح لا يملك نطاق «{scope}»",
                    "code": "scope"}, status=403)

            ok, used = svc.within_rate_limit(key)
            if not ok:
                return Response({
                    "detail": (f"تجاوزتَ السقف: {used} نداءً في الساعة "
                               f"من {key.rate_limit_per_hour}"),
                    "code": "rate_limit"}, status=429)

            # ⚠️ **والقراءة داخل سياق حساب المفتاح وحده**
            with account_scope(key.account_id):
                request.api_key = key
                res = fn(request, *a, **kw)
                svc.log_call(key=key, path=request.path,
                             method=request.method,
                             status_code=res.status_code,
                             ip=_client_ip(request))
                return res
        return inner
    return outer


def _paginate(request, qs, limit=100):
    """صفحاتٌ بسيطة — فالنداء لا يُنزل عشرة آلاف صفّ."""
    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    limit = min(int(request.GET.get("limit", limit) or limit), 500)
    total = qs.count()
    start = (page - 1) * limit
    return list(qs[start:start + limit]), {
        "page": page, "limit": limit, "total": total,
        "pages": (total + limit - 1) // limit,
    }


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@api_key_required(ApiScope.EMPLOYEES)
def employees(request):
    """موظفو الشركة — ⚠️ **بلا بياناتٍ حسّاسة**."""
    from apps.employees.models import Employment

    qs = (Employment.objects
          .filter(company_id=request.api_key.company_id)
          .select_related("person", "department", "job_title")
          .order_by("employee_no"))
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])

    rows, meta = _paginate(request, qs)
    return Response({
        "data": [{
            "employee_no": e.employee_no,
            "name": e.person.display_name,
            "department": getattr(e.department, "name_ar", "") or "",
            "job_title": getattr(e.job_title, "name_ar", "") or "",
            "join_date": e.join_date,
            "status": e.status,
            # ⚠️ **ولا هويةَ ولا آيبان ولا راتب** — فالتكامل لا
            # يحتاجها، وتسريبُها يضرّ صاحبها.
        } for e in rows],
        "meta": meta,
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@api_key_required(ApiScope.ATTENDANCE)
def attendance(request):
    """سجلّ الحضور اليوميّ."""
    from apps.attendance.models import AttendanceDay

    qs = (AttendanceDay.objects
          .filter(company_id=request.api_key.company_id)
          .select_related("employment")
          .order_by("-work_date"))
    if request.GET.get("from"):
        qs = qs.filter(work_date__gte=request.GET["from"])
    if request.GET.get("to"):
        qs = qs.filter(work_date__lte=request.GET["to"])
    if request.GET.get("employee_no"):
        qs = qs.filter(
            employment__employee_no=request.GET["employee_no"])

    rows, meta = _paginate(request, qs)
    return Response({
        "data": [{
            "employee_no": d.employment.employee_no,
            "work_date": d.work_date,
            "status": d.status,
            "worked_minutes": d.worked_minutes,
            "late_minutes": getattr(d, "late_minutes", 0),
            "overtime_minutes": d.approved_overtime_minutes,
        } for d in rows],
        "meta": meta,
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@api_key_required(ApiScope.PAYROLL)
def payroll_runs(request):
    """
    المسيرات — **المعتمدة وحدها**.

    ⚠️ فمسيرٌ قيد الاحتساب أرقامٌ غير نهائية، وقراءتُه تُبنى عليها
    قيودٌ خاطئة.
    """
    from apps.payroll.models import PayrollRun, PayrollRunStatus

    qs = (PayrollRun.objects
          .filter(company_id=request.api_key.company_id,
                  status__in=[PayrollRunStatus.APPROVED,
                              PayrollRunStatus.PAID])
          .order_by("-period_year", "-period_month"))

    rows, meta = _paginate(request, qs)
    return Response({
        "data": [{
            "run_no": r.run_no,
            "period": f"{r.period_year}-{r.period_month:02d}",
            "run_type": r.run_type,
            "status": r.status,
            "employee_count": r.employee_count,
            "total_gross": str(r.total_gross),
            "total_deductions": str(r.total_deductions),
            "total_net": str(r.total_net),
            "approved_at": r.approved_at,
        } for r in rows],
        "meta": meta,
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@api_key_required(ApiScope.PAYROLL)
def payroll_run_detail(request, run_no):
    """قسائم مسيرٍ معتمد — للتكامل المحاسبيّ."""
    from apps.payroll.models import PayrollRun, PayrollRunStatus

    run = PayrollRun.objects.filter(
        company_id=request.api_key.company_id, run_no=run_no,
        status__in=[PayrollRunStatus.APPROVED,
                    PayrollRunStatus.PAID]).first()
    if run is None:
        return Response({"detail": "المسير غير موجود أو غير معتمد"},
                        status=404)

    slips = run.payslips.select_related(
        "employment__person").prefetch_related("lines")
    return Response({
        "run_no": run.run_no,
        "period": f"{run.period_year}-{run.period_month:02d}",
        "total_net": str(run.total_net),
        "payslips": [{
            "employee_no": s.employment.employee_no,
            "name": s.employment.person.display_name,
            "gross": str(s.gross_earnings),
            "deductions": str(s.total_deductions),
            "net": str(s.net_pay),
            "lines": [{
                "code": l.component_code, "name": l.name_ar,
                "type": l.line_type, "amount": str(l.amount),
            } for l in s.lines.all()],
        } for s in slips],
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@api_key_required(ApiScope.LEAVES)
def leave_requests(request):
    """الطلبات والإجازات."""
    from apps.leaves.models import Request

    qs = (Request.objects
          .filter(company_id=request.api_key.company_id)
          .select_related("employment").order_by("-id"))
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    if request.GET.get("type"):
        qs = qs.filter(request_type=request.GET["type"])

    rows, meta = _paginate(request, qs)
    return Response({
        "data": [{
            "request_no": r.request_no,
            "employee_no": r.employment.employee_no,
            "type": r.request_type,
            "status": r.status,
            "created_at": r.created_at,
        } for r in rows],
        "meta": meta,
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@api_key_required(ApiScope.ORG)
def org_structure(request):
    """الهيكل التنظيميّ — إداراتٌ ومسمّيات."""
    from apps.organization.models import Department, JobTitle

    cid = request.api_key.company_id
    return Response({
        "departments": [{
            "code": d.code, "name_ar": d.name_ar,
            "parent": getattr(d.parent, "code", None),
        } for d in Department.objects.filter(company_id=cid)],
        "job_titles": [{
            "code": getattr(j, "code", ""), "name_ar": j.name_ar,
        } for j in JobTitle.objects.filter(company_id=cid)],
    })


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@api_key_required(ApiScope.ORG)
def whoami(request):
    """
    تحقّقٌ من المفتاح — **أوّل ما يناديه المتكامل**.
    """
    k = request.api_key
    return Response({
        "company": k.company.legal_name_ar,
        "key_name": k.name,
        "scopes": k.scopes,
        "rate_limit_per_hour": k.rate_limit_per_hour,
        "expires_on": k.expires_on,
    })
