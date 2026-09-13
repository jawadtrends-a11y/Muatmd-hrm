"""
تقييم الأداء (ق-146).

⚠️⚠️ **وتقييم المدير مجهول** — لا يُحفظ اسم صاحبه.

⚠️ **والأثر تقريرٌ فقط** — لا مال.
"""
import hashlib
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class PerformanceError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def _require_enabled(company_id):
    from apps.core.features.gate import Features

    if not Features.enabled(company_id, "performance"):
        raise PerformanceError("تقييم الأداء غير متاح في باقتكم")


# ══════════ المؤشّرات ══════════

@transaction.atomic
def create_kpi(*, department, code, name_ar, scale, direction="higher",
               kind="quantitative", unit="", description="",
               default_target=None, by_employment_id=None):
    """
    مدير الإدارة يضع مؤشّرًا — **مسودّةً حتى تعتمده الموارد**.

    ⚠️ فمؤشّرٌ يضعه مديرٌ ويقيس به فريقه بلا مراجعة يصير حكمًا بلا
    ضابط (قرار جواد).
    """
    from apps.employees.models import KPI, ApprovalState, KPIScale

    _require_enabled(department.company_id)

    code = (code or "").strip().upper()
    if not code or not (name_ar or "").strip():
        raise PerformanceError("الرمز والاسم مطلوبان")
    if KPI.objects.filter(company_id=department.company_id,
                          code=code).exists():
        raise PerformanceError("الرمز مستعمل")
    if scale not in KPIScale.values:
        raise PerformanceError("مقياس غير معروف")

    return KPI.objects.create(
        account_id=department.account_id,
        company_id=department.company_id,
        department=department, code=code, name_ar=name_ar.strip()[:200],
        description=description or "", kind=kind, scale=scale,
        direction=direction, unit=unit or "",
        default_target=default_target,
        state=ApprovalState.PENDING,
        created_by_employment_id=by_employment_id)


@transaction.atomic
def decide_kpi(*, kpi, approve, by_person_id=None, note=""):
    """اعتماد الموارد للمؤشّر أو رفضه."""
    from apps.employees.models import ApprovalState

    if kpi.state == ApprovalState.APPROVED and approve:
        raise PerformanceError("معتمدٌ بالفعل")

    kpi.state = (ApprovalState.APPROVED if approve
                 else ApprovalState.REJECTED)
    kpi.approved_by_person_id = by_person_id
    kpi.approved_at = timezone.now()
    kpi.decision_note = (note or "")[:255]
    kpi.save(update_fields=["state", "approved_by_person_id",
                            "approved_at", "decision_note",
                            "updated_at"])
    return kpi


# ══════════ الإسناد ══════════

@transaction.atomic
def assign(*, cycle, employment, kpi, target, weight):
    """
    يُسند مؤشّرًا لموظفٍ في دورة.

    ⚠️ **والمعتمَد وحده يُقاس به**، **ومجموع الأوزان لا يتجاوز
    ١٠٠**: فوزنٌ زائد يُجمّل النتيجة.
    """
    from django.db.models import Sum

    from apps.employees.models import KPIAssignment

    _require_enabled(cycle.company_id)

    if not cycle.is_open:
        raise PerformanceError("الدورة مغلقة")
    if not kpi.is_usable:
        raise PerformanceError(
            "المؤشّر غير معتمد — لا يُقاس به قبل اعتماد الموارد")

    weight = int(weight)
    if not 1 <= weight <= 100:
        raise PerformanceError("الوزن بين ١ و١٠٠")

    used = (KPIAssignment.objects
            .filter(cycle=cycle, employment=employment)
            .aggregate(t=Sum("weight"))["t"] or 0)
    if used + weight > 100:
        raise PerformanceError(
            f"مجموع الأوزان يتجاوز ١٠٠ — المستعمل {used}")

    return KPIAssignment.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        cycle=cycle, employment=employment, kpi=kpi,
        target=Decimal(str(target)), weight=weight)


