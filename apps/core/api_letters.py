"""
مسارات قوالب الخطابات والصادر منها (ق-128).
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.core.models import IssuedLetter, LetterTemplate
from apps.core.services import letters as svc


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _tpl_json(t):
    return {
        "id": t.id, "code": t.code, "name_ar": t.name_ar,
        "heading_ar": t.heading_ar, "addressee_ar": t.addressee_ar,
        "body_ar": t.body_ar, "includes_salary": t.includes_salary,
        "valid_days": t.valid_days, "is_active": t.is_active,
        "issued_count": t.issued.count(),
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def templates(request):
    """قوالب الشركة — عرضًا وإضافة."""
    Features.require(_company_id(request), "letter_templates")

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = LetterTemplate.objects.filter(company_id=_company_id(request))
        return Response({
            "templates": [_tpl_json(t) for t in qs],
            "variables": [{"key": k, "label_ar": lbl, "salary": sal}
                          for k, lbl, sal in svc.VARIABLES],
        })

    Gate.require(request.user, "employees.edit")
    from apps.accounts.models import Company

    # مقيَّد بشركة المنفّذ النشطة
    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    code = str(d.get("code") or "").strip().upper()
    if not code or not str(d.get("name_ar") or "").strip():
        return Response({"detail": "الرمز والاسم مطلوبان"}, status=400)
    if LetterTemplate.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    try:
        svc.validate_body(d.get("body_ar", ""))
    except svc.LetterError as e:
        return Response({"detail": str(e)}, status=400)

    t = LetterTemplate.objects.create(
        account=comp.account, company=comp, code=code,
        name_ar=d.get("name_ar", ""), name_en=d.get("name_en", ""),
        heading_ar=d.get("heading_ar", ""),
        addressee_ar=d.get("addressee_ar", ""),
        body_ar=d.get("body_ar", ""),
        includes_salary=bool(d.get("includes_salary", False)),
        valid_days=int(d.get("valid_days") or 30))
    return Response(_tpl_json(t), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def template_detail(request, template_id):
    """تعديل قالب أو تعطيله — والمستعمل لا يُحذف."""
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "letter_templates")

    t = LetterTemplate.objects.filter(
        id=template_id, company_id=_company_id(request)).first()
    if t is None:
        return Response({"detail": "غير موجود"}, status=404)

    if request.method == "DELETE":
        # ⚠️ ما صدر منه خطابٌ يُعطَّل ولا يُحذف: الخطاب يشير إليه،
        # وحذفه يترك صادرًا بلا قالب.
        if t.issued.exists():
            t.is_active = False
            t.save(update_fields=["is_active"])
            return Response({"deactivated": True,
                             "detail": "صدرت منه خطابات — عُطّل ولم يُحذف"})
        t.delete()
        return Response({"deleted": True})

    d = request.data
    if "body_ar" in d:
        try:
            svc.validate_body(d["body_ar"])
        except svc.LetterError as e:
            return Response({"detail": str(e)}, status=400)
    for f in ("name_ar", "name_en", "heading_ar", "addressee_ar",
              "body_ar"):
        if f in d:
            setattr(t, f, str(d[f] or ""))
    if "includes_salary" in d:
        t.includes_salary = bool(d["includes_salary"])
    if "is_active" in d:
        t.is_active = bool(d["is_active"])
    if "valid_days" in d:
        t.valid_days = int(d["valid_days"] or 30)
    t.save()
    return Response(_tpl_json(t))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def preview_template(request, template_id):
    """
    معاينة القالب ببيانات موظف — قبل أن يُصدر.

    فمن يكتب قالبًا يرى نتيجته لا نصًّا بمتغيّرات.
    """
    from apps.employees.models import Employment

    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "letter_templates")

    t = LetterTemplate.objects.filter(
        id=template_id, company_id=_company_id(request)).first()
    if t is None:
        return Response({"detail": "القالب غير موجود"}, status=404)

    emp = Gate.filter_queryset(
        request.user, "employees.view", Employment.objects.all()
    ).filter(id=request.data.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    ctx = svc.build_context(
        emp, letter_no="LTR-XXXX-00000",
        addressee=request.data.get("addressee", ""),
        include_salary=bool(request.data.get("include_salary"))
        and t.includes_salary)
    return Response({
        "heading_ar": svc.render(t.heading_ar, ctx),
        "body_ar": svc.render(t.body_ar, ctx),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def issue_letter(request):
    """يُصدر خطابًا لموظف — بنصٍّ مجمَّد ورقمٍ متسلسل."""
    from apps.employees.models import Employment

    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "letter_templates")

    t = LetterTemplate.objects.filter(
        id=request.data.get("template_id"),
        company_id=_company_id(request), is_active=True).first()
    if t is None:
        return Response({"detail": "القالب غير متاح"}, status=404)

    emp = Gate.filter_queryset(
        request.user, "employees.edit", Employment.objects.all()
    ).filter(id=request.data.get("employment_id")).first()
    if emp is None:
        return Response({"detail": "الموظف غير موجود"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        letter = svc.issue(
            template=t, employment=emp,
            addressee=request.data.get("addressee", ""),
            include_salary=bool(request.data.get("include_salary")),
            request_id=request.data.get("request_id"),
            issued_by_person_id=actor.id if actor else None)
    except svc.LetterError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({
        "id": letter.id, "letter_no": letter.letter_no,
        "issued_on": letter.issued_on, "valid_until": letter.valid_until,
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def letter_detail(request, letter_id):
    """
    نصّ خطابٍ صادر — لصاحبه أو لمن يملك عرض الموظفين.

    ⚠️ **وصاحبه يراه دائمًا**: خطابه هو، ولو لم يملك صلاحية.
    """
    from apps.employees.models import Employment

    letter = IssuedLetter.objects.filter(
        id=letter_id, company_id=_company_id(request)
    ).select_related("employment__person", "template").first()
    if letter is None:
        return Response({"detail": "غير موجود"}, status=404)

    person = getattr(request.user, "person", None)
    mine = person and letter.employment.person_id == person.id
    if not mine:
        allowed = Gate.filter_queryset(
            request.user, "employees.view", Employment.objects.all()
        ).filter(id=letter.employment_id).exists()
        if not allowed:
            return Response({"detail": "ليس لك"}, status=403)

    from datetime import date as _d

    return Response({
        "id": letter.id, "letter_no": letter.letter_no,
        "template": letter.template.name_ar,
        "employee": letter.employment.person.display_name,
        "employee_no": letter.employment.employee_no,
        "heading_ar": letter.heading_ar,
        "addressee_ar": letter.addressee_ar,
        "body_ar": letter.body_ar,
        "issued_on": letter.issued_on,
        "valid_until": letter.valid_until,
        "expired": bool(letter.valid_until
                        and letter.valid_until < _d.today()),
    })
