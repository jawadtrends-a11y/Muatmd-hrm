"""
بيانات المنشأة — قراءة وتعديل.

كل نقطة تمر بالبوابات الثلاث: الميزة → الصلاحية → النطاق.
ولا استعلام خام: الشركة تُجلب عبر Gate.filter_queryset حتى لا
يقرأ مستخدمُ حسابٍ شركةَ حسابٍ آخر.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Company
from apps.core.access.gate import Gate

# الحقول القابلة للتعديل — ما ليس هنا لا يُكتب مهما أُرسل.
EDITABLE = [
    "legal_name_ar", "legal_name_en",
    "cr_number", "cr_expiry_date", "unified_national_number", "vat_number",
    "gosi_establishment_no", "mol_establishment_no",
    "activity_code", "entity_size",
    "fiscal_year_start_month", "contact_email",
]


def _active_company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _serialize(c):
    return {
        "id": c.id,
        "code": c.code,
        "legal_name_ar": c.legal_name_ar,
        "legal_name_en": c.legal_name_en,
        "cr_number": c.cr_number,
        "cr_expiry_date": (c.cr_expiry_date.isoformat()
                           if c.cr_expiry_date else None),
        "unified_national_number": c.unified_national_number,
        "vat_number": c.vat_number,
        "gosi_establishment_no": c.gosi_establishment_no,
        "mol_establishment_no": c.mol_establishment_no,
        "activity_code": c.activity_code,
        "entity_size": c.entity_size,
        "fiscal_year_start_month": c.fiscal_year_start_month,
        "contact_email": c.contact_email,
        "is_active": c.is_active,
    }


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def company_settings(request):
    perm = "company.view" if request.method == "GET" else "company.edit"
    Gate.require(request.user, perm)

    cid = _active_company_id(request)
    if not cid:
        return Response({"detail": "لا شركة نشطة"},
                        status=status.HTTP_400_BAD_REQUEST)

    qs = Gate.filter_queryset(request.user, perm, Company.objects.all())
    company = qs.filter(id=cid).first()
    if company is None:
        return Response({"detail": "الشركة غير متاحة"},
                        status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(_serialize(company))

    data = request.data or {}
    errors = {}

    # الاسم النظامي لا يُفرَّغ — فهو ما يظهر في كل مستند.
    if "legal_name_ar" in data and not str(data["legal_name_ar"]).strip():
        errors["legal_name_ar"] = "الاسم النظامي مطلوب"

    if "fiscal_year_start_month" in data:
        try:
            m = int(data["fiscal_year_start_month"])
            if not 1 <= m <= 12:
                raise ValueError
        except (TypeError, ValueError):
            errors["fiscal_year_start_month"] = "الشهر بين ١ و١٢"

    email = str(data.get("contact_email", "")).strip()
    if email and "@" not in email:
        errors["contact_email"] = "بريد غير صحيح"

    if errors:
        return Response({"errors": errors},
                        status=status.HTTP_400_BAD_REQUEST)

    changed = []
    for f in EDITABLE:
        if f not in data:
            continue
        v = data[f]
        if f == "fiscal_year_start_month":
            v = int(v)
        elif f == "cr_expiry_date":
            v = v or None
        else:
            v = str(v).strip()
        if getattr(company, f) != v:
            setattr(company, f, v)
            changed.append(f)

    if changed:
        company.save(update_fields=changed + ["updated_at"])

    return Response(_serialize(company))


def _my_company_ids(user):
    """أرقام شركاته — توظيفه النشط، وما يبلغه نطاقه."""
    from apps.employees.models import Employment, EmploymentStatus

    m = getattr(user, "account_membership", None)
    if m is None:
        return None, set()
    ids = set()
    person = getattr(user, "person", None)
    if person is not None:
        ids = set(Employment.objects.filter(
            person_id=person.id, status=EmploymentStatus.ACTIVE
        ).values_list("company_id", flat=True))
    # مالك الحساب ومن نطاقه على الحساب يرى شركاته كلّها
    ids |= set(m.company_ids or [])
    return m, ids


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_companies(request):
    """
    شركات المستخدم — ما له فيها توظيف نشط داخل حسابه.

    ويظهر المبدّل لمن له أكثر من واحدة وحده: من له شركة واحدة لا
    يزحم قائمته بخيار لا يفعل شيئًا.
    """
    m, ids = _my_company_ids(request.user)
    if m is None:
        return Response({"active_id": None, "companies": []})

    qs = Company.objects.filter(id__in=ids, account_id=m.account_id,
                                is_active=True).order_by("legal_name_ar")
    return Response({
        "active_id": m.active_company_id,
        "companies": [{
            "id": c.id, "code": c.code,
            "name_ar": c.legal_name_ar,
            "name_en": c.legal_name_en or c.legal_name_ar,
        } for c in qs],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def switch_company(request):
    """
    تبديل الشركة النشطة — {"company_id": n}.

    ولا يُقبل إلا ما هو في شركاته: المُدخل من المستخدم، وقبوله
    بلا فحص يفتح شركة غيره.
    """
    m, allowed = _my_company_ids(request.user)
    if m is None:
        return Response({"detail": "لا عضوية"},
                        status=status.HTTP_403_FORBIDDEN)

    try:
        cid = int(request.data.get("company_id"))
    except (TypeError, ValueError):
        return Response({"detail": "معرّف غير صحيح"},
                        status=status.HTTP_400_BAD_REQUEST)

    # الشركة معطَّلة أو من حساب آخر لا تُقبل ولو كانت في نطاقه
    if not Company.objects.filter(id=cid, account_id=m.account_id,
                                  is_active=True).exists():
        return Response({"detail": "الشركة غير متاحة لك"},
                        status=status.HTTP_403_FORBIDDEN)
    if cid not in allowed:
        return Response({"detail": "الشركة غير متاحة لك"},
                        status=status.HTTP_403_FORBIDDEN)

    m.active_company_id = cid
    m.save(update_fields=["active_company"])
    return Response({"switched": True, "active_id": cid})
