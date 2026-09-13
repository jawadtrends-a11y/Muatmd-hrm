"""
التدريب والدورات (ق-149).

⚠️⚠️ **وميزانية التدريب ثلاثية المصدر**: ميزانية الموظف إن
أُدخلت، فميزانية مرتبته، فبلا سقف — **والفارغ لا يعني صفرًا**.
"""
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class TrainingError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def _require_enabled(company_id):
    from apps.core.features.gate import Features

    if not Features.enabled(company_id, "training"):
        raise TrainingError("التدريب غير متاح في باقتكم")


def budget_for(employment):
    """
    سقفُ تدريب الموظف السنويّ — **أو None إن لم يكن**.

    ⚠️ **والترتيب: الموظف، فمرتبته، فبلا سقف** — والفارغ لا يعني
    صفرًا، بل «لا قيد من هنا» (قرار جواد).
    """
    if employment.training_budget_override is not None:
        return employment.training_budget_override

    grade = getattr(employment, "job_grade", None)
    if grade is not None and grade.training_budget is not None:
        return grade.training_budget

    return None


def spent_this_year(employment, year=None, exclude_id=None):
    """
    ما حُسب على ميزانيته هذه السنة.

    ⚠️ **والمعتمَد يُحسب ولو لم يحضر** — فالمقعد حُجز ودُفع.
    """
    from django.db.models import Sum

    from apps.employees.models import NominationState, TrainingNomination

    year = year or timezone.localdate().year
    qs = TrainingNomination.objects.filter(
        employment=employment,
        state__in=[NominationState.APPROVED, NominationState.ATTENDED,
                   NominationState.NO_SHOW],
        scheduled_on__year=year)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.aggregate(t=Sum("cost"))["t"] or ZERO


def budget_state(employment, year=None):
    """حالة الميزانية — للعرض والتحقّق."""
    cap = budget_for(employment)
    used = spent_this_year(employment, year)
    return {
        "budget": str(cap) if cap is not None else None,
        "used": str(used),
        "remaining": (str(max(cap - used, ZERO))
                      if cap is not None else None),
        "unlimited": cap is None,
    }


@transaction.atomic
def nominate(*, course, employment, scheduled_on=None,
             by_employment_id=None):
    """
    المدير يرشّح موظفًا لدورةٍ متاحة.

    ⚠️ **والتكلفة تُجمَّد عند الترشيح**: فتغيّر سعر الدورة بعدها
    لا يغيّر ما احتُسب على الميزانية.
    """
    from apps.employees.models import NominationState, TrainingNomination

    _require_enabled(employment.company_id)

    if not course.is_active:
        raise TrainingError("الدورة غير متاحة")

    live = TrainingNomination.objects.filter(
        course=course, employment=employment,
        state__in=[NominationState.PENDING, NominationState.APPROVED]
    ).first()
    if live:
        raise TrainingError("الموظف مرشَّحٌ لهذه الدورة بالفعل")

    return TrainingNomination.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        course=course, employment=employment,
        scheduled_on=scheduled_on or timezone.localdate(),
        cost=course.cost,
        state=NominationState.PENDING,
        nominated_by_employment_id=by_employment_id)


def check_budget(nomination):
    """
    أيتجاوز الترشيح ميزانيته؟

    ⚠️ **ويُنبَّه ولا يُمنع**: فحالاتٌ تستحقّ التجاوز، والموارد
    تقرّر.
    """
    cap = budget_for(nomination.employment)
    if cap is None:
        return {"exceeds": False, "warning": ""}

    year = (nomination.scheduled_on or timezone.localdate()).year
    used = spent_this_year(nomination.employment, year,
                           exclude_id=nomination.id)
    cost = Decimal(str(nomination.cost or 0))

    if used + cost > cap:
        return {
            "exceeds": True,
            "warning": (f"⚠️ يتجاوز ميزانية التدريب: المستعمل {used} "
                        f"من {cap}، وهذه الدورة {cost}"),
            "budget": str(cap), "used": str(used), "cost": str(cost),
        }
    return {"exceeds": False, "warning": ""}


