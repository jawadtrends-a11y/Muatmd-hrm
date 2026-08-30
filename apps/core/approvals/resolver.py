"""
محدِّد المعتمِدين — الواجهة الوحيدة التي تسألها الموديولات.

بُنيت صوريًا في السبرنت الثالث (ق-18) بشرط: ممنوع على أي موديول
أن يفحص صلاحية الاعتماد مباشرة، والكل ينادي resolve_approvers.

والشرط أثمر: بناء المحرك الفعلي في السبرنت العاشر كان تغييرًا
في هذا الملف وحده — لا إعادة كتابة لأي موديول.

التنفيذ الآن في apps/leaves/services/approvals.py
"""
from apps.leaves.services.approvals import (  # noqa: F401
    Approver,
    ApprovalError,
    decide,
    is_approval_engine_ready,
    pending_for,
    resolve_approvers,
    select_chain,
    submit_request,
)

__all__ = [
    "Approver", "ApprovalError", "decide", "is_approval_engine_ready",
    "pending_for", "resolve_approvers", "select_chain", "submit_request",
]
