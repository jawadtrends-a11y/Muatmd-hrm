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
