"""
كتالوج ودجتات الرئيسية (ق-106).

المستخدم يختار ودجتاته — **من المتاح لدوره وحده**: الكتالوج يحرس
بالصلاحية، والاختيار لا يفتح ما لا يملكه. فمن لا يرى الرواتب لا
تظهر له ودجت الرواتب في قائمة الاختيار أصلًا.

والحجم: sm عمود، md عمودان، lg الصف كاملًا.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WidgetSpec:
    key: str
    name_ar: str
    name_en: str
    size: str                 # sm | md | lg
    permission: str | None
    group: str                # الفئة في شاشة الاختيار
    default: bool = False     # يظهر لمن لم يخصّص بعد
    # أدنى نطاق يستحقّها: من نطاقه أضيق لا تُعرض له.
    # فـ«حضور فريقي» لمن نطاقه own تعرض شخصًا واحدًا هو صاحبها —
    # صحيحةٌ عزلًا ومربكةٌ عرضًا.
    min_scope: str = ""       # "" | team | department | company


def _w(key, name_ar, name_en, size, permission, group, default=False,
       min_scope=""):
    return WidgetSpec(key, name_ar, name_en, size, permission, group,
                      default, min_scope)


WIDGETS = [
    # ══ ما يخصّني — لكل موظف ══
    _w("my_leave_balance", "رصيد إجازاتي", "My leave balance",
       "sm", None, "me", True),
    _w("my_requests", "طلباتي القائمة", "My open requests",
       "md", None, "me", True),
    _w("my_attendance", "حضوري هذا الشهر", "My attendance this month",
       "md", None, "me", True),
    _w("my_next_leave", "إجازتي القادمة", "My next leave",
       "sm", None, "me"),
    _w("my_documents", "وثائقي القاربة على الانتهاء", "My expiring documents",
       "sm", None, "me"),
    _w("my_last_payslip", "آخر قسيمة راتب", "My latest payslip",
       "sm", "payslips.view_own", "me"),

    # ══ ما ينتظر قراري — لمن يعتمد ══
    _w("pending_approvals", "بانتظار قراري", "Awaiting my decision",
       "md", "requests.approve", "approvals", True),
    _w("overdue_approvals", "طلبات تأخّر قراري فيها", "Overdue decisions",
       "sm", "requests.approve", "approvals"),
    _w("pending_delegations", "إنابات تنتظر قراري", "Delegations awaiting me",
       "sm", None, "approvals"),

    # ══ فريقي — للمشرف ومدير الإدارة ══
    _w("team_today", "حضور فريقي اليوم", "My team today",
       "md", "attendance.view", "team", True, min_scope="team"),
    _w("team_absent", "غياب فريقي اليوم", "Team absent today",
       "sm", "attendance.view", "team", min_scope="team"),
    _w("team_on_leave", "من فريقي في إجازة", "Team on leave",
       "md", "leaves.view", "team", min_scope="team"),
    _w("team_upcoming_leaves", "إجازات فريقي القادمة", "Upcoming team leaves",
       "md", "leaves.view", "team", min_scope="team"),
    _w("team_late", "تأخّر فريقي هذا الشهر", "Team lateness this month",
       "md", "attendance.view", "team", min_scope="team"),

    # ══ المنشأة — للموارد والمالك والمدير العام ══
    _w("headcount", "عدد الموظفين", "Headcount",
       "sm", "employees.view_all", "company", True, min_scope="company"),
    _w("new_hires", "الموظفون المنضمّون حديثًا", "Recent hires",
       "md", "employees.view_all", "company", True, min_scope="company"),
    _w("attendance_today", "حضور اليوم", "Attendance today",
       "md", "attendance.view_all", "company", True, min_scope="company"),
    _w("expiring_documents", "وثائق قاربت على الانتهاء", "Expiring documents",
       "md", "employees.view_all", "company", True, min_scope="company"),
    _w("expiring_iqama", "إقامات قاربت على الانتهاء", "Expiring residencies",
       "md", "employees.view_all", "company", min_scope="company"),
    _w("headcount_by_dept", "الموظفون حسب الإدارة", "Headcount by department",
       "md", "employees.view_all", "company", min_scope="company"),
    _w("nationalities", "الموظفون حسب الجنسية", "Employees by nationality",
       "md", "employees.view_all", "company", min_scope="company"),
    _w("terminations", "المنتهية خدماتهم هذا الشهر", "Terminations this month",
       "sm", "employees.view_all", "company", min_scope="company"),
    _w("leave_liability", "أرصدة الإجازات المستحقّة", "Leave liability",
       "md", "leaves.view_all", "company", min_scope="company"),
    _w("absence_rate", "معدّل الغياب الشهري", "Monthly absence rate",
       "md", "attendance.view_all", "company", min_scope="company"),
    _w("overtime_summary", "الساعات الإضافية هذا الشهر", "Overtime this month",
       "md", "attendance.view_all", "company", min_scope="company"),

    # ══ المال — لمن يرى الرواتب ══
    _w("payroll_status", "حالة المسير الجاري", "Current payroll status",
       "lg", "payroll.view", "payroll", True),
    _w("payroll_net_trend", "صافي الأجور — ستّة أشهر", "Net pay — six months",
       "lg", "payroll.view", "payroll"),
    _w("payroll_by_dept", "أجور الشهر حسب الإدارة", "Monthly pay by department",
       "md", "payroll.view", "payroll"),
    _w("eosb_liability", "مخصّص نهاية الخدمة", "End-of-service liability",
       "md", "payroll.view", "payroll"),
    _w("advances_outstanding", "السلف القائمة", "Outstanding advances",
       "sm", "payroll.view", "payroll"),
]

WIDGETS_BY_KEY = {w.key: w for w in WIDGETS}

GROUPS = {
    "me": ("ما يخصّني", "About me"),
    "approvals": ("ما ينتظر قراري", "Awaiting my decision"),
    "team": ("فريقي", "My team"),
    "company": ("المنشأة", "Organization"),
    "payroll": ("الرواتب", "Payroll"),
}


SCOPE_RANK = {"own": 0, "team": 1, "department": 2,
              "branch": 3, "company": 4, "account": 5}


def allowed_widgets(perms, scopes=None):
    """
    ودجتات هذا المستخدم — الصلاحية تحرس، والنطاق يحرس معها.

    فالموظف قد يملك attendance.view بنطاق own: يرى حضوره هو،
    و«حضور فريقي» تعرض له نفسه فقط — صحيحةٌ ومربكة.
    """
    scopes = scopes or {}
    out = []
    for w in WIDGETS:
        if w.permission is not None and w.permission not in perms:
            continue
        if w.min_scope:
            have = SCOPE_RANK.get(scopes.get(w.permission, "own"), 0)
            if have < SCOPE_RANK.get(w.min_scope, 0):
                continue
        out.append(w)
    return out


def default_keys(perms, scopes=None):
    """ما يظهر لمن لم يخصّص بعد."""
    return [w.key for w in allowed_widgets(perms, scopes) if w.default]
