"""
تشغيل التقارير المخصّصة (ق-126).

⚠️ **يمرّ بالبوابة والعزل كأي تقرير**: من نطاقه إدارته لا يرى
غيرها ولو اختار حقولها، ومن لا يملك صلاحية الرواتب لا يبني تقريرًا
عن الرواتب.
"""
from datetime import date

from apps.core.access.gate import Gate
from apps.core.reports.base import Column, ReportError
from apps.core.reports.builder_fields import field_map


def _queryset_for(source, user, company):
    """
    استعلام المصدر — **مرشَّحًا بالبوابة**.

    فالتقرير المخصّص لا يفتح ما يغلقه النظام: مدير الإدارة يبني
    تقريرًا عن إدارته وحدها.
    """
    from apps.attendance.models import AttendanceDay
    from apps.employees.models import Employment
    from apps.leaves.models import Request
    from apps.payroll.models import Payslip

    if source == "employees":
        return Gate.filter_queryset(
            user, "employees.view", Employment.objects.all()
        ).filter(company=company)

    if source == "attendance":
        return Gate.filter_queryset(
            user, "attendance.view", AttendanceDay.objects.all()
        ).filter(company=company)

    if source == "requests":
        return Gate.filter_queryset(
            user, "requests.view", Request.objects.all()
        ).filter(company=company)

    if source == "payroll":
        Gate.require(user, "payroll.view")
        return Gate.filter_queryset(
            user, "payroll.view", Payslip.objects.all()
        ).filter(company=company)

    raise ReportError(f"مصدر غير معروف: {source}")


#: أي حقل تاريخٍ يُصفّى به كل مصدر
DATE_FIELD = {
    "employees": "join_date",
    "attendance": "work_date",
    "requests": "submitted_at",
    "payroll": "run__payment_date",
}

#: التصفية المتاحة: المفتاح → مسار ORM لكل مصدر
FILTER_PATHS = {
    "branch_id": {"employees": "branch_id",
                  "attendance": "employment__branch_id",
                  "requests": "employment__branch_id",
                  "payroll": "employment__branch_id"},
    "department_id": {"employees": "department_id",
                      "attendance": "employment__department_id",
                      "requests": "employment__department_id",
                      "payroll": "employment__department_id"},
    "status": {"employees": "status", "attendance": "status",
               "requests": "status", "payroll": None},
    "request_type": {"requests": "request_type"},
}


def run_custom_report(*, report, user, company, date_from=None,
                      date_to=None, extra_filters=None):
    """
    يشغّل تقريرًا مخصّصًا ويرجع أعمدةً وصفوفًا.

    ⚠️ **الحقول تُصفّى بالصلاحية**: من لا يملك `payroll.view` لا
    يرى عمود الراتب ولو كان محفوظًا في التقرير — فالتقرير يُشارَك
    بين موظفين نطاقاتهم مختلفة.
    """
    fmap = field_map(report.source)
    perms = Gate.accessible_permissions(user)

    chosen = []
    for key in (report.fields or []):
        f = fmap.get(key)
        if f is None:
            continue                     # حقلٌ حُذف من الكتالوج
        if f.perm and f.perm not in perms:
            continue                     # ليس له
        chosen.append(f)

    if not chosen:
        raise ReportError("لا حقول متاحة لك في هذا التقرير")

    qs = _queryset_for(report.source, user, company)

    # التصفية المحفوظة ثم الممرَّرة — والممرَّرة تغلب
    filters = dict(report.filters or {})
    filters.update(extra_filters or {})
    for key, value in filters.items():
        if value in (None, "", []):
            continue
        path = FILTER_PATHS.get(key, {}).get(report.source)
        if path:
            qs = qs.filter(**{path: value})

    date_path = DATE_FIELD.get(report.source)
    if date_path and date_from:
        qs = qs.filter(**{f"{date_path}__gte": date_from})
    if date_path and date_to:
        qs = qs.filter(**{f"{date_path}__lte": date_to})

    if report.sort_by:
        key = report.sort_by.lstrip("-")
        f = fmap.get(key)
        if f:
            qs = qs.order_by(("-" if report.sort_by.startswith("-") else "")
                             + f.path)

    paths = [f.path for f in chosen]
    rows = []
    # ⚠️ سقفٌ صريح: تقريرٌ بلا حدّ يُسقط الخادم على شركةٍ كبيرة،
    # والمستخدم لا يقرأ خمسين ألف صفٍّ على الشاشة.
    for raw in qs.values(*paths)[:5000]:
        rows.append({f.key: raw.get(f.path) for f in chosen})

    columns = [
        Column(key=f.key, label_ar=f.label_ar,
               kind=f.kind, total=f.total)
        for f in chosen
    ]
    return columns, rows


def available_fields(source, user):
    """الحقول التي يستحقّها هذا المستخدم من هذا المصدر."""
    perms = Gate.accessible_permissions(user)
    out = []
    for f in field_map(source).values():
        if f.perm and f.perm not in perms:
            continue
        out.append({
            "key": f.key, "label_ar": f.label_ar,
            "label_en": f.label_en or f.label_ar,
            "kind": f.kind, "total": f.total,
        })
    return out
