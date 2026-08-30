"""
خدمة العهد ووثائق الموظف (ق-41).

العهد تُقوَّم ماليًا وتُخصم من مخالصة نهاية الخدمة عند عدم الإرجاع.
الوثائق تُنبَّه قبل انتهائها — انتهاء إقامة يوقف الموظف ويغرّم الشركة.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from apps.employees.models_assets import (
    Asset, AssetStatus, DocumentType, EmployeeDocument,
)

ZERO = Decimal("0")
TWO = Decimal("0.01")


def r2(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


class AssetError(Exception):
    pass


def _next_asset_no(company):
    year = date.today().year
    count = Asset.objects.filter(
        company=company, asset_no__startswith=f"AST-{year}").count()
    return f"AST-{year}-{count + 1:05d}"


# ══════════ العهد ══════════

@transaction.atomic
def assign_asset(*, employment, name_ar, value=0, category="other",
                 serial_number="", assigned_date=None,
                 expected_return_date=None, handover_document="",
                 condition_note=""):
    """يسلّم عهدة لموظف."""
    value = Decimal(str(value))
    if value < 0:
        raise AssetError("قيمة العهدة لا تكون سالبة")

    return Asset.objects.create(
        account=employment.account, company=employment.company,
        asset_no=_next_asset_no(employment.company),
        name_ar=name_ar, category=category, serial_number=serial_number,
        value=value, employment=employment,
        assigned_date=assigned_date or date.today(),
        expected_return_date=expected_return_date,
        handover_document=handover_document,
        condition_note=condition_note, status=AssetStatus.ASSIGNED)


@transaction.atomic
def return_asset(*, asset, returned_date=None, condition_note="",
                 status=AssetStatus.RETURNED):
    """
    استرجاع العهدة.

    status: returned (سليمة) · damaged (تالفة) · lost (مفقودة)
    التالفة والمفقودة تبقى ضمن المخالصة.
    """
    if asset.status not in (AssetStatus.ASSIGNED, AssetStatus.DAMAGED,
                            AssetStatus.LOST):
        raise AssetError(
            f"العهدة {asset.get_status_display()} — لا تُسترجع")

    asset.status = status
    asset.returned_date = returned_date or date.today()
    if condition_note:
        asset.condition_note = condition_note
    asset.save()
    return asset


def outstanding_assets(employment):
    """عهد لم تُرجَع — تدخل المخالصة."""
    return Asset.objects.filter(
        employment=employment,
        status__in=[AssetStatus.ASSIGNED, AssetStatus.LOST,
                    AssetStatus.DAMAGED])


def assets_settlement(employment):
    """
    كشف العهد عند نهاية الخدمة (ق-41).

    ما لم يُرجَع تُخصم قيمته من المستحقات.
    """
    rows = []
    total = ZERO
    for a in outstanding_assets(employment):
        rows.append({
            "asset_no": a.asset_no,
            "name_ar": a.name_ar,
            "category": a.get_category_display(),
            "serial_number": a.serial_number,
            "value": str(r2(a.value)),
            "status": a.get_status_display(),
            "assigned_date": str(a.assigned_date),
        })
        total += a.value

    return {
        "count": len(rows),
        "total_value": str(r2(total)),
        "assets": rows,
        "note": ("تُخصم قيمة ما لم يُرجَع من مستحقات نهاية الخدمة"
                 if rows else "لا عهد قائمة"),
    }


@transaction.atomic
def deduct_unreturned(*, employment, note=""):
    """يعلّم العهد غير المرجَعة كمخصومة بعد تسوية المخالصة."""
    count = 0
    for a in outstanding_assets(employment):
        a.status = AssetStatus.DEDUCTED
        if note:
            a.condition_note = note
        a.save()
        count += 1
    return count


# ══════════ الوثائق ══════════

@transaction.atomic
def add_document(*, employment, document_type, document_number="",
                 expiry_date=None, issue_date=None, expiry_hijri="",
                 issuing_authority="", file_url="", alert_days_before=60,
                 note=""):
    """يضيف وثيقة بتاريخ انتهاء."""
    if expiry_date and issue_date and expiry_date < issue_date:
        raise AssetError("تاريخ الانتهاء قبل تاريخ الإصدار")

    return EmployeeDocument.objects.create(
        account=employment.account, company=employment.company,
        employment=employment, document_type=document_type,
        document_number=document_number, issue_date=issue_date,
        expiry_date=expiry_date, expiry_hijri=expiry_hijri,
        issuing_authority=issuing_authority, file_url=file_url,
        alert_days_before=alert_days_before, note=note)


def expiring_documents(company, within_days=60, include_expired=True):
    """
    وثائق تنتهي قريبًا أو انتهت — أساس التنبيه الاستباقي.

    انتهاء إقامة أو رخصة عمل يوقف الموظف ويعرّض الشركة لغرامات.
    """
    from apps.employees.models import EmploymentStatus

    today = date.today()
    horizon = today + timedelta(days=within_days)

    qs = EmployeeDocument.objects.filter(
        company=company, expiry_date__isnull=False,
        expiry_date__lte=horizon,
        employment__status=EmploymentStatus.ACTIVE,
    ).select_related("employment__person")

    if not include_expired:
        qs = qs.filter(expiry_date__gte=today)

    rows = []
    for d in qs.order_by("expiry_date"):
        days = (d.expiry_date - today).days
        rows.append({
            "document_id": d.id,
            "employee_no": d.employment.employee_no,
            "name": d.employment.person.display_name,
            "document_type": d.get_document_type_display(),
            "document_number": d.document_number,
            "expiry_date": str(d.expiry_date),
            "expiry_hijri": d.expiry_hijri,
            "days_remaining": days,
            "is_expired": days < 0,
            "severity": ("منتهية" if days < 0
                         else "حرجة" if days <= 15
                         else "قريبة" if days <= 30
                         else "تنبيه"),
        })
    return rows


def document_alerts_for(employment):
    """وثائق موظف تحتاج تنبيهًا — لملفه الشخصي."""
    return [
        {
            "document_type": d.get_document_type_display(),
            "expiry_date": str(d.expiry_date),
            "days_remaining": d.days_to_expiry,
            "is_expired": d.is_expired,
        }
        for d in EmployeeDocument.objects.filter(employment=employment)
        if d.needs_alert
    ]
