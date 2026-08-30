"""
تقارير الحضور والإجازات والموظفين.
"""
from datetime import date
from decimal import Decimal

from apps.core.reports.base import Column, Param, Report, register

ZERO = Decimal("0")


# ══════════════════ الحضور ══════════════════

@register
class AttendanceSummaryReport(Report):
    """ملخص الحضور الشهري — الأساس الذي يقرأه محرك الرواتب."""

    key = "attendance_summary"
    title_ar = "تقرير ملخص الحضور والانصراف"
    group = "attendance"
    permission = "attendance.view"
    params = [
        Param("year", "السنة", "text", required=True),
        Param("month", "الشهر", "text", required=True),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("department", "القسم", width=18),
            Column("worked_days", "أيام العمل", "number", width=12,
                   total=True),
            Column("absence_days", "أيام الغياب", "number", width=12,
                   total=True),
            Column("leave_days", "أيام الإجازة", "number", width=12,
                   total=True),
            Column("late_minutes", "دقائق التأخير", "number", width=14,
                   total=True),
            Column("overtime_hours", "ساعات إضافية معتمدة", "number",
                   width=18, total=True),
        ]

    def subtitle(self):
        return (f"{self.options.get('year')}-"
                f"{int(self.options.get('month', 1)):02d}")

    def rows(self):
        from apps.attendance.models import AttendanceMonthlySummary

        qs = AttendanceMonthlySummary.objects.filter(
            company=self.company,
            period_year=int(self.options["year"]),
            period_month=int(self.options["month"]),
        ).select_related("employment__person", "employment__department")

        return [
            {
                "employee_no": s.employment.employee_no,
                "name": s.employment.person.display_name,
                "department": (s.employment.department.name_ar
                               if s.employment.department else ""),
                "worked_days": str(s.worked_days),
                "absence_days": str(s.unpaid_absent_days),
                "leave_days": str(s.paid_leave_days),
                "late_minutes": s.late_minutes,
                "overtime_hours": f"{s.approved_overtime_minutes / 60:.2f}",
            }
            for s in qs.order_by("employment__employee_no")
        ]


@register
class AttendanceDetailReport(Report):
    """الحضور والانصراف يومًا بيوم."""

    key = "attendance_detail"
    title_ar = "تقرير الحضور والانصراف"
    group = "attendance"
    permission = "attendance.view"
    params = [
        Param("from_date", "من", "date", required=True),
        Param("to_date", "إلى", "date", required=True),
        Param("employment_id", "الموظف", "select"),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=24),
            Column("work_date", "التاريخ", "date", width=12),
            Column("status", "الحالة", width=14),
            Column("first_in", "الحضور", width=10),
            Column("last_out", "الانصراف", width=10),
            Column("worked_minutes", "دقائق العمل", "number", width=12,
                   total=True),
            Column("late_minutes", "التأخير", "number", width=10,
                   total=True),
            Column("overtime_minutes", "الإضافي", "number", width=10,
                   total=True),
        ]

    def subtitle(self):
        return (f"من {self.options.get('from_date')} "
                f"إلى {self.options.get('to_date')}")

    def rows(self):
        from apps.attendance.models import AttendanceDay
        from django.utils import timezone

        qs = AttendanceDay.objects.filter(
            company=self.company,
            work_date__gte=self.options["from_date"],
            work_date__lte=self.options["to_date"],
        ).select_related("employment__person")

        if self.options.get("employment_id"):
            qs = qs.filter(employment_id=self.options["employment_id"])

        def _t(dt):
            return timezone.localtime(dt).strftime("%H:%M") if dt else ""

        return [
            {
                "employee_no": d.employment.employee_no,
                "name": d.employment.person.display_name,
                "work_date": str(d.work_date),
                "status": d.get_status_display(),
                "first_in": _t(d.first_in),
                "last_out": _t(d.last_out),
                "worked_minutes": d.worked_minutes,
                "late_minutes": d.late_minutes,
                "overtime_minutes": d.approved_overtime_minutes,
            }
            for d in qs.order_by("employment__employee_no", "work_date")
        ]


@register
class OvertimeReport(Report):
    """العمل الإضافي المعتمد — ما يدخل المسير فعلًا."""

    key = "overtime"
    title_ar = "تقرير العمل الإضافي"
    group = "attendance"
    permission = "attendance.view"
    params = [
        Param("from_date", "من", "date", required=True),
        Param("to_date", "إلى", "date", required=True),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("work_date", "التاريخ", "date", width=12),
            Column("computed_minutes", "المحتسب", "number", width=12,
                   total=True),
            Column("approved_minutes", "المعتمد", "number", width=12,
                   total=True),
            Column("approved_hours", "ساعات معتمدة", "number", width=14),
        ]

    def notes(self):
        return ["الإضافي لا يدخل المسير إلا بعد اعتماد صريح"]

    def subtitle(self):
        return (f"من {self.options.get('from_date')} "
                f"إلى {self.options.get('to_date')}")

    def rows(self):
        from apps.attendance.models import AttendanceDay

        qs = AttendanceDay.objects.filter(
            company=self.company,
            work_date__gte=self.options["from_date"],
            work_date__lte=self.options["to_date"],
            overtime_minutes__gt=0,
        ).select_related("employment__person")

        return [
            {
                "employee_no": d.employment.employee_no,
                "name": d.employment.person.display_name,
                "work_date": str(d.work_date),
                "computed_minutes": d.overtime_minutes,
                "approved_minutes": d.approved_overtime_minutes,
                "approved_hours": f"{d.approved_overtime_minutes / 60:.2f}",
            }
            for d in qs.order_by("employment__employee_no", "work_date")
        ]


