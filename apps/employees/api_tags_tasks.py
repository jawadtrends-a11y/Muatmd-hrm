"""
مسارات الدليل والوسوم والمهام (ق-131).
"""
from datetime import date

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.employees.models import (
    EmployeeTag, EmployeeTagAssignment, Employment, EmploymentStatus,
    Task, TaskPriority, TaskStatus)


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _me(request):
    person = getattr(request.user, "person", None)
    if person is None:
        return None
    return Employment.objects.filter(
        person=person, company_id=_company_id(request),
        status=EmploymentStatus.ACTIVE).first()


# ══════════ دليل الموظفين ══════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def directory(request):
    """
    دليل الزملاء — للبحث عمّن يتواصل معه.

    ⚠️ **بلا بيانات حسّاسة**: لا راتب ولا هوية ولا عنوان — فالدليل
    يفتحه كل موظف، ومن أراد الملفّ يذهب إليه بصلاحيته.
    """
    Features.require(_company_id(request), "employee_directory")

    # ⚠️ ولا يمرّ بنطاق «الموظفين»: الدليل كلّه معروضٌ لكل موظف —
    # وإلا صار من نطاقه نفسه يرى نفسه فقط في دليل الزملاء.
    qs = (Employment.objects
          .filter(company_id=_company_id(request),
                  status=EmploymentStatus.ACTIVE)
          .select_related("person", "department", "job_title", "branch"))

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(person__first_name_ar__icontains=q)
            | Q(person__family_name_ar__icontains=q)
            | Q(employee_no__icontains=q)
            | Q(job_title__name_ar__icontains=q)
            | Q(department__name_ar__icontains=q))

    if request.GET.get("department_id"):
        qs = qs.filter(department_id=request.GET["department_id"])
    if request.GET.get("branch_id"):
        qs = qs.filter(branch_id=request.GET["branch_id"])

    rows = [{
        "employment_id": e.id,
        "employee_no": e.employee_no,
        "name": e.person.display_name,
        "job_title": getattr(e.job_title, "name_ar", "") or "",
        "department": getattr(e.department, "name_ar", "") or "",
        "branch": getattr(e.branch, "name_ar", "") or "",
        "email": e.person.email or "",
        "mobile": e.person.mobile_e164 or "",
    } for e in qs.order_by("person__first_name_ar")[:500]]

    return Response({"rows": rows, "count": len(rows)})


# ══════════ الوسوم ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def tags(request):
    """وسوم الشركة — عرضًا وإضافة."""
    Features.require(_company_id(request), "employee_tags")

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = EmployeeTag.objects.filter(company_id=_company_id(request))
        return Response([{
            "id": t.id, "name_ar": t.name_ar, "color": t.color,
            "description": t.description, "is_active": t.is_active,
            "count": t.assignments.count(),
        } for t in qs])

    Gate.require(request.user, "employees.edit")
    from apps.accounts.models import Company

    # مقيَّد بشركة المنفّذ النشطة
    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    name = str(request.data.get("name_ar") or "").strip()
    if not name:
        return Response({"detail": "اسم الوسم مطلوب"}, status=400)
    if EmployeeTag.objects.filter(company=comp, name_ar=name).exists():
        return Response({"detail": "الوسم موجود"}, status=409)

    t = EmployeeTag.objects.create(
        account=comp.account, company=comp, name_ar=name,
        color=str(request.data.get("color") or ""),
        description=str(request.data.get("description") or "")[:255])
    return Response({"id": t.id, "name_ar": t.name_ar},
                    status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def tag_detail(request, tag_id):
    """حذف وسم — وإسناداته معه."""
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "employee_tags")

    t = EmployeeTag.objects.filter(
        id=tag_id, company_id=_company_id(request)).first()
    if t is None:
        return Response({"detail": "غير موجود"}, status=404)
    t.delete()
    return Response({"deleted": True})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def employee_tags(request, employment_id):
    """إسناد وسمٍ لموظف أو نزعه."""
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "employee_tags")

    emp = Gate.filter_queryset(
        request.user, "employees.edit", Employment.objects.all()
    ).filter(id=employment_id).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    tag = EmployeeTag.objects.filter(
        id=request.data.get("tag_id"),
        company_id=_company_id(request)).first()
    if tag is None:
        return Response({"detail": "الوسم غير موجود"}, status=404)

    if request.method == "DELETE":
        EmployeeTagAssignment.objects.filter(
            tag=tag, employment=emp).delete()
        return Response({"removed": True})

    actor = getattr(request.user, "person", None)
    EmployeeTagAssignment.objects.get_or_create(
        tag=tag, employment=emp,
        defaults={"account_id": emp.account_id,
                  "company_id": emp.company_id,
                  "assigned_by_person_id": actor.id if actor else None})
    return Response({"assigned": True}, status=status.HTTP_201_CREATED)


