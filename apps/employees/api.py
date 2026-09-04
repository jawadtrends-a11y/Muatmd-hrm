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
        # ق-80: الفاعل يُنسب — وتعديل الراتب أخطر تغيير في النظام،
        # فتسجيله مجهولًا يُفرغ سجل العمليات من معناه
        s = set_salary_structure(
            employment=emp, lines=lines,
            effective_from=date.fromisoformat(request.data["effective_from"]),
            reason=request.data.get("reason", "adjustment"),
            note=request.data.get("note", ""),
            approved_by=getattr(request.user, "person", None))
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

    from apps.core.i18n import localized, request_locale
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

    lang = request_locale(request)

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
                "component": localized(line.component, locale=lang),
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
            "department": localized(emp.department, locale=lang),
            "branch": localized(emp.branch, locale=lang),
            "job_title": localized(emp.job_title, locale=lang),
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


# ══════════════════ حسابي — الإعدادات الشخصية (ق-58) ══════════════════

@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def my_account(request):
    """
    إعدادات المستخدم عن نفسه: الصورة واللغة.

    متاحة لكل مصادَق بلا صلاحية — فهي بياناته هو.
    """
    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    if request.method == "PUT":
        locale = request.data.get("preferred_locale")
        if locale in ("ar", "en", "ur", "hi", "tl", "bn"):
            person.preferred_locale = locale
            person.save(update_fields=["preferred_locale", "updated_at"])

    from apps.core.models_files import FileKind, StoredFile
    avatar = StoredFile.objects.filter(
        person=person, kind=FileKind.AVATAR, is_deleted=False
    ).order_by("-created_at").first()

    return Response({
        "username": request.user.username,
        "name_ar": person.display_name,
        "email": person.email,
        "mobile": person.mobile_e164,
        "preferred_locale": person.preferred_locale,
        "avatar_id": avatar.id if avatar else None,
        # المسار بلا بادئة /api — الواجهة تضيف API_BASE بنفسها،
        # وإضافتها هنا تُنتج /api/api/files/3/ فتنكسر الصورة
        "avatar_url": f"/files/{avatar.id}/" if avatar else None,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_my_password(request):
    """
    تغيير كلمة المرور — بالقديمة والجديدة.

    القديمة شرط: من ترك جهازه مفتوحًا لا يُغيَّر عليه.
    """
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    old = request.data.get("current_password", "")
    new = request.data.get("new_password", "")

    if not request.user.check_password(old):
        return Response({"detail": "كلمة المرور الحالية غير صحيحة",
                         "code": "wrong_password"}, status=400)

    if old == new:
        return Response({"detail": "كلمة المرور الجديدة تطابق الحالية"},
                        status=400)

    try:
        validate_password(new, request.user)
    except DjangoValidationError as e:
        return Response({"detail": " · ".join(e.messages),
                         "code": "weak_password"}, status=400)

    request.user.set_password(new)
    request.user.save(update_fields=["password"])
    update_session_auth_hash(request, request.user)

    # إبطال كل الرموز الأخرى — تغيير كلمة المرور يُخرج الأجهزة
    from apps.accounts.models_tokens import AuthToken
    AuthToken.objects.filter(user=request.user).update(revoked=True)

    return Response({
        "changed": True,
        "note": "غُيّرت كلمة المرور — سُجّل خروجك من كل الأجهزة",
    })


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def my_avatar(request):
    """رفع الصورة الشخصية أو حذفها (ق-61)."""
    from apps.core.models_files import FileKind, StoredFile
    from apps.core.services.files import UploadError, soft_delete, store

    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    if request.method == "DELETE":
        for f in StoredFile.objects.filter(
                person=person, kind=FileKind.AVATAR, is_deleted=False):
            soft_delete(f, by_person=person)
        return Response({"deleted": True})

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return Response({"detail": "لم يُرفع ملف"}, status=400)

    # الصورة الجديدة تحلّ محل القديمة
    for f in StoredFile.objects.filter(
            person=person, kind=FileKind.AVATAR, is_deleted=False):
        soft_delete(f, by_person=person)

    try:
        obj, dup = store(
            uploaded=uploaded, kind=FileKind.AVATAR,
            account=person.account, person=person, uploaded_by=person)
    except UploadError as e:
        return Response({"detail": str(e), "code": "upload_error"},
                        status=400)

    return Response({
        "id": obj.id,
        "url": f"/files/{obj.id}/",
        "size": obj.size_label,
        "was_duplicate": dup,
    }, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_attachment(request):
    """
    رفع مرفق طلب (ق-70).

    متاح لكل من يقدّم طلبًا — الموظف لنفسه أو المسنِد نيابةً عنه.
    والحدود من KIND_RULES: PDF وصور، مليونا بايت، وتصغير تلقائي.

    ولا يُربط بطلب هنا: الملف يُرفع أولًا ويُرسل معرّفه مع الطلب،
    فالمستخدم يرى ما رفعه قبل أن يُرسل.
    """
    from apps.core.models_files import FileKind
    from apps.core.services.files import UploadError, store

    person = getattr(request.user, "person", None)
    if person is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return Response({"detail": "لم يُرفع ملف"}, status=400)

    try:
        obj, dup = store(
            uploaded=uploaded, kind=FileKind.ATTACHMENT,
            account=person.account, person=person, uploaded_by=person)
    except UploadError as e:
        return Response({"detail": str(e), "code": "upload_error"},
                        status=400)

    return Response({
        "id": obj.id,
        "url": f"/files/{obj.id}/",
        "name": obj.original_name,
        "size": obj.size_label,
        "was_duplicate": dup,
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def serve_file(request, file_id):
    """
    يخدم ملفًا بعد فحص الصلاحية (ق-61).

    لا رابط مباشر: من يعرف المسار لا يصل، ومن له حق الوصول يصل.
    """
    from django.http import FileResponse, Http404

    from apps.core.models_files import FileKind, StoredFile

    obj = StoredFile.objects.filter(id=file_id, is_deleted=False).first()
    if obj is None:
        raise Http404

    person = getattr(request.user, "person", None)

    # الصورة الشخصية وملفات صاحبها: يراها هو
    if person and obj.person_id == person.id:
        pass
    elif obj.kind == FileKind.AVATAR:
        pass      # الصور الشخصية مرئية لزملاء الحساب
    else:
        Gate.require(request.user, "employees.view")

    try:
        return FileResponse(obj.file.open("rb"),
                            filename=obj.original_name)
    except FileNotFoundError:
        raise Http404


# ══════════════════ ملف الموظف الكامل (ق-63) ══════════════════

def _person_block(p):
    """البيانات الأساسية — الاسم والهوية والجواز."""
    return {
        "id": p.id,
        "first_name_ar": p.first_name_ar,
        "father_name_ar": p.father_name_ar,
        "grandfather_name_ar": p.grandfather_name_ar,
        "family_name_ar": p.family_name_ar,
        "full_name_ar": p.display_name,
        "full_name_en": p.full_name_en,
        "gender": p.gender,
        "gender_label": p.get_gender_display(),
        "birth_date": p.birth_date,
        "birth_date_hijri": p.birth_date_hijri,
        "marital_status": p.marital_status,
        "marital_label": (p.get_marital_status_display()
                          if p.marital_status else ""),
        "nationality_code": p.nationality_code,
        "id_type": p.id_type,
        "id_type_label": p.get_id_type_display(),
        "id_number": p.id_number,
        "id_expiry_date": p.id_expiry_date,
        "id_expiry_hijri": p.id_expiry_hijri,
        "passport_number": p.passport_number,
        "passport_expiry_date": p.passport_expiry_date,
        "border_number": p.border_number,
        "mobile": p.mobile_e164,
        "email": p.email,
        "preferred_locale": p.preferred_locale,
        "gosi_scheme_code": p.gosi_scheme_code,
        "gosi_first_subscription_date": p.gosi_first_subscription_date,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_profile(request, employment_id):
    """
    ملف الموظف الكامل — أحد عشر تبويبًا (ق-63).

    يرجع كل الأقسام دفعةً واحدة: الواجهة تعرضها بتبويبات بلا
    نداءات متتابعة.
    """
    from datetime import date

    from apps.core.models_files import FileKind, StoredFile
    from apps.employees.models import Employment, SalaryStructure
    from apps.employees.models_assets import (
        Advance, AdvanceStatus, Asset, AssetStatus, EmployeeDocument,
    )
    from apps.payroll.models_banks import label_for

    from apps.core.i18n import localized, request_locale
    lang = request_locale(request)

    # ق-65: الموظف يرى ملفه هو بلا صلاحية إدارية — بياناته ملكه.
    # وغيره يحتاج employees.view بنطاقه.
    person = getattr(request.user, "person", None)
    own = person and Employment.objects.filter(
        id=employment_id, person=person).exists()

    if not own:
        Gate.require(request.user, "employees.view")
        base = Gate.filter_queryset(
            request.user, "employees.view", Employment.objects.all())
    else:
        base = Employment.objects.filter(person=person)

    emp = base.filter(id=employment_id).select_related(
        "person", "department", "branch", "job_title",
        "direct_manager__person", "job_grade", "job_step",
        "primary_site", "company").first()

    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    p = emp.person

    # ── مدة الخدمة ──
    start = emp.service_start_date or emp.join_date
    days = (date.today() - start).days
    years, rem = divmod(days, 365)

    # ── الراتب ──
    structure = SalaryStructure.objects.filter(
        employment=emp, effective_to__isnull=True
    ).prefetch_related("lines__component").first()

    lines, gross = [], 0
    if structure:
        for ln in structure.lines.all():
            lines.append({
                "component": localized(ln.component, locale=lang),
                "code": ln.component.code,
                "amount": str(ln.amount),
                "is_deduction": getattr(ln.component, "is_deduction", False),
                "in_gosi": getattr(ln.component, "in_gosi_wage", False),
                "in_eosb": getattr(ln.component, "in_eosb_wage", False),
            })
            gross += float(ln.amount)

    # ── السجل التاريخي (ق-66): نسبة التغيير ومن أجراه ──
    structures = list(SalaryStructure.objects.filter(
        employment=emp).order_by("-effective_from").prefetch_related(
        "lines__component").select_related("approved_by_person")[:12])

    history = []
    for i, st in enumerate(structures):
        total = sum(float(l.amount) for l in st.lines.all())

        # النسبة مقارنةً بما قبله (الأقدم في القائمة)
        change_pct = None
        if i + 1 < len(structures):
            prev = sum(float(l.amount) for l in structures[i + 1].lines.all())
            if prev > 0:
                change_pct = round((total - prev) / prev * 100, 2)

        history.append({
            "id": st.id,
            "effective_from": st.effective_from,
            "effective_to": st.effective_to,
            "gross": f"{total:.2f}",
            "change_percent": change_pct,
            "reason": st.reason or "",
            "note": st.note or "",
            "changed_by": (st.approved_by_person.display_name
                           if st.approved_by_person else ""),
            "lines": [{
                "component": localized(l.component, locale=lang),
                "amount": str(l.amount),
                "is_deduction": getattr(l.component, "is_deduction", False),
            } for l in st.lines.all()],
        })

    # ── تفصيل الراتب الحالي (ق-66): استحقاقات ثم خصومات ثم صافٍ ──
    earnings = [l for l in lines if not l.get("is_deduction")]
    deductions = [l for l in lines if l.get("is_deduction")]
    total_earnings = sum(float(l["amount"]) for l in earnings)
    total_deductions = sum(float(l["amount"]) for l in deductions)

    # حصة الموظف من التأمينات — خصم فعلي من راتبه
    # الحصة تُحتسب في المسير — نأخذها من آخر قسيمة معتمدة
    gosi_employee = 0.0
    if emp.is_gosi_registered and not emp.gosi_borne_by_company:
        try:
            from apps.payroll.models import Payslip
            last = Payslip.objects.filter(
                employment=emp).order_by("-id").first()
            if last:
                gosi_employee = float(
                    getattr(last, "gosi_employee_share", 0) or 0)
        except Exception:      # noqa: BLE001
            gosi_employee = 0.0

    # ── التابعون وأرقام الطوارئ ──
    dependents = [{
        "id": d.id, "full_name_ar": d.full_name_ar,
        "relation": d.relation, "relation_label": d.get_relation_display(),
        "id_number": d.id_number, "id_expiry_date": d.id_expiry_date,
        "birth_date": d.birth_date, "nationality_code": d.nationality_code,
    } for d in p.dependents.all()]

    contacts = [{
        "id": c.id, "full_name_ar": c.full_name_ar,
        "relation": c.relation, "mobile": c.mobile,
        "phone": c.phone, "is_primary": c.is_primary,
    } for c in p.emergency_contacts.all()]

    # ── الوثائق ──
    documents = [{
        "id": d.id,
        "document_type": d.document_type,
        "type_label": d.get_document_type_display(),
        "document_number": d.document_number,
        "issue_date": d.issue_date,
        "expiry_date": d.expiry_date,
        "days_left": ((d.expiry_date - date.today()).days
                      if d.expiry_date else None),
    } for d in EmployeeDocument.objects.filter(employment=emp)]

    # ── الملفات ──
    files = [{
        "id": f.id, "kind": f.kind, "kind_label": f.get_kind_display(),
        "name": f.original_name, "size": f.size_label,
        "url": f"/files/{f.id}/",
        "uploaded_at": f.created_at,
    } for f in StoredFile.objects.filter(person=p, is_deleted=False)]

    avatar = next((f for f in files if f["kind"] == FileKind.AVATAR), None)

    # ── السلف والعهد ──
    advances = Advance.objects.filter(
        employment=emp, status=AdvanceStatus.ACTIVE)
    assets = Asset.objects.filter(
        employment=emp, status=AssetStatus.ASSIGNED)

    return Response({
        "employment_id": emp.id,
        "employee_no": emp.employee_no,
        "status": emp.status,
        "status_label": emp.get_status_display(),
        "avatar_url": avatar["url"] if avatar else None,
        # الموظف يقرأ ملفه ويطلب تعديله؛ الموارد تعدّل مباشرةً
        "is_own": bool(own),
        "can_edit": not own,

        "personal": _person_block(p),

        "job": {
            "job_title": localized(emp.job_title, locale=lang),
            "job_title_id": emp.job_title_id,
            "department": localized(emp.department, locale=lang),
            "department_id": emp.department_id,
            "branch": localized(emp.branch, locale=lang),
            "branch_id": emp.branch_id,
            "site": localized(emp.primary_site, locale=lang),
            "site_id": emp.primary_site_id,
            "manager": (emp.direct_manager.person.display_name
                        if emp.direct_manager else ""),
            "manager_id": emp.direct_manager_id,
            "grade": localized(emp.job_grade, locale=lang),
            "grade_id": emp.job_grade_id,
            "step": localized(emp.job_step, locale=lang),
            "step_id": emp.job_step_id,
            "employment_type": emp.employment_type,
            "work_ratio": str(emp.work_ratio),
        },

        "contract": {
            "contract_type": emp.contract_type,
            "contract_start_date": emp.contract_start_date,
            "contract_end_date": emp.contract_end_date,
            "join_date": emp.join_date,
            "service_start_date": start,
            "probation_days": emp.probation_days,
            "probation_end_date": emp.probation_end_date,
            "in_probation": (emp.probation_end_date is not None
                             and emp.probation_end_date >= date.today()),
            "service_years": years,
            "service_months": rem // 30,
        },

        "salary": {
            "gross": f"{gross:.2f}",
            "lines": lines,
            # ق-66: الراتب يُعرض كما يُبنى
            "earnings": earnings,
            "deductions": deductions,
            "total_earnings": f"{total_earnings:.2f}",
            "total_deductions": f"{total_deductions:.2f}",
            "gosi_employee": f"{gosi_employee:.2f}",
            "net": f"{total_earnings - total_deductions - gosi_employee:.2f}",
            "history": history,
        },

        "gosi": {
            "is_registered": emp.is_gosi_registered,
            "establishment_no": emp.gosi_establishment_no,
            "registered_at": emp.gosi_registered_at,
            "declared_wage": (str(emp.gosi_declared_wage)
                              if emp.gosi_declared_wage else ""),
            "borne_by_company": emp.gosi_borne_by_company,
            "scheme_code": p.gosi_scheme_code,
            "is_mol_registered": emp.is_mol_registered,
            "mol_contract_no": emp.mol_contract_no,
            "include_in_wps": emp.include_in_wps,
        },

        "bank": {
            "iban": emp.iban,
            "bank_name": label_for(emp.iban),
            "bank_code": emp.bank_code,
            "payment_method": emp.payment_method,
        },

        "dependents": dependents,
        "emergency_contacts": contacts,
        "documents": documents,
        "files": files,

        "obligations": {
            "advances_count": advances.count(),
            "advances_outstanding": f"{sum(float(a.amount) - float(a.repaid_amount) for a in advances):.2f}",
            "assets_count": assets.count(),
        },
    })


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_employee_profile(request, employment_id):
    """
    تعديل ملف الموظف — قسمًا قسمًا (ق-63).

    يقبل `section` ليحدّد ما يُعدَّل، فلا يُرسل الملف كاملًا
    لتغيير حقل واحد.
    """
    from apps.employees.models import Employment

    Gate.require(request.user, "employees.edit")
    emp = Gate.filter_queryset(
        request.user, "employees.edit", Employment.objects.all()
    ).filter(id=employment_id).select_related("person").first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    section = request.data.get("section", "")
    d = request.data.get("data") or {}
    p = emp.person

    PERSON_FIELDS = {
        "first_name_ar", "father_name_ar", "grandfather_name_ar",
        "family_name_ar", "full_name_en", "gender", "birth_date",
        "birth_date_hijri", "marital_status", "nationality_code",
        "id_expiry_date", "id_expiry_hijri", "passport_number",
        "passport_expiry_date", "border_number", "email",
        "preferred_locale", "gosi_scheme_code",
        "gosi_first_subscription_date",
    }

    EMPLOYMENT_FIELDS = {
        "job_title_id", "department_id", "branch_id", "primary_site_id",
        "direct_manager_id", "job_grade_id", "job_step_id",
        "employment_type", "work_ratio",
        "contract_type", "contract_start_date", "contract_end_date",
        "probation_days",
        "is_gosi_registered", "gosi_establishment_no", "gosi_declared_wage",
        "gosi_borne_by_company", "is_mol_registered", "mol_contract_no",
        "include_in_wps", "iban", "bank_code", "payment_method",
    }

    changed = []

    for key, value in d.items():
        if key in PERSON_FIELDS:
            setattr(p, key, value if value != "" else None
                    if key.endswith("_date") else value)
            changed.append(key)
        elif key in EMPLOYMENT_FIELDS:
            setattr(emp, key, value if value != "" else None
                    if (key.endswith("_date") or key.endswith("_id"))
                    else value)
            changed.append(key)

    if not changed:
        return Response({"detail": "لا حقول قابلة للتعديل"}, status=400)

    # الآيبان يُتحقق منه — اشتراط البنك المركزي (ق-57)
    if "iban" in changed and emp.iban:
        from apps.employees.services.validators import validate_saudi_iban
        ok, err = validate_saudi_iban(emp.iban)
        if not ok:
            return Response({"detail": err, "code": "invalid_iban"},
                            status=400)

    try:
        p.save()
        emp.save()
    except Exception as e:      # noqa: BLE001
        return Response({"detail": f"قيمة غير صالحة: {e}"}, status=400)

    # سجل العمليات (ق-44)
    from apps.core.services.audit import log_action
    actor = getattr(request.user, "person", None)
    log_action(
        instance=emp, action="update", actor=actor,
        label=emp.employee_no,
        summary=f"تعديل {section or 'الملف'}: " + "، ".join(changed[:6]),
        channel="web")

    return Response({"updated": True, "fields": changed})




def _resolve_employment(request, employment_id, write=False):
    """
    يجلب الارتباط الوظيفي — الموظف يصل لملفه هو بلا صلاحية (ق-65).

    write=True يعني عملية كتابة: صاحب الملف مسموح له (فالنتيجة
    طلب لا تعديل)، وغيره يحتاج employees.edit.
    """
    from apps.employees.models import Employment

    person = getattr(request.user, "person", None)
    own = person and Employment.objects.filter(
        id=employment_id, person=person).exists()

    if own:
        return Employment.objects.filter(
            id=employment_id, person=person).select_related("person").first(), True

    Gate.require(request.user, "employees.edit" if write else "employees.view")
    emp = Gate.filter_queryset(
        request.user, "employees.edit" if write else "employees.view",
        Employment.objects.all()
    ).filter(id=employment_id).select_related("person").first()

    return emp, False

@api_view(["GET", "POST", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def employee_dependents(request, employment_id):
    """التابعون — توثيق فقط (ق-63)."""
    from apps.employees.models import Employment
    from apps.employees.models_profile import Dependent

    emp, own = _resolve_employment(request, employment_id,
                                   write=request.method != "GET")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    p = emp.person

    if request.method == "GET":
        return Response([{
            "id": d.id, "full_name_ar": d.full_name_ar,
            "full_name_en": d.full_name_en,
            "relation": d.relation, "relation_label": d.get_relation_display(),
            "id_number": d.id_number, "id_expiry_date": d.id_expiry_date,
            "birth_date": d.birth_date,
            "nationality_code": d.nationality_code,
        } for d in p.dependents.all()])

    d = request.data

    if request.method == "DELETE":
        Dependent.objects.filter(
            person=p, id=request.GET.get("id") or d.get("id")).delete()
        return Response({"deleted": True})

    if request.method == "PUT":
        obj = Dependent.objects.filter(person=p, id=d.get("id")).first()
        if obj is None:
            return Response({"detail": "التابع غير موجود"}, status=404)
    else:
        obj = Dependent(account_id=p.account_id, person=p)

    for f in ("full_name_ar", "full_name_en", "relation", "id_number",
              "nationality_code", "note"):
        if f in d:
            setattr(obj, f, (d.get(f) or "")[:180])
    for f in ("id_expiry_date", "birth_date"):
        if f in d:
            setattr(obj, f, d.get(f) or None)

    if not obj.full_name_ar or not obj.relation:
        return Response({"detail": "الاسم وصلة القرابة مطلوبان"}, status=400)

    obj.save()
    return Response({"id": obj.id}, status=201 if request.method == "POST"
                    else 200)


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def employee_contacts(request, employment_id):
    """أرقام الطوارئ."""
    from apps.employees.models import Employment
    from apps.employees.models_profile import EmergencyContact

    emp, own = _resolve_employment(request, employment_id,
                                   write=request.method != "GET")
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    p = emp.person

    if request.method == "GET":
        return Response([{
            "id": c.id, "full_name_ar": c.full_name_ar,
            "relation": c.relation, "mobile": c.mobile,
            "phone": c.phone, "is_primary": c.is_primary,
        } for c in p.emergency_contacts.all()])

    if request.method == "DELETE":
        EmergencyContact.objects.filter(
            person=p, id=request.GET.get("id")).delete()
        return Response({"deleted": True})

    d = request.data
    obj = EmergencyContact.objects.create(
        account_id=p.account_id, person=p,
        full_name_ar=(d.get("full_name_ar") or "")[:180],
        relation=(d.get("relation") or "")[:60],
        mobile=(d.get("mobile") or "")[:20],
        phone=(d.get("phone") or "")[:20],
        is_primary=bool(d.get("is_primary")))

    return Response({"id": obj.id}, status=201)


# ══════════ التغيير الوظيفي (ق-82) ══════════

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def job_changes(request, employment_id):
    """
    تغييرات الموظف الوظيفية — قراءةً وتسجيلًا.

    موظف الموارد يسجّل، ومدير الموارد يعتمد (ق-82).
    """
    from datetime import date as _date

    from apps.employees.models import ChangeType, JobChange
    from apps.employees.services.job_changes import (JobChangeError,
                                                     create_change)
    from apps.organization.models import Department

    Gate.require(request.user, "employees.view")
    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=employment_id,
             company_id=_company_id(request)).select_related(
        "person", "department").first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    if request.method == "GET":
        rows = []
        for c in emp.job_changes.select_related(
                "new_department", "new_job_title", "successor__person"):
            rows.append({
                "id": c.id,
                "type": c.change_type,
                "type_label": c.get_change_type_display(),
                "effective_from": c.effective_from,
                "status": c.status,
                "status_label": c.get_status_display(),
                "new_job_title": (c.new_job_title.name_ar
                                  if c.new_job_title_id else None),
                "new_department": (c.new_department.name_ar
                                   if c.new_department_id else None),
                "new_role_code": c.new_role_code,
                "dismissal_reason": c.dismissal_reason,
                "successor": (c.successor.person.display_name
                              if c.successor_id else None),
                "note": c.note,
                "created_at": c.created_at,
                "decided_at": c.decided_at,
                "decision_note": c.decision_note,
            })
        return Response(rows)

    # ── التسجيل ──
    Gate.require(request.user, "employees.edit")

    d = request.data
    ctype = d.get("change_type", "")
    if ctype not in ChangeType.values:
        return Response({"detail": f"نوع غير معروف: {ctype}"}, status=400)

    dept = None
    if d.get("new_department_id"):
        # معزول ذاتيًا: مقيَّد بشركة الموظف الذي مرّ بالبوابة
        dept = Department.objects.filter(id=d["new_department_id"], company_id=emp.company_id).first()
        if dept is None:
            return Response({"detail": "الإدارة غير موجودة"}, status=400)

    mgr = None
    if d.get("new_direct_manager_id"):
        mgr = Employment.objects.filter(id=d["new_direct_manager_id"], company_id=emp.company_id).first()

    title = None
    if d.get("new_job_title_id"):
        from apps.organization.models import JobTitle
        title = JobTitle.objects.filter(
            id=d["new_job_title_id"], company_id=emp.company_id).first()
        if title is None:
            return Response({"detail": "المسمّى غير موجود"}, status=400)

    succ = None
    if d.get("successor_employment_id"):
        succ = Employment.objects.filter(id=d["successor_employment_id"], company_id=emp.company_id).first()
        if succ is None:
            return Response({"detail": "البديل غير موجود"}, status=400)

    try:
        c = create_change(
            employment=emp, change_type=ctype,
            effective_from=_date.fromisoformat(str(d["effective_from"])),
            new_job_title=title,
            new_department=dept, new_direct_manager=mgr,
            new_role_code=d.get("new_role_code", ""),
            dismissal_reason=d.get("dismissal_reason", ""),
            successor=succ, note=d.get("note", ""),
            actor=getattr(request.user, "person", None))
    except JobChangeError as e:
        return Response({"detail": str(e), "code": "invalid_change"},
                        status=400)
    except (KeyError, ValueError) as e:
        return Response({"detail": f"بيانات ناقصة: {e}"}, status=400)

    return Response({"id": c.id, "status": c.status,
                     "status_label": c.get_status_display()}, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def decide_job_change(request, change_id):
    """
    مدير الموارد يعتمد التغيير أو يرفضه — وبالاعتماد يسري (ق-82).
    """
    from apps.employees.models import JobChange
    from apps.employees.services.job_changes import (JobChangeError,
                                                     decide_change)

    Gate.require(request.user, "employees.terminate")

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    c = JobChange.objects.filter(
        id=change_id, company_id=_company_id(request)
    ).select_related("employment__person", "successor__person").first()
    if c is None:
        return Response({"detail": "التغيير غير موجود"}, status=404)

    try:
        c, effect = decide_change(
            change=c, approve=bool(request.data.get("approve")),
            actor=getattr(request.user, "person", None),
            note=request.data.get("note", ""))
    except JobChangeError as e:
        return Response({"detail": str(e), "code": "cannot_decide"},
                        status=409)

    return Response({"id": c.id, "status": c.status,
                     "status_label": c.get_status_display(),
                     "effect": effect})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_job_changes(request):
    """
    التغييرات الوظيفية التي تنتظر قراري (ق-82).

    تُضمّ لعدّاد ما ينتظر القرار: فمن يفتح النظام يرى الرقم بلا
    فتح ملف كل موظف.
    """
    from apps.employees.models import ChangeStatus, JobChange

    if not Gate.check(request.user, "employees.terminate").allowed:
        return Response([])

    # معزول ذاتيًا: مقيَّد بشركة المنفّذ النشطة
    qs = JobChange.objects.filter(company_id=_company_id(request), status=ChangeStatus.PENDING).select_related(
        "employment__person", "new_department", "successor__person")

    return Response([{
        "id": c.id,
        "employment_id": c.employment_id,
        "employee_no": c.employment.employee_no,
        "employee_name": c.employment.person.display_name,
        "type": c.change_type,
        "type_label": c.get_change_type_display(),
        "effective_from": c.effective_from,
        "new_department": (c.new_department.name_ar
                           if c.new_department_id else None),
        "successor": (c.successor.person.display_name
                      if c.successor_id else None),
        "created_at": c.created_at,
    } for c in qs.order_by("-created_at")])