# ══════════════════ الإجازات ══════════════════

@register
class LeaveBalanceReport(Report):
    """رصيد الإجازات — التزام على الشركة واستفسار متكرر."""

    key = "leave_balance"
    title_ar = "تقرير رصيد الإجازات"
    group = "leaves"
    permission = "leaves.view"
    params = [
        Param("year", "السنة", "text", required=True),
        Param("paid_only", "المدفوعة فقط", "bool", default=True),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("leave_type", "نوع الإجازة", width=20),
            Column("opening", "الرصيد الافتتاحي", "number", width=14,
                   total=True),
            Column("accrued", "المستحق", "number", width=12, total=True),
            Column("consumed", "المستهلك", "number", width=12, total=True),
            Column("adjusted", "التسويات", "number", width=12, total=True),
            Column("available", "المتاح", "number", width=12, total=True),
        ]

    def subtitle(self):
        return f"سنة {self.options.get('year')}"

    def rows(self):
        from apps.leaves.models import LeaveBalance

        qs = LeaveBalance.objects.filter(
            company=self.company, year=int(self.options["year"]),
        ).select_related("employment__person", "leave_type")

        if self.options.get("paid_only", True):
            qs = qs.filter(leave_type__is_paid=True)

        return [
            {
                "employee_no": b.employment.employee_no,
                "name": b.employment.person.display_name,
                "leave_type": b.leave_type.name_ar,
                "opening": str(b.opening_balance),
                "accrued": str(b.accrued),
                "consumed": str(b.consumed),
                "adjusted": str(b.adjusted),
                "available": str(b.available),
            }
            for b in qs.order_by("employment__employee_no",
                                 "leave_type__display_order")
        ]


@register
class LeaveRequestsReport(Report):
    """طلبات الإجازات في فترة."""

    key = "leave_requests"
    title_ar = "تقرير الإجازات"
    group = "leaves"
    permission = "leaves.view"
    params = [
        Param("from_date", "من", "date", required=True),
        Param("to_date", "إلى", "date", required=True),
        Param("status", "الحالة", "select",
              options=[
                  {"value": "", "label": "الكل"},
                  {"value": "approved", "label": "معتمدة"},
                  {"value": "pending", "label": "قيد الاعتماد"},
                  {"value": "rejected", "label": "مرفوضة"},
              ]),
    ]

    def columns(self):
        return [
            Column("request_no", "رقم الطلب", width=18),
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=26),
            Column("leave_type", "نوع الإجازة", width=18),
            Column("start_date", "من", "date", width=12),
            Column("end_date", "إلى", "date", width=12),
            Column("days", "الأيام", "number", width=10, total=True),
            Column("is_paid", "مدفوعة", "bool", width=10),
            Column("status", "الحالة", width=14),
        ]

    def subtitle(self):
        return (f"من {self.options.get('from_date')} "
                f"إلى {self.options.get('to_date')}")

    def rows(self):
        from apps.leaves.models import Request, RequestType

        qs = Request.objects.filter(
            company=self.company, request_type=RequestType.LEAVE,
        ).select_related("employment__person")

        if self.options.get("status"):
            qs = qs.filter(status=self.options["status"])

        rows = []
        frm = str(self.options["from_date"])
        to = str(self.options["to_date"])
        for r in qs.order_by("-created_at"):
            start = r.payload.get("start_date", "")
            end = r.payload.get("end_date", "")
            if not start or start > to or (end and end < frm):
                continue
            rows.append({
                "request_no": r.request_no,
                "employee_no": r.employment.employee_no,
                "name": r.employment.person.display_name,
                "leave_type": r.payload.get("leave_type_name", ""),
                "start_date": start,
                "end_date": end,
                "days": r.payload.get("days", ""),
                "is_paid": "نعم" if r.payload.get("is_paid") else "لا",
                "status": r.get_status_display(),
            })
        return rows


# ══════════════════ الموظفون ══════════════════

