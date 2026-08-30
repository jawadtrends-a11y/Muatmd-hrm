"""
سجل التقارير — يُحمَّل تلقائيًا عند الإقلاع.

استيراد الوحدات هنا يضمن تسجيل كل تقرير في REGISTRY.
"""
from apps.core.reports.base import (  # noqa: F401
    Column, GROUPS, Param, Report, ReportError, ReportResult, catalog,
    get_report, register, REGISTRY,
)


def load_reports():
    """يستورد وحدات التقارير فتُسجَّل."""
    from apps.core.reports import financial, operations  # noqa: F401
    return len(REGISTRY)
