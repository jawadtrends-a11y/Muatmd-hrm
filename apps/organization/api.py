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
            {"id": b.id, "code": b.code, "name_ar": b.name_ar,
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
    return Response({"id": b.id, "code": b.code, "name_ar": b.name_ar}, status=201)


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
            {"id": d.id, "code": d.code, "name_ar": d.name_ar,
             "parent_id": d.parent_id, "branch_id": d.branch_id,
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
        )
    except StructureError as e:
        return _err(e)
    return Response({"id": d.id, "code": d.code, "path": d.path,
                     "depth": d.depth}, status=201)


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
            {"id": h.id, "name_ar": h.name_ar, "start_date": h.start_date,
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
            start_date=request.data.get("start_date"),
            end_date=request.data.get("end_date"),
            is_paid=request.data.get("is_paid", True),
        )
    except StructureError as e:
        return _err(e, "holiday_conflict", status.HTTP_409_CONFLICT)
    return Response({"id": h.id, "name_ar": h.name_ar, "days": h.days}, status=201)


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
            {"id": j.id, "name_ar": j.name_ar,
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
    return Response({"id": j.id, "name_ar": j.name_ar}, status=201)