@transaction.atomic
def decide_nomination(*, nomination, approve, by_person_id=None,
                      note=""):
    """
    اعتماد الموارد للترشيح أو رفضه.

    ⚠️ **فترشيحٌ بلا مراجعة يصرف ميزانيةً بلا ضابط**.
    """
    from apps.employees.models import NominationState

    if nomination.state != NominationState.PENDING:
        raise TrainingError(
            f"الترشيح {nomination.get_state_display()} — لا يُعاد")

    nomination.state = (NominationState.APPROVED if approve
                        else NominationState.REJECTED)
    nomination.decided_by_person_id = by_person_id
    nomination.decided_at = timezone.now()
    nomination.decision_note = (note or "")[:255]
    nomination.save(update_fields=["state", "decided_by_person_id",
                                   "decided_at", "decision_note",
                                   "updated_at"])
    return nomination


@transaction.atomic
def record_result(*, nomination, attended, score=None, passed=None,
                  certificate_url="", note=""):
    """
    تسجيل الحضور والنتيجة.

    ⚠️ **ولا نتيجة لغير المعتمَد**: فمن لم يُعتمد ترشيحه لم يحضر.
    """
    from apps.employees.models import NominationState

    if nomination.state not in (NominationState.APPROVED,
                                NominationState.ATTENDED,
                                NominationState.NO_SHOW):
        raise TrainingError(
            "لا نتيجة إلا لترشيحٍ معتمد")

    nomination.state = (NominationState.ATTENDED if attended
                        else NominationState.NO_SHOW)
    if attended:
        nomination.score = (Decimal(str(score))
                            if score not in (None, "") else None)
        nomination.passed = passed
        nomination.certificate_url = (certificate_url or "")[:500]
        nomination.completed_on = timezone.localdate()
    nomination.result_note = (note or "")[:255]
    nomination.save()
    return nomination


@transaction.atomic
def request_course(*, employment, course_name, justification,
                   provider="", estimated_cost=None, reference_url=""):
    """
    الموظف يطلب دورةً **غير متوفّرة** (قرار جواد).

    ⚠️ **والمبرّر إلزاميّ**: فطلبٌ بلا مبرّر لا يُدرَس.
    """
    from apps.employees.models import TrainingCourse, TrainingRequest

    _require_enabled(employment.company_id)

    name = (course_name or "").strip()
    if not name:
        raise TrainingError("اسم الدورة مطلوب")
    if not (justification or "").strip():
        raise TrainingError("بيّن مبرّر الطلب — فطلبٌ بلا مبرّر لا يُدرَس")

    # ⚠️ **والمتوفّر يُرشَّح له لا يُطلَب**
    exists = TrainingCourse.objects.filter(
        company_id=employment.company_id, is_active=True,
        name_ar__iexact=name).first()
    if exists:
        raise TrainingError(
            f"«{exists.name_ar}» متوفّرة — اطلب من مديرك ترشيحك لها")

    return TrainingRequest.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        employment=employment, course_name=name[:200],
        provider=(provider or "")[:150],
        estimated_cost=(Decimal(str(estimated_cost))
                        if estimated_cost not in (None, "") else None),
        justification=justification.strip(),
        reference_url=(reference_url or "")[:500])


@transaction.atomic
def decide_request(*, request_obj, approve, by_person_id=None, note="",
                   create_course=False, code=""):
    """
    قرار الموارد في طلب الموظف — **وقد تُضيفه للكتالوج**.
    """
    from apps.employees.models import (
        NominationState, TrainingCourse)

    if request_obj.state != NominationState.PENDING:
        raise TrainingError("حُسم الطلب — لا يُعاد")

    request_obj.state = (NominationState.APPROVED if approve
                         else NominationState.REJECTED)
    request_obj.decided_by_person_id = by_person_id
    request_obj.decided_at = timezone.now()
    request_obj.decision_note = (note or "")[:255]

    if approve and create_course:
        c = (code or "").strip().upper() or f"REQ{request_obj.id}"
        if TrainingCourse.objects.filter(
                company_id=request_obj.company_id, code=c).exists():
            raise TrainingError("رمز الدورة مستعمل")
        request_obj.created_course = TrainingCourse.objects.create(
            account_id=request_obj.account_id,
            company_id=request_obj.company_id,
            code=c, name_ar=request_obj.course_name,
            provider=request_obj.provider,
            cost=request_obj.estimated_cost)

    request_obj.save()
    return request_obj