@transaction.atomic
def enter_actual(*, assignment, actual, by_employment, note=""):
    """
    المشرف يُدخل الفعليّ لمن تحته.

    ⚠️ **ولا يُدخل أحدٌ لنفسه**: فمن يقيس نفسه لا يُحاسَب.
    """
    from apps.employees.models import ApprovalState

    _require_enabled(assignment.company_id)

    if not assignment.cycle.is_open:
        raise PerformanceError("الدورة مغلقة")
    if assignment.state == ApprovalState.APPROVED:
        raise PerformanceError("اعتُمد — لا يُعدَّل")
    if by_employment and by_employment.id == assignment.employment_id:
        raise PerformanceError(
            "لا تُدخل فعليّ نفسك — فمن يقيس نفسه لا يُحاسَب")

    assignment.actual = Decimal(str(actual))
    assignment.entered_by_employment_id = getattr(by_employment, "id",
                                                  None)
    assignment.entered_at = timezone.now()
    assignment.entry_note = (note or "")[:255]
    assignment.state = ApprovalState.PENDING
    assignment.save()
    return assignment


@transaction.atomic
def approve_actual(*, assignment, approve=True, by_person_id=None,
                   note=""):
    """
    اعتماد الموارد للمدخَل.

    ⚠️ **فالمدخَل لا يصير نتيجةً قبل مراجعته**.
    """
    from apps.employees.models import ApprovalState

    if assignment.actual is None:
        raise PerformanceError("لا فعليّ مُدخَل بعد")

    assignment.state = (ApprovalState.APPROVED if approve
                        else ApprovalState.REJECTED)
    assignment.approved_by_person_id = by_person_id
    assignment.approved_at = timezone.now()
    assignment.decision_note = (note or "")[:255]
    assignment.save(update_fields=["state", "approved_by_person_id",
                                   "approved_at", "decision_note",
                                   "updated_at"])
    return assignment


# ══════════ التقييم الذاتيّ والمجهول ══════════

def _fingerprint(cycle_id, author_id, subject_id):
    """
    بصمةٌ تمنع التكرار **بلا كشف الهوية**.

    ⚠️ فبلا هذا يُقيَّم المدير مرّاتٍ من شخصٍ واحد — **والبصمة
    تُطابق ولا تُفكّ**.
    """
    raw = f"{cycle_id}:{author_id}:{subject_id}:muatmd-upward"
    return hashlib.sha256(raw.encode()).hexdigest()


@transaction.atomic
def submit_self_review(*, cycle, employment, score, strengths="",
                       improvements="", comment=""):
    """الموظف يقيّم نفسه — **منسوبًا لصاحبه**، فهو عن نفسه."""
    from apps.employees.models import PeerReview, ReviewKind

    _require_enabled(cycle.company_id)

    if not cycle.is_open:
        raise PerformanceError("الدورة مغلقة")
    if not cycle.self_review_enabled:
        raise PerformanceError("التقييم الذاتيّ غير مفعَّل في الدورة")
    if not 1 <= int(score) <= 5:
        raise PerformanceError("التقدير من ١ إلى ٥")

    if PeerReview.objects.filter(
            cycle=cycle, kind=ReviewKind.SELF,
            subject_employment=employment).exists():
        raise PerformanceError("قيّمتَ نفسك في هذه الدورة")

    return PeerReview.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        cycle=cycle, kind=ReviewKind.SELF,
        author_employment=employment,
        subject_employment=employment,
        score=int(score), strengths=strengths or "",
        improvements=improvements or "", comment=comment or "")