# ══════════ المهام ══════════

def _task_json(t):
    return {
        "id": t.id, "title": t.title, "description": t.description,
        "assignee_id": t.assignee_id,
        "assignee": t.assignee.person.display_name,
        "assigned_by": (t.assigned_by.person.display_name
                        if t.assigned_by else ""),
        "due_date": t.due_date,
        "priority": t.priority, "priority_label": t.get_priority_display(),
        "status": t.status, "status_label": t.get_status_display(),
        "overdue": bool(t.due_date and t.due_date < date.today()
                        and t.status in (TaskStatus.OPEN,
                                         TaskStatus.IN_PROGRESS)),
        "completed_at": t.completed_at,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def tasks(request):
    """مهامّي أو مهامّ فريقي — وإنشاءٌ جديد."""
    Features.require(_company_id(request), "tasks")

    me = _me(request)
    if me is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    if request.method == "GET":
        scope = request.GET.get("scope") or "mine"
        qs = Task.objects.filter(
            company_id=_company_id(request)
        ).select_related("assignee__person", "assigned_by__person")

        if scope == "assigned":
            # ما أسندتُه لغيري
            qs = qs.filter(assigned_by=me)
        elif scope == "team":
            # ⚠️ فريقي بالبوابة — فمن نطاقه نفسه لا يرى مهامّ غيره
            allowed = Gate.filter_queryset(
                request.user, "employees.view", Employment.objects.all()
            ).values_list("id", flat=True)
            qs = qs.filter(assignee_id__in=allowed)
        else:
            qs = qs.filter(assignee=me)

        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        else:
            qs = qs.exclude(status__in=[TaskStatus.DONE,
                                        TaskStatus.CANCELLED])

        return Response([_task_json(t) for t in qs[:300]])

    d = request.data
    title = str(d.get("title") or "").strip()
    if not title:
        return Response({"detail": "عنوان المهمّة مطلوب"}, status=400)

    # ⚠️ ولا يُسنِد إلا لمن يراه: من نطاقه نفسه يُسنِد لنفسه فقط
    assignee = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=d.get("assignee_id") or me.id).first()
    if assignee is None:
        return Response({"detail": "لا تملك الإسناد لهذا الموظف"},
                        status=403)

    due = None
    if d.get("due_date"):
        try:
            due = date.fromisoformat(str(d["due_date"]))
        except ValueError:
            return Response({"detail": "تاريخ غير صالح"}, status=400)

    t = Task.objects.create(
        account_id=me.account_id, company_id=me.company_id,
        title=title, description=str(d.get("description") or ""),
        assignee=assignee, assigned_by=me, due_date=due,
        priority=d.get("priority") or TaskPriority.NORMAL)
    return Response(_task_json(t), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def task_detail(request, task_id):
    """
    تحديث مهمّة أو إلغاؤها.

    ⚠️ **ولا تُحذف المنجزة**: سجلُّ ما أُنجز يُراجَع، ومحوُه يُخفي
    عمل الموظف — فتُلغى بدل ذلك.
    """
    Features.require(_company_id(request), "tasks")

    me = _me(request)
    t = Task.objects.filter(
        id=task_id, company_id=_company_id(request)).first()
    if t is None or me is None:
        return Response({"detail": "غير موجودة"}, status=404)

    # المسنَد إليه يغيّر الحالة، والمُسنِد يغيّر كل شيء
    is_mine = t.assignee_id == me.id
    is_owner = t.assigned_by_id == me.id
    if not (is_mine or is_owner
            or Gate.check(request.user, "employees.edit").allowed):
        return Response({"detail": "ليست لك"}, status=403)

    if request.method == "DELETE":
        if t.status == TaskStatus.DONE:
            return Response({
                "detail": "منجزة — تُلغى ولا تُحذف",
                "code": "task_done"}, status=409)
        t.status = TaskStatus.CANCELLED
        t.save(update_fields=["status", "updated_at"])
        return Response({"cancelled": True})

    d = request.data
    if "status" in d and d["status"] in TaskStatus.values:
        t.status = d["status"]
        if d["status"] == TaskStatus.DONE:
            t.completed_at = timezone.now()
            t.completion_note = str(d.get("completion_note") or "")[:255]
        else:
            t.completed_at = None

    if is_owner or Gate.check(request.user, "employees.edit").allowed:
        for f in ("title", "description"):
            if f in d:
                setattr(t, f, str(d[f] or ""))
        if d.get("priority") in TaskPriority.values:
            t.priority = d["priority"]
        if "due_date" in d:
            try:
                t.due_date = (date.fromisoformat(str(d["due_date"]))
                              if d["due_date"] else None)
            except ValueError:
                return Response({"detail": "تاريخ غير صالح"}, status=400)
    t.save()
    return Response(_task_json(t))
