"""
API الموظفين: الأشخاص، الارتباطات، وهياكل الرواتب.

قاعدة العزل المالي (ق-3): بيانات الشخص المشتركة تُقرأ على مستوى
الحساب، لكن كل ما هو مالي معلّق بالارتباط — فمديرة الموارد في شركة
لا ترى راتبه في شركة أخرى إطلاقًا.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.employees.models import Employment, Person, SalaryStructure
from apps.employees.services.hiring import (
    DuplicatePersonError, HiringError, create_employment, create_person,
    current_salary_structure, set_salary_structure,
)

# الحقول المشتركة للشخص — كل ما عداها يُقرأ من ارتباط الشركة النشطة
PERSON_SHARED_FIELDS = (
    "first_name_ar", "father_name_ar", "grandfather_name_ar",
    "family_name_ar", "full_name_en", "gender", "birth_date",
    "nationality_code", "id_type", "id_number", "id_expiry_date",
    "preferred_locale",
)


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _dec(v, field):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValueError(f"قيمة غير صالحة في {field}: {v}")


def _employment_brief(e):
    return {
        "id": e.id, "employee_no": e.employee_no,
        "person_id": e.person_id,
        "name_ar": e.person.display_name,
        "job_title": e.job_title.name_ar if e.job_title else None,
        "department": e.department.name_ar if e.department else None,
        "status": e.status, "join_date": e.join_date,
        "is_gosi_registered": e.is_gosi_registered,
        "is_mol_registered": e.is_mol_registered,
        "include_in_wps": e.include_in_wps,
        "counts_in_nitaqat": e.counts_in_nitaqat,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def employees(request):
    """قائمة الموظفين وإضافتهم."""
    company_id = _company_id(request)
    if company_id is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = Gate.filter_queryset(request.user, "employees.view",
                                  Employment.objects.all())
        qs = qs.filter(company_id=company_id).select_related(
            "person", "job_title", "department")
        if request.GET.get("status"):
            qs = qs.filter(status=request.GET["status"])
        if request.GET.get("q"):
            q = request.GET["q"]
            qs = qs.filter(person__family_name_ar__icontains=q)
        return Response([_employment_brief(e) for e in qs])

    Gate.require(request.user, "employees.create")
    from apps.accounts.models import Company
    comp = Gate.filter_queryset(
        request.user, "company.view", Company.objects.all()
    ).filter(id=company_id).first()
    if comp is None:
        return Response({"detail": "الشركة غير متاحة"}, status=404)

    d = request.data

    # ⚠️ معاملة واحدة تلفّ إنشاء الشخص والارتباط معًا (with atomic).
    # بلاها: create_person تنجح وتُحفظ بمعاملتها الخاصة، ثم
    # create_employment تفشل — فيبقى شخص يتيم يمنع إعادة المحاولة
    # بنفس الهوية أو الجوال. حدث فعلًا عند أول تجربة إدخال.
    from django.db import transaction as _tx
    try:
      with _tx.atomic():
        person_id = d.get("person_id")
        if person_id:
            # شخص موجود — ارتباط إضافي بشركة أخرى (ق-4)
            pqs = Gate.filter_queryset(request.user, "employees.view",
                                       Person.objects.all())
            person = pqs.filter(id=person_id).first()
            if person is None:
                return Response({"detail": "الشخص غير موجود"}, status=404)
            warnings = []
        else:
            person, warnings = create_person(
                account=comp.account,
                first_name_ar=d.get("first_name_ar", ""),
                father_name_ar=d.get("father_name_ar", ""),
                grandfather_name_ar=d.get("grandfather_name_ar", ""),
                family_name_ar=d.get("family_name_ar", ""),
                full_name_en=d.get("full_name_en", ""),
                gender=d.get("gender", ""),
                nationality_code=d.get("nationality_code", ""),
                id_type=d.get("id_type", ""),
                id_number=d.get("id_number", ""),
                mobile=d.get("mobile", ""),
                email=d.get("email", ""),
                gosi_scheme_code=d.get("gosi_scheme_code") or None,
                force=bool(d.get("force")),
            )

        lines = []
        for item in d.get("salary_lines", []):
            from apps.payroll.models import PayComponent
            comp_qs = Gate.filter_queryset(
                request.user, "employees.create", PayComponent.objects.all())
            pc = comp_qs.filter(company_id=company_id,
                                code=item.get("code", "")).first()
            if pc is None:
                return Response(
                    {"detail": f"مكوّن غير موجود: {item.get('code')}"},
                    status=400)
            lines.append((pc, _dec(item.get("amount", 0), "amount")))

        emp, structure, w2 = create_employment(
            person=person, company=comp,
            employee_no=d.get("employee_no", ""),
            join_date=date.fromisoformat(d["join_date"]),
            service_start_date=(date.fromisoformat(d["service_start_date"])
                                if d.get("service_start_date") else None),
            salary_lines=lines or None,
            iban=d.get("iban", ""),
            probation_days=int(d.get("probation_days", 90)),
        )
    except DuplicatePersonError as e:
        # الرسائل المفصّلة لا كلمة «مكرر» وحدها — العميل يحتاج
        # معرفة أي حقل تكرر ليصححه
        return Response({
            "detail": " · ".join(e.blocking) or "شخص مكرر",
            "code": "duplicate_person",
            "blocking": e.blocking,
        }, status=status.HTTP_409_CONFLICT)
    except HiringError as e:
        return Response({"detail": str(e), "code": "hiring_error"}, status=400)
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات ناقصة أو غير صالحة: {e}"},
                        status=400)

    return Response({
        "employment_id": emp.id, "person_id": person.id,
        "employee_no": emp.employee_no,
        "structure_id": structure.id if structure else None,
        "warnings": warnings + w2,
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_detail(request, employment_id):
    """
    ملف الموظف — بيانات الشخص المشتركة + ارتباط الشركة النشطة فقط.

    ارتباطاته الأخرى تُعرض بلا أي بيان مالي، ولمن يملك صلاحية
    persons.view_cross_company فقط (ق-3).
    """
    Gate.require(request.user, "employees.view")
    company_id = _company_id(request)
    qs = Gate.filter_queryset(request.user, "employees.view",
                              Employment.objects.all())
    emp = qs.filter(id=employment_id,
                    company_id=company_id).select_related("person").first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    p = emp.person
    payload = {
        "person": {f: getattr(p, f) for f in PERSON_SHARED_FIELDS},
        "employment": {
            **_employment_brief(emp),
            "service_start_date": emp.effective_service_start,
            "contract_type": emp.contract_type,
            "probation_end_date": emp.probation_end_date,
            "work_ratio": str(emp.work_ratio),
            "employment_type": emp.employment_type,
            "iban": emp.iban,
            "gosi_declared_wage": (str(emp.gosi_declared_wage)
                                   if emp.gosi_declared_wage else None),
            "gosi_borne_by_company": emp.gosi_borne_by_company,
        },
        "other_employments": None,
    }
    payload["person"]["display_name"] = p.display_name
    payload["person"]["gosi_scheme_code"] = p.gosi_scheme_code

    if Gate.check(request.user, "persons.view_cross_company").allowed:
        others = p.employments.exclude(id=emp.id).select_related("company")
        payload["other_employments"] = [
            {"company_name": o.company.legal_name_ar,
             "employee_no": o.employee_no, "status": o.status}
            for o in others
        ]
        payload["note"] = ("الارتباطات الأخرى تُعرض بلا أي بيان مالي — "
                           "الرواتب لا تُشارك عبر الشركات إطلاقًا")
    return Response(payload)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def salary_structures(request, employment_id):
    """هياكل الرواتب — تاريخية، لا تعديل في المكان."""
    company_id = _company_id(request)
    perm = ("payroll.view" if request.method == "GET"
            else "payroll.structures")
    Gate.require(request.user, perm)

    eqs = Gate.filter_queryset(request.user, perm, Employment.objects.all())
    emp = eqs.filter(id=employment_id, company_id=company_id).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    if request.method == "GET":
        sqs = Gate.filter_queryset(request.user, perm,
                                   SalaryStructure.objects.all())
        return Response([
            {
                "id": s.id, "effective_from": s.effective_from,
                "effective_to": s.effective_to, "reason": s.reason,
                "gross_monthly": str(s.gross_monthly),
                "lines": [{"code": l.component.code,
                           "name_ar": l.component.name_ar,
                           "amount": str(l.amount)}
                          for l in s.lines.select_related("component")],
            }
            for s in sqs.filter(employment=emp).prefetch_related(
                "lines__component")
        ])

    from apps.payroll.models import PayComponent
    lines = []
    cqs = Gate.filter_queryset(request.user, perm, PayComponent.objects.all())
    for item in request.data.get("lines", []):
        pc = cqs.filter(company_id=company_id,
                        code=item.get("code", "")).first()
        if pc is None:
            return Response({"detail": f"مكوّن غير موجود: {item.get('code')}"},
                            status=400)
        try:
            lines.append((pc, _dec(item.get("amount", 0), "amount")))
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

    try:
        s = set_salary_structure(
            employment=emp, lines=lines,
            effective_from=date.fromisoformat(request.data["effective_from"]),
            reason=request.data.get("reason", "adjustment"),
            note=request.data.get("note", ""))
    except HiringError as e:
        return Response({"detail": str(e)}, status=400)
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات غير صالحة: {e}"}, status=400)

    return Response({"id": s.id, "effective_from": s.effective_from,
                     "gross_monthly": str(s.gross_monthly)}, status=201)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def registration_flags(request, employment_id):
    """
    أعلام التسجيل النظامي (ق-15) — التوظيف مستقل عن التسجيل.
    النظام يعكس الواقع ولا يفرض التسجيل.
    """
    Gate.require(request.user, "employees.edit")
    company_id = _company_id(request)
    qs = Gate.filter_queryset(request.user, "employees.edit",
                              Employment.objects.all())
    emp = qs.filter(id=employment_id, company_id=company_id).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    for field in ("is_gosi_registered", "gosi_establishment_no",
                  "gosi_declared_wage", "is_mol_registered",
                  "mol_contract_no", "include_in_wps",
                  "registration_note", "gosi_borne_by_company"):
        if field in request.data:
            setattr(emp, field, request.data[field])
    emp.save()

    return Response({
        "id": emp.id,
        "is_gosi_registered": emp.is_gosi_registered,
        "is_mol_registered": emp.is_mol_registered,
        "include_in_wps": emp.include_in_wps,
        "counts_in_nitaqat": emp.counts_in_nitaqat,
        "gosi_borne_by_company": emp.gosi_borne_by_company,
        "note": ("نطاقات تحتسب المسجّلين في قوى فقط. حقوق نهاية الخدمة "
                 "والإجازات تُحتسب للجميع بغض النظر عن التسجيل."),
    })


# ══════════════════ الملف الشخصي للموظف (ق-54) ══════════════════

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_profile(request):
    """
    ملف الموظف عن نفسه — الشاشة الرئيسية له.

    بياناته وراتبه وخدمته ووثائقه، بلا صلاحيات إدارية.
    """
    from datetime import date

    from apps.employees.models import (
        Employment, EmploymentStatus, SalaryStructure,
    )
    from apps.employees.models_assets import (
        Advance, AdvanceStatus, Asset, AssetStatus, EmployeeDocument,
    )
    from apps.payroll.models_banks import label_for

    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    company_id = _company_id(request)
    emp = Employment.objects.filter(
        person=person, company_id=company_id,
        status=EmploymentStatus.ACTIVE).select_related(
        "person", "department", "branch", "job_title",
        "direct_manager__person").first()

    if emp is None:
        emp = Employment.objects.filter(
            person=person).select_related("person").first()
    if emp is None:
        return Response({"detail": "لا ارتباط وظيفي"}, status=404)

    # مدة الخدمة
    start = emp.service_start_date or emp.join_date
    days = (date.today() - start).days
    years, rem = divmod(days, 365)
    months = rem // 30

    # هيكل الراتب الساري
    structure = SalaryStructure.objects.filter(
        employment=emp, effective_to__isnull=True
    ).prefetch_related("lines__component").first()

    salary_lines = []
    gross = 0
    if structure:
        for line in structure.lines.all():
            salary_lines.append({
                "component": line.component.name_ar,
                "code": line.component.code,
                "amount": str(line.amount),
            })
            gross += float(line.amount)

    # الوثائق القريبة من الانتهاء
    docs = []
    for d in EmployeeDocument.objects.filter(employment=emp):
        if not d.expiry_date:
            continue
        left = (d.expiry_date - date.today()).days
        if left > 90:
            continue
        docs.append({
            "type": d.get_document_type_display(),
            "number": d.document_number,
            "expiry_date": d.expiry_date,
            "days_left": left,
            "severity": ("منتهية" if left < 0
                         else "حرجة" if left <= 14
                         else "قريبة" if left <= 30 else "تنبيه"),
        })
    docs.sort(key=lambda x: x["days_left"])

    # السلف والعهد
    advances = Advance.objects.filter(
        employment=emp, status=AdvanceStatus.ACTIVE)
    outstanding = sum(
        float(a.amount) - float(a.repaid_amount) for a in advances)
    assets = Asset.objects.filter(
        employment=emp, status=AssetStatus.ASSIGNED)

    return Response({
        "employee": {
            "employment_id": emp.id,
            "employee_no": emp.employee_no,
            "name_ar": emp.person.display_name,
            "name_en": emp.person.full_name_en,
            "id_number": emp.person.id_number,
            "id_type": emp.person.get_id_type_display(),
            "nationality": emp.person.nationality_code,
            "mobile": emp.person.mobile_e164,
            "email": emp.person.email,
            "department": emp.department.name_ar if emp.department else "",
            "branch": emp.branch.name_ar if emp.branch else "",
            "job_title": emp.job_title.name_ar if emp.job_title else "",
            "manager": (emp.direct_manager.person.display_name
                        if emp.direct_manager else ""),
            "status": emp.status,
            "status_label": emp.get_status_display(),
        },
        "service": {
            "join_date": emp.join_date,
            "service_start_date": start,
            "years": years,
            "months": months,
            "days_total": days,
            "in_probation": (
                emp.probation_end_date is not None
                and emp.probation_end_date >= date.today()),
            "probation_end": emp.probation_end_date,
        },
        "salary": {
            "gross": f"{gross:.2f}",
            "lines": salary_lines,
            "iban": emp.iban,
            "bank": label_for(emp.iban),
        },
        "registration": {
            "gosi": emp.is_gosi_registered,
            "mol": emp.is_mol_registered,
            "wps": emp.include_in_wps,
        },
        "documents": docs,
        "obligations": {
            "advances_outstanding": f"{outstanding:.2f}",
            "advances_count": advances.count(),
            "assets_count": assets.count(),
            "assets_value": f"{sum(float(a.value) for a in assets):.2f}",
        },
    })
