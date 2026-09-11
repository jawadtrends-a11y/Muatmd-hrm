"""
نشر السياسات وتتبّع الإقرار بها (ق-129).

⚠️ **سياسةٌ بلا إقرارٍ موثَّق لا يُحتجّ بها** — والإقرار بختم
وقته هو الحجّة.
"""
import logging
from datetime import date

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class PolicyError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def audience_queryset(policy, base=None):
    """
    الموظفون المعنيّون بهذه السياسة.

    ⚠️ **النشطون وحدهم**: من أُنهيت خدمته لا يُطالَب بإقرار، وعدّه
    في «لم يُقرّوا» يجعل اللوحة لا تخلو أبدًا.
    """
    from apps.employees.models import Employment, EmploymentStatus
    from apps.core.models import PolicyAudience

    qs = base if base is not None else Employment.objects.all()
    qs = qs.filter(company_id=policy.company_id,
                   status=EmploymentStatus.ACTIVE)

    if policy.audience == PolicyAudience.DEPARTMENT and policy.department_id:
        qs = qs.filter(department_id=policy.department_id)
    elif policy.audience == PolicyAudience.BRANCH and policy.branch_id:
        qs = qs.filter(branch_id=policy.branch_id)
    return qs


@transaction.atomic
def publish(*, policy, by_person_id=None):
    """
    ينشر السياسة فتظهر لمن تخصّهم.

    ⚠️ **ولا تُنشر بلا نصّ ولا تاريخ سريان**: فسياسةٌ فارغة تُطالَب
    بالإقرار بها.
    """
    if not (policy.body_ar or "").strip():
        raise PolicyError("لا نصّ للسياسة")
    if policy.effective_from is None:
        raise PolicyError("تاريخ السريان مطلوب")

    policy.is_published = True
    policy.published_at = timezone.now()
    policy.published_by_person_id = by_person_id
    policy.save(update_fields=["is_published", "published_at",
                               "published_by_person_id", "updated_at"])
    logger.info("نُشرت السياسة %s نسخة %s", policy.code, policy.version)
    return policy


@transaction.atomic
def bump_version(*, policy, body_ar=None, effective_from=None):
    """
    نسخةٌ جديدة — **تُبطل الإقرارات السابقة**.

    فمن أقرّ بالنسخة الأولى لا يُعدّ مُقرًّا بما عُدّل بعدها،
    وإلا احتجّت المنشأة بتوقيعٍ على نصٍّ لم يره.

    والإقرارات القديمة **لا تُحذف**: سجلٌّ يُراجَع، ومحوُه يُخفي
    ما جرى.
    """
    if body_ar is not None:
        policy.body_ar = body_ar
    if effective_from is not None:
        policy.effective_from = effective_from
    policy.version += 1
    policy.save(update_fields=["body_ar", "effective_from", "version",
                               "updated_at"])
    return policy


@transaction.atomic
def acknowledge(*, policy, employment, ip=None):
    """
    يُسجّل إقرار الموظف بالنسخة الحالية.

    ⚠️ **بالنسخة لا بالسياسة** — والتكرار لا يُنشئ ثانيًا.
    """
    from apps.core.models import PolicyAcknowledgement

    if not policy.is_published:
        raise PolicyError("السياسة غير منشورة")
    if not policy.requires_ack:
        raise PolicyError("هذه السياسة للاطّلاع ولا تحتاج إقرارًا")

    ack, created = PolicyAcknowledgement.objects.get_or_create(
        policy=policy, employment=employment, version=policy.version,
        defaults={"account_id": employment.account_id,
                  "company_id": employment.company_id, "ip": ip})
    return ack, created


def compliance(policy):
    """
    من أقرّ ومن لم يُقرّ — بالنسخة الحالية.

    فسياسةٌ نُشرت ولا يُعرف من قرأها بلا فائدة.
    """
    from apps.core.models import PolicyAcknowledgement

    people = list(audience_queryset(policy)
                  .select_related("person", "department"))
    acked = set(PolicyAcknowledgement.objects.filter(
        policy=policy, version=policy.version
    ).values_list("employment_id", flat=True))

    done, pending = [], []
    for e in people:
        row = {"employment_id": e.id, "employee_no": e.employee_no,
               "name": e.person.display_name,
               "department": getattr(e.department, "name_ar", "") or ""}
        (done if e.id in acked else pending).append(row)

    total = len(people)
    return {
        "version": policy.version,
        "total": total,
        "acknowledged": len(done),
        "pending": len(pending),
        "rate": round(len(done) * 100 / total) if total else 0,
        "done_rows": done,
        "pending_rows": pending,
    }


def my_policies(employment):
    """
    سياسات هذا الموظف — بحالة إقراره بكلٍّ.

    ⚠️ **وما لم يُقرّ به يُصدَّر أوّلًا**: فالقائمة ترتيبُها
    تنبيهٌ لا مجرّد عرض.
    """
    from apps.core.models import Policy, PolicyAcknowledgement

    qs = Policy.objects.filter(
        company_id=employment.company_id, is_published=True,
        effective_from__lte=date.today())

    mine = []
    acked = dict(PolicyAcknowledgement.objects.filter(
        employment=employment
    ).values_list("policy_id", "version"))

    for p in qs:
        if employment.id not in set(
                audience_queryset(p).values_list("id", flat=True)):
            continue
        ok = acked.get(p.id) == p.version
        mine.append({
            "id": p.id, "code": p.code, "title_ar": p.title_ar,
            "version": p.version,
            "effective_from": p.effective_from,
            "requires_ack": p.requires_ack,
            "acknowledged": ok or not p.requires_ack,
            "needs_ack": p.requires_ack and not ok,
        })

    mine.sort(key=lambda r: (not r["needs_ack"], r["title_ar"]))
    return mine