@transaction.atomic
def submit_upward_review(*, cycle, author_employment, manager_employment,
                         score, strengths="", improvements="",
                         comment=""):
    """
    الموظف يقيّم مديره — ⚠️⚠️ **مجهولًا**.

    **فلا يُحفظ اسم صاحبه**: لو رآه المدير باسمه لم يصدق أحد (قرار
    جواد).
    """
    from apps.employees.models import PeerReview, ReviewKind

    _require_enabled(cycle.company_id)

    if not cycle.is_open:
        raise PerformanceError("الدورة مغلقة")
    if not cycle.upward_review_enabled:
        raise PerformanceError("تقييم المديرين غير مفعَّل في الدورة")
    if author_employment.id == manager_employment.id:
        raise PerformanceError("هذا تقييمٌ ذاتيّ لا تقييم مدير")
    if not 1 <= int(score) <= 5:
        raise PerformanceError("التقدير من ١ إلى ٥")

    fp = _fingerprint(cycle.id, author_employment.id,
                      manager_employment.id)
    if PeerReview.objects.filter(cycle=cycle, author_fingerprint=fp
                                 ).exists():
        raise PerformanceError("قيّمتَ هذا المدير في الدورة")

    return PeerReview.objects.create(
        account_id=author_employment.account_id,
        company_id=author_employment.company_id,
        cycle=cycle, kind=ReviewKind.UPWARD,
        author_employment=None,               # ⚠️ مجهولٌ دائمًا
        subject_employment=manager_employment,
        author_fingerprint=fp,
        score=int(score), strengths=strengths or "",
        improvements=improvements or "", comment=comment or "")


def upward_summary(cycle, manager_employment, min_reviews=3):
    """
    خلاصةُ تقييم مديرٍ — **مجمَّعةً لا مفصَّلة**.

    ⚠️ **ولا تُعرض دون حدٍّ أدنى**: فثلاثةٌ يُخفون بعضهم، وواحدٌ
    يُعرَف بالضرورة.
    """
    from django.db.models import Avg, Count

    from apps.employees.models import PeerReview, ReviewKind

    qs = PeerReview.objects.filter(
        cycle=cycle, kind=ReviewKind.UPWARD,
        subject_employment=manager_employment)
    agg = qs.aggregate(n=Count("id"), avg=Avg("score"))

    if (agg["n"] or 0) < min_reviews:
        return {"count": agg["n"] or 0, "average": None,
                "comments": [],
                "note": f"تُعرض عند {min_reviews} تقييماتٍ فأكثر — "
                        "حمايةً لهوية المقيّمين"}

    return {
        "count": agg["n"],
        "average": round(float(agg["avg"]), 2),
        "comments": [c for c in qs.values_list("comment", flat=True)
                     if (c or "").strip()],
    }


# ══════════ النتيجة ══════════

def final_score(cycle, employment):
    """
    النتيجة الموزونة — **من المعتمَد وحده**.

    ⚠️ فمدخَلٌ لم يُراجَع ليس نتيجة.
    """
    from apps.employees.models import (
        ApprovalState, BehaviorRating, KPIAssignment)

    rows = (KPIAssignment.objects
            .filter(cycle=cycle, employment=employment,
                    state=ApprovalState.APPROVED)
            .select_related("kpi"))

    total_w, acc = 0, ZERO
    details = []
    for a in rows:
        sc = a.score
        if sc is None:
            continue
        total_w += a.weight
        acc += sc * Decimal(a.weight)
        details.append({"kpi": a.kpi.name_ar, "weight": a.weight,
                        "target": str(a.target), "actual": str(a.actual),
                        "score": round(float(sc), 1)})

    kpi_score = (acc / Decimal(total_w)) if total_w else None

    beh = BehaviorRating.objects.filter(cycle=cycle,
                                        employment=employment)
    beh_avg = None
    if beh.exists():
        beh_avg = sum(b.score for b in beh) / beh.count()

    return {
        "kpi_score": (round(float(kpi_score), 1)
                      if kpi_score is not None else None),
        "weight_covered": total_w,
        "behavior_average": (round(beh_avg, 2)
                             if beh_avg is not None else None),
        "details": details,
        # ⚠️ **والأثر تقريرٌ فقط** — لا مال (قرار جواد)
        "affects_pay": False,
    }
