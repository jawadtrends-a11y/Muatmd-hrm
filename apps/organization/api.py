"""
API الهيكل التنظيمي.

كل نقطة تمر بالبوابات الثلاث:
  الميزة (الباقة) → الصلاحية (الدور) → النطاق (RLS + Gate)
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.organization.models import Branch, CostCenter, Department, Holiday, JobTitle
from apps.organization.services.structure import (
    LimitExceeded, StructureError, create_branch, create_department,
    create_holiday, department_tree, move_department,
)


def _company(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _get_company(request, company_id):
    """الشركة عبر البوابة — لا استعلام خام حتى للكائنات المرجعية."""
    from apps.accounts.models import Company
    qs = Gate.filter_queryset(request.user, "company.view", Company.objects.all())
    return qs.filter(id=company_id).first()


def _get_department(request, dept_id, company_id, permission):
    """قسم مرجعي عبر البوابة — يمنع اختيار قسم خارج نطاق المستخدم."""
    qs = Gate.filter_queryset(request.user, permission, Department.objects.all())
    return qs.filter(id=dept_id, company_id=company_id).first()


def _get_branch(request, branch_id, company_id, permission):
    qs = Gate.filter_queryset(request.user, permission, Branch.objects.all())
    return qs.filter(id=branch_id, company_id=company_id).first()


def _err(exc, code="structure_error", http=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": str(exc), "code": code}, status=http)



def _usage(model_name, obj, user):
    """
    كم يستعمل هذا العنصر — والزر الذي يُرفض عند الضغط لا يُعرض.

    والعدّ يمرّ بالبوابة كغيره: من لا يرى موظفًا لا يُحتسب عليه.
    """
    from apps.employees.models import Employment
    from apps.organization.models import Department

    emps = Gate.filter_queryset(user, "employees.view",
                                Employment.objects.all())
    depts = Gate.filter_queryset(user, "org.view",
                                 Department.objects.all())

    if model_name == "branch":
        return (emps.filter(branch=obj, status="active").count(),
                depts.filter(branch=obj, is_active=True).count())

    if model_name == "department":
        return (emps.filter(department=obj, status="active").count(),
                depts.filter(parent=obj, is_active=True).count())

    if model_name == "job_title":
        return emps.filter(job_title=obj, status="active").count(), 0

    # ق-156: مركز التكلفة — ويُعدّ كغيره بالبوّابة
    if model_name == "cost_center":
        return emps.filter(cost_center=obj, status="active").count(), 0

    return 0, 0


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def branches(request):
    company_id = _company(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "org.view")
        qs = Gate.filter_queryset(request.user, "org.view", Branch.objects.all())
        return Response([
            {"id": b.id, "code": b.code, "name_ar": b.name_ar, "can_delete": _usage("branch", b, request.user)[0] == 0 and _usage("branch", b, request.user)[1] == 0, "name_en": getattr(b, "name_en", ""),
             "city": b.city, "is_active": b.is_active,
             "mol_establishment_no": b.mol_establishment_no,
             "gosi_establishment_no": b.gosi_establishment_no}
            for b in qs.filter(company_id=company_id)
        ])

    Gate.require(request.user, "org.manage")
    comp = _get_company(request, company_id)
    try:
        b = create_branch(
            company=comp,
            code=request.data.get("code", ""),
            name_ar=request.data.get("name_ar", ""),
            # ق-92: الاسمان معًا — والواجهة تعرض بلغة المستخدم
            name_en=request.data.get("name_en", ""),
            city=request.data.get("city", ""),
            mol_establishment_no=request.data.get("mol_establishment_no", ""),
            gosi_establishment_no=request.data.get("gosi_establishment_no", ""),
        )
    except LimitExceeded as e:
        # 402 لا 403 — حد الباقة رسالة ترقية لا رفض صلاحية
        return Response(
            {"detail": str(e), "code": "plan_limit_exceeded",
             "feature": e.feature_key, "limit": e.limit,
             "upgrade_url": "/settings/subscription"},
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )
    except StructureError as e:
        return _err(e)
    return Response({"id": b.id, "code": b.code, "name_ar": b.name_ar, "name_en": getattr(b, "name_en", "")}, status=201)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def departments(request):
    company_id = _company(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "org.view")
        qs = Gate.filter_queryset(request.user, "org.view", Department.objects.all())
        return Response([
            {"id": d.id, "code": d.code, "name_ar": d.name_ar, "can_delete": _usage("department", d, request.user)[0] == 0 and _usage("department", d, request.user)[1] == 0, "name_en": getattr(d, "name_en", ""),
             "parent_id": d.parent_id, "branch_id": d.branch_id,
             # ق-156: **مدير الإدارة** — الحقل كان مبنيًّا ومعطَّلًا
             "manager_employment_id": d.manager_employment_id,
             "manager_name": _manager_name(d),
             "path": d.path, "depth": d.depth, "is_active": d.is_active}
            for d in qs.filter(company_id=company_id)
        ])

    Gate.require(request.user, "org.manage")
    comp = _get_company(request, company_id)
    parent = None
    if request.data.get("parent_id"):
        parent = _get_department(
            request, request.data["parent_id"], company_id, "org.manage")
        if parent is None:
            return _err("القسم الأعلى غير موجود", "parent_not_found", 404)
    try:
        d = create_department(
            company=comp, code=request.data.get("code", ""),
            name_ar=request.data.get("name_ar", ""), parent=parent,
            # ق-92: الاسمان معًا — والواجهة تعرض بلغة المستخدم
            name_en=request.data.get("name_en", ""),
        )
    except StructureError as e:
        return _err(e)

    # ق-156: **ويُسنَد المدير عند الإنشاء** — فإدارةٌ بلا مديرٍ
    # معلَن تُبقي سلسلة الاعتماد بلا مرجع.
    mgr_id = request.data.get("manager_employment_id")
    if mgr_id:
        ok, err = _set_manager(request, d, mgr_id, company_id)
        if not ok:
            return _err(err, "manager_not_found", 404)

    return Response({"id": d.id, "code": d.code, "path": d.path,
                     "depth": d.depth,
                     "manager_employment_id": d.manager_employment_id},
                    status=201)


def _manager_name(dept):
    """اسم مدير الإدارة — أو فراغٌ إن لم يُسنَد."""
    from apps.employees.models import Employment

    if not dept.manager_employment_id:
        return ""
    e = (Employment.objects
         .filter(id=dept.manager_employment_id)
         .select_related("person").first())
    return e.person.display_name if e else ""


def _set_manager(request, dept, mgr_id, company_id):
    """
    يُسند مدير الإدارة.

    ⚠️ **ولا يُسنَد من شركةٍ أخرى**: فمديرٌ خارج الشركة يكسر
    سلسلة الاعتماد ويطّلع على ما ليس له.
    """
    from apps.employees.models import Employment, EmploymentStatus

    if not mgr_id:
        dept.manager_employment_id = None
        dept.save(update_fields=["manager_employment_id"])
        return True, ""

    # ⚠️ **وعبر البوّابة لا خامًا**: فمن لا يرى الموظف لا يُسنده
    # مديرًا — والنطاق يُحترم هنا كما في كل قراءة.
    e = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=mgr_id, company_id=company_id,
             status=EmploymentStatus.ACTIVE).first()
    if e is None:
        return False, "المدير غير موجود في هذه الشركة أو غير نشط"

    dept.manager_employment_id = e.id
    dept.save(update_fields=["manager_employment_id"])
    return True, ""


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def department_tree_view(request):
    """الشجرة كاملة — استعلام واحد."""
    Gate.require(request.user, "org.view")
    company_id = _company(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)
    comp = _get_company(request, company_id)
    return Response(department_tree(comp))


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def department_move(request, dept_id):
    Gate.require(request.user, "org.manage")
    company_id = _company(request)
    qs = Gate.filter_queryset(request.user, "org.manage", Department.objects.all())
    dept = qs.filter(id=dept_id, company_id=company_id).first()
    if dept is None:
        return _err("القسم غير موجود", "not_found", 404)

    new_parent = None
    if request.data.get("parent_id"):
        new_parent = _get_department(
            request, request.data["parent_id"], company_id, "org.manage")
        if new_parent is None:
            return _err("القسم الأعلى غير موجود", "parent_not_found", 404)
    try:
        move_department(department=dept, new_parent=new_parent)
    except StructureError as e:
        return _err(e, "invalid_move")
    dept.refresh_from_db()
    return Response({"id": dept.id, "path": dept.path, "depth": dept.depth})


def _holiday_end(data):
    """
    تاريخ النهاية — من end_date إن أُرسل، وإلا من days.

    والخلط بينهما كان يمرّر None فتنكسر المقارنة بـ500: الشاشة
    ترسل days والمسار ينتظر end_date.
    """
    from datetime import date, timedelta

    end = (data.get("end_date") or "").strip() if isinstance(
        data.get("end_date"), str) else data.get("end_date")
    if end:
        return end

    start = data.get("start_date")
    if not start:
        return None
    try:
        d = date.fromisoformat(str(start))
        n = int(data.get("days") or 1)
    except (TypeError, ValueError):
        return start
    n = max(1, n)
    return (d + timedelta(days=n - 1)).isoformat()


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def holidays(request):
    """العطل — تديرها الشركة بالكامل."""
    company_id = _company(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "org.view")
        qs = Gate.filter_queryset(request.user, "org.view", Holiday.objects.all())
        return Response([
            {"id": h.id, "name_ar": h.name_ar, "name_en": getattr(h, "name_en", ""), "start_date": h.start_date,
             "end_date": h.end_date, "days": h.days, "is_paid": h.is_paid,
             "branch_id": h.branch_id}
            for h in qs.filter(company_id=company_id)
        ])

    Gate.require(request.user, "org.manage")
    comp = _get_company(request, company_id)
    branch = None
    if request.data.get("branch_id"):
        branch = _get_branch(
            request, request.data["branch_id"], company_id, "org.manage")
    try:
        h = create_holiday(
            company=comp, branch=branch,
            name_ar=request.data.get("name_ar", ""),
            # ق-92: الاسمان معًا — والواجهة تعرض بلغة المستخدم
            name_en=request.data.get("name_en", ""),
            start_date=request.data.get("start_date"),
            # الشاشة تسأل عن «عدد الأيام» لا تاريخ نهاية: أيسر على
            # المستخدم. ويُقبل end_date صريحًا لمن يرسله.
            end_date=_holiday_end(request.data),
            is_paid=request.data.get("is_paid", True),
        )
    except StructureError as e:
        return _err(e, "holiday_conflict", status.HTTP_409_CONFLICT)
    return Response({"id": h.id, "name_ar": h.name_ar, "name_en": getattr(h, "name_en", ""), "days": h.days}, status=201)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def job_titles(request):
    company_id = _company(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "org.view")
        qs = Gate.filter_queryset(request.user, "org.view", JobTitle.objects.all())
        return Response([
            {"id": j.id, "name_ar": j.name_ar, "can_delete": _usage("job_title", j, request.user)[0] == 0 and _usage("job_title", j, request.user)[1] == 0, "name_en": getattr(j, "name_en", ""),
             "mol_occupation_code": j.mol_occupation_code,
             "is_saudization_reserved": j.is_saudization_reserved}
            for j in qs.filter(company_id=company_id)
        ])

    Gate.require(request.user, "org.manage")
    comp = _get_company(request, company_id)
    j = JobTitle.objects.create(
        account=comp.account, company=comp,
        name_ar=request.data.get("name_ar", ""),
        name_en=request.data.get("name_en", ""),
        mol_occupation_code=request.data.get("mol_occupation_code", ""),
        is_saudization_reserved=request.data.get("is_saudization_reserved", False),
    )
    return Response({"id": j.id, "name_ar": j.name_ar, "name_en": getattr(j, "name_en", "")}, status=201)


# ══════════ التعديل والحذف (ق-93) ══════════

def _org_detail(request, model, obj_id, used_by=None, guard=None):
    """
    تعديل كيان تنظيمي أو حذفه.

    والحذف مشروط: ما يستعمله موظف يُعطَّل ولا يُحذف — والرسالة
    تخبر بما يُفعل (انقل الموظفين أو أنهِ عقودهم) لا بما وقع.
    """
    obj = model.objects.filter(
        id=obj_id, company_id=_company(request)).first()
    if obj is None:
        return Response({"detail": "غير موجود"}, status=404)

    if request.method == "DELETE":
        if guard:
            blocked = guard(obj)
            if blocked:
                return Response({"detail": blocked,
                                 "code": "has_children"}, status=409)

        count = used_by(obj) if used_by else 0
        if count and hasattr(obj, "is_active"):
            obj.is_active = False
            obj.save(update_fields=["is_active"])
            return Response({
                "deactivated": True,
                "detail": f"مستعمل لدى {count} موظفًا — عُطّل ولم "
                          f"يُحذف. انقلهم أو أنهِ عقودهم ثم احذفه.",
            })

        obj.delete()
        return Response({"deleted": True})

    for f in ("name_ar", "name_en", "code", "city",
              "mol_establishment_no", "gosi_establishment_no",
              "mol_occupation_code"):
        if f in request.data and hasattr(obj, f):
            setattr(obj, f, request.data[f] or "")

    # التواريخ تُعدَّل أيضًا — بدونها تُنشأ العطلة ولا يُصحَّح
    # تاريخها أبدًا، والتعديل ينجح ظاهرًا ولا يغيّر شيئًا.
    from datetime import date as _date
    for f in ("start_date", "end_date"):
        if f in request.data and hasattr(obj, f) and request.data[f]:
            setattr(obj, f, _date.fromisoformat(str(request.data[f])[:10]))
    if "is_paid" in request.data and hasattr(obj, "is_paid"):
        obj.is_paid = bool(request.data["is_paid"])
    if (hasattr(obj, "start_date") and hasattr(obj, "end_date")
            and obj.end_date < obj.start_date):
        return Response({"detail": "تاريخ النهاية قبل تاريخ البداية"},
                        status=400)

    # is_active ليس في كل كيان — العطلة تُحذف ولا تُعطَّل
    if "is_active" in request.data and hasattr(obj, "is_active"):
        obj.is_active = bool(request.data["is_active"])
    obj.save()

    out = {
        "id": obj.id,
        "name_ar": obj.name_ar,
        "name_en": getattr(obj, "name_en", ""),
        "is_active": getattr(obj, "is_active", True),
    }
    if hasattr(obj, "start_date"):
        out["start_date"] = str(obj.start_date)
        out["end_date"] = str(obj.end_date)
        out["days"] = obj.days
    return Response(out)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def branch_detail(request, branch_id):
    """تعديل فرع أو حذفه."""
    from apps.employees.models import Employment
    from apps.organization.models import Branch, Department

    Gate.require(request.user, "org.manage")

    def guard(b):
        n = _usage("branch", b, request.user)[1]
        if n:
            return f"فيه {n} إدارة — انقلها أو احذفها أولًا"
        return ""

    return _org_detail(
        request, Branch, branch_id,
        used_by=lambda b: _usage("branch", b, request.user)[0],
        guard=guard)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def department_detail(request, dept_id):
    """تعديل إدارة أو حذفها."""
    from apps.employees.models import Employment
    from apps.organization.models import Department

    Gate.require(request.user, "org.manage")

    # ق-156: **ويُسنَد المدير أو يُنزع** قبل بقيّة التعديل.
    #
    # ⚠️ فالحقل كان مبنيًّا في النموذج ولا يصله شيء — **إدارةٌ بلا
    # مديرٍ معلَن** رغم أن مكانه محجوز.
    if request.method == "PUT" and "manager_employment_id" in request.data:
        company_id = _company(request)
        dept = Gate.filter_queryset(
            request.user, "org.manage", Department.objects.all()
        ).filter(id=dept_id, company_id=company_id).first()
        if dept is None:
            return _err("الإدارة غير موجودة", "not_found", 404)
        ok, err = _set_manager(
            request, dept, request.data["manager_employment_id"],
            company_id)
        if not ok:
            return _err(err, "manager_not_found", 404)

    def guard(d):
        n = _usage("department", d, request.user)[1]
        if n:
            return f"تحتها {n} إدارة فرعية — انقلها أولًا"
        return ""

    return _org_detail(
        request, Department, dept_id,
        used_by=lambda d: _usage("department", d,
                                 request.user)[0],
        guard=guard)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def job_title_detail(request, title_id):
    """تعديل مسمّى وظيفي أو حذفه."""
    from apps.employees.models import Employment
    from apps.organization.models import JobTitle

    Gate.require(request.user, "org.manage")

    return _org_detail(
        request, JobTitle, title_id,
        used_by=lambda j: _usage("job_title", j,
                                 request.user)[0])


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def holiday_detail(request, holiday_id):
    """تعديل إجازة رسمية أو حذفها — ولا تُستعمل في عقد فتُحذف."""
    from apps.organization.models import Holiday

    Gate.require(request.user, "org.manage")
    return _org_detail(request, Holiday, holiday_id)


# ══════════ مراكز التكلفة (ق-156) ══════════
#
# ⚠️ **النموذج كان مبنيًّا بلا مسار**: والواجهة تناديه فيردّ ٤٠٤
# في كل فتح لملفّ موظف (بلاغ جواد).

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def cost_centers(request):
    """مراكز التكلفة — عرضًا وإنشاءً."""
    from apps.organization.models import CostCenter

    company_id = _company(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "org.view")
        qs = CostCenter.objects.filter(company_id=company_id)
        if request.GET.get("active") != "0":
            qs = qs.filter(is_active=True)
        return Response([
            {"id": c.id, "code": c.code, "name_ar": c.name_ar,
             "name_en": getattr(c, "name_en", ""),
             "is_active": c.is_active}
            for c in qs
        ])

    Gate.require(request.user, "org.manage")
    comp = _get_company(request, company_id)

    code = str(request.data.get("code") or "").strip().upper()
    name = str(request.data.get("name_ar") or "").strip()
    if not code or not name:
        return _err("الرمز والاسم مطلوبان", "missing", 400)
    if CostCenter.objects.filter(company=comp, code=code).exists():
        return _err("الرمز مستعمل", "duplicate", 409)

    c = CostCenter.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=name, name_en=request.data.get("name_en", ""))
    return Response({"id": c.id, "code": c.code}, status=201)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def cost_center_detail(request, center_id):
    """
    تعديل مركز تكلفة أو حذفه.

    ⚠️ **والمستعمل يُعطَّل ولا يُحذف**: فموظفون وقيودٌ تشير إليه.
    """
    from apps.employees.models import Employment
    from apps.organization.models import CostCenter

    Gate.require(request.user, "org.manage")

    c = CostCenter.objects.filter(
        id=center_id, company_id=_company(request)).first()
    if c is None:
        return _err("غير موجود", "not_found", 404)

    if request.method == "DELETE":
        used = _usage("cost_center", c, request.user)[0]
        if used:
            c.is_active = False
            c.save(update_fields=["is_active"])
            return Response({
                "deactivated": True,
                "detail": f"مستعملٌ لـ{used} موظفًا — عُطّل ولم يُحذف"})
        c.delete()
        return Response({"deleted": True})

    for f in ("name_ar", "name_en"):
        if f in request.data:
            setattr(c, f, str(request.data[f] or "").strip())
    if "is_active" in request.data:
        c.is_active = bool(request.data["is_active"])
    c.save()
    return Response({"id": c.id, "code": c.code})