@register
class ExpiringDocumentsReport(Report):
    """
    الوثائق والإقامات المنتهية — أهم تقرير استباقي.

    انتهاء إقامة أو رخصة عمل يوقف الموظف ويعرّض الشركة لغرامات.
    """

    key = "expiring_documents"
    title_ar = "تقرير الوثائق والإقامات المنتهية"
    group = "employees"
    permission = "employees.view"
    params = [
        Param("within_days", "خلال (أيام)", "text", default="60"),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("document_type", "نوع الوثيقة", width=18),
            Column("document_number", "الرقم", width=18),
            Column("expiry_date", "تاريخ الانتهاء", "date", width=14),
            Column("days_remaining", "الأيام المتبقية", "number", width=14),
            Column("severity", "الأولوية", width=12),
        ]

    def subtitle(self):
        return f"خلال {self.options.get('within_days', 60)} يومًا"

    def rows(self):
        from apps.employees.services.assets import expiring_documents
        try:
            within = int(self.options.get("within_days") or 60)
        except (TypeError, ValueError):
            within = 60
        return [
            {k: v for k, v in row.items() if k != "document_id"}
            for row in expiring_documents(self.company, within_days=within)
        ]


@register
class AssetsReport(Report):
    """العهد — ما بذمة الموظفين وقيمته."""

    key = "assets"
    title_ar = "تقرير العهد"
    group = "employees"
    permission = "employees.view"
    params = [
        Param("status", "الحالة", "select",
              options=[
                  {"value": "assigned", "label": "بعهدة الموظف"},
                  {"value": "", "label": "الكل"},
                  {"value": "returned", "label": "مُرجَعة"},
                  {"value": "lost", "label": "مفقودة"},
              ], default="assigned"),
    ]

    def columns(self):
        return [
            Column("asset_no", "رقم العهدة", width=16),
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=26),
            Column("asset_name", "الوصف", width=24),
            Column("category", "التصنيف", width=12),
            Column("serial_number", "الرقم التسلسلي", width=18),
            Column("value", "القيمة", "money", width=14, total=True),
            Column("assigned_date", "تاريخ التسليم", "date", width=14),
            Column("status", "الحالة", width=14),
        ]

    def notes(self):
        return ["قيمة ما لم يُرجَع تُخصم من مستحقات نهاية الخدمة (ق-41)"]

    def rows(self):
        from apps.employees.models_assets import Asset

        qs = Asset.objects.filter(
            company=self.company).select_related("employment__person")
        if self.options.get("status"):
            qs = qs.filter(status=self.options["status"])

        return [
            {
                "asset_no": a.asset_no,
                "employee_no": a.employment.employee_no,
                "name": a.employment.person.display_name,
                "asset_name": a.name_ar,
                "category": a.get_category_display(),
                "serial_number": a.serial_number,
                "value": str(a.value),
                "assigned_date": str(a.assigned_date),
                "status": a.get_status_display(),
            }
            for a in qs.order_by("employment__employee_no", "asset_no")
        ]


@register
class EmployeesReport(Report):
    """قائمة الموظفين وحالة تسجيلهم النظامي (ق-15)."""

    key = "employees"
    title_ar = "تقرير الموظفين"
    group = "employees"
    permission = "employees.view"
    params = [
        Param("status", "الحالة", "select",
              options=[
                  {"value": "active", "label": "على رأس العمل"},
                  {"value": "", "label": "الكل"},
                  {"value": "terminated", "label": "منتهية خدمتهم"},
              ], default="active"),
    ]

    def columns(self):
        return [
            Column("employee_no", "الرقم الوظيفي", width=12),
            Column("name", "الموظف", width=28),
            Column("id_number", "رقم الهوية", width=14),
            Column("nationality", "الجنسية", width=10),
            Column("department", "القسم", width=18),
            Column("job_title", "المسمى الوظيفي", width=20),
            Column("join_date", "المباشرة", "date", width=12),
            Column("gosi", "التأمينات", "bool", width=10),
            Column("mol", "قوى", "bool", width=8),
            Column("wps", "حماية الأجور", "bool", width=12),
            Column("status", "الحالة", width=14),
        ]

    def notes(self):
        return ["نطاقات تحتسب المسجّلين في قوى فقط (ق-15)"]

    def rows(self):
        from apps.employees.models import Employment

        qs = Employment.objects.filter(
            company=self.company).select_related(
            "person", "department", "job_title")
        if self.options.get("status"):
            qs = qs.filter(status=self.options["status"])

        return [
            {
                "employee_no": e.employee_no,
                "name": e.person.display_name,
                "id_number": e.person.id_number,
                "nationality": e.person.nationality_code,
                "department": e.department.name_ar if e.department else "",
                "job_title": e.job_title.name_ar if e.job_title else "",
                "join_date": str(e.join_date),
                "gosi": "نعم" if e.is_gosi_registered else "لا",
                "mol": "نعم" if e.is_mol_registered else "لا",
                "wps": "نعم" if e.include_in_wps else "لا",
                "status": e.get_status_display(),
            }
            for e in qs.order_by("employee_no")
        ]
