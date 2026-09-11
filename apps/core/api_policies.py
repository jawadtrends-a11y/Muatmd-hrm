"""مسارات السياسات وإقراراتها (ق-129)."""
from datetime import date

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.access.gate import Gate
from apps.core.features.gate import Features
from apps.core.models import Policy, PolicyAudience
from apps.core.services import policies as svc


def _company_id(request):
    ctx = getattr(request, "account_ctx", None)
    return getattr(ctx, "active_company_id", None)


def _ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (fwd.split(",")[0].strip() if fwd
            else request.META.get("REMOTE_ADDR"))


def _my_employment(request):
    from apps.employees.models import Employment, EmploymentStatus

    person = getattr(request.user, "person", None)
    if person is None:
        return None
    return Employment.objects.filter(
        person=person, company_id=_company_id(request),
        status=EmploymentStatus.ACTIVE).first()


def _json(p):
    return {
        "id": p.id, "code": p.code, "title_ar": p.title_ar,
        "body_ar": p.body_ar, "version": p.version,
        "effective_from": p.effective_from,
        "audience": p.audience, "audience_label": p.get_audience_display(),
        "department_id": p.department_id, "branch_id": p.branch_id,
        "requires_ack": p.requires_ack,
        "is_published": p.is_published, "published_at": p.published_at,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def policies(request):
    """سياسات الشركة — عرضًا وإنشاءً."""
    Features.require(_company_id(request), "policies")

    if request.method == "GET":
        Gate.require(request.user, "employees.view")
        qs = Policy.objects.filter(company_id=_company_id(request))
        return Response({
            "policies": [_json(p) for p in qs],
            "audiences": [{"value": v, "label": lbl}
                          for v, lbl in PolicyAudience.choices],
        })

    Gate.require(request.user, "employees.edit")
    from apps.accounts.models import Company

    # مقيَّد بشركة المنفّذ النشطة
    comp = Company.objects.filter(id=_company_id(request)).first()
    if comp is None:
        return Response({"detail": "لا شركة نشطة"}, status=400)

    d = request.data
    code = str(d.get("code") or "").strip().upper()
    if not code or not str(d.get("title_ar") or "").strip():
        return Response({"detail": "الرمز والعنوان مطلوبان"}, status=400)
    if Policy.objects.filter(company=comp, code=code).exists():
        return Response({"detail": "الرمز مستعمل"}, status=409)

    try:
        eff = date.fromisoformat(str(d.get("effective_from")
                                     or date.today()))
    except ValueError:
        return Response({"detail": "تاريخ غير صالح"}, status=400)

    p = Policy.objects.create(
        account=comp.account, company=comp, code=code,
        title_ar=d.get("title_ar", ""), title_en=d.get("title_en", ""),
        body_ar=d.get("body_ar", ""), effective_from=eff,
        audience=d.get("audience") or PolicyAudience.ALL,
        department_id=d.get("department_id") or None,
        branch_id=d.get("branch_id") or None,
        requires_ack=bool(d.get("requires_ack", True)))
    return Response(_json(p), status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def policy_detail(request, policy_id):
    """
    تعديل سياسة أو حذفها.

    ⚠️ **وتعديل النصّ بعد النشر يرفع النسخة** — فيُبطل الإقرارات،
    ولا يحتجّ أحدٌ بتوقيعٍ على نصٍّ تغيّر.
    """
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "policies")

    p = Policy.objects.filter(
        id=policy_id, company_id=_company_id(request)).first()
    if p is None:
        return Response({"detail": "غير موجودة"}, status=404)

    if request.method == "DELETE":
        if p.acks.exists():
            return Response({
                "detail": "أُقرّ بها موظفون — لا تُحذف، أوقفها بدل ذلك",
                "code": "policy_acknowledged",
            }, status=409)
        p.delete()
        return Response({"deleted": True})

    d = request.data
    body_changed = ("body_ar" in d
                    and str(d["body_ar"]) != p.body_ar)

    for f in ("title_ar", "title_en", "audience"):
        if f in d:
            setattr(p, f, str(d[f] or ""))
    for f in ("department_id", "branch_id"):
        if f in d:
            setattr(p, f, d[f] or None)
    if "requires_ack" in d:
        p.requires_ack = bool(d["requires_ack"])
    if "is_published" in d and not d["is_published"]:
        p.is_published = False

    eff = None
    if d.get("effective_from"):
        try:
            eff = date.fromisoformat(str(d["effective_from"]))
            p.effective_from = eff
        except ValueError:
            return Response({"detail": "تاريخ غير صالح"}, status=400)
    p.save()

    if body_changed:
        if p.is_published and p.acks.exists():
            svc.bump_version(policy=p, body_ar=str(d["body_ar"]))
        else:
            p.body_ar = str(d["body_ar"])
            p.save(update_fields=["body_ar", "updated_at"])

    return Response(_json(p))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish_policy(request, policy_id):
    """ينشرها فتظهر لمن تخصّهم."""
    Gate.require(request.user, "employees.edit")
    Features.require(_company_id(request), "policies")

    p = Policy.objects.filter(
        id=policy_id, company_id=_company_id(request)).first()
    if p is None:
        return Response({"detail": "غير موجودة"}, status=404)

    actor = getattr(request.user, "person", None)
    try:
        svc.publish(policy=p, by_person_id=actor.id if actor else None)
    except svc.PolicyError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_json(p))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def policy_compliance(request, policy_id):
    """من أقرّ ومن لم يُقرّ — فسياسةٌ لا يُعرف من قرأها بلا فائدة."""
    Gate.require(request.user, "employees.view")
    Features.require(_company_id(request), "policies")

    p = Policy.objects.filter(
        id=policy_id, company_id=_company_id(request)).first()
    if p is None:
        return Response({"detail": "غير موجودة"}, status=404)
    return Response(svc.compliance(p))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_policies(request):
    """سياساتي — وما لم أُقرّ به أوّلًا."""
    Features.require(_company_id(request), "policies")

    emp = _my_employment(request)
    if emp is None:
        return Response([])
    return Response(svc.my_policies(emp))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def acknowledge(request, policy_id):
    """
    إقراري بالسياسة — بختم وقته.

    ⚠️ **ولا يُقرّ أحدٌ عن أحد**: التوقيع شخصيّ، ومن أقرّ عن غيره
    أبطل الحجّة.
    """
    Features.require(_company_id(request), "policies")

    emp = _my_employment(request)
    if emp is None:
        return Response({"detail": "لا ملف موظف مرتبط بحسابك"}, status=404)

    p = Policy.objects.filter(
        id=policy_id, company_id=_company_id(request),
        is_published=True).first()
    if p is None:
        return Response({"detail": "السياسة غير متاحة"}, status=404)

    try:
        ack, created = svc.acknowledge(policy=p, employment=emp,
                                       ip=_ip(request))
    except svc.PolicyError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({"acknowledged": True, "new": created,
                     "version": ack.version,
                     "at": ack.acknowledged_at})
