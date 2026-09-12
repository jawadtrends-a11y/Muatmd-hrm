"""
مطالبات المصروفات (ق-139).

⚠️ **المصروف يُثبَت لا يُدّعى**: الفاتورة إلزامية، فتعويضٌ بلا
إثبات يفتح بابًا لا يُغلق.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class ExpenseError(Exception):
    """سببٌ يُعرض للمستخدم كما هو."""


def _next_no(company_id):
    """رقم المطالبة — أقصى مستعمل + ١."""
    from apps.payroll.models import ExpenseClaim

    year = timezone.localdate().year
    prefix = f"EXP-{year}-"
    last = (ExpenseClaim.objects
            .filter(company_id=company_id, claim_no__startswith=prefix)
            .order_by("-claim_no").values_list("claim_no", flat=True)
            .first())
    n = int(last.rsplit("-", 1)[-1]) if last else 0
    return f"{prefix}{n + 1:05d}"


def month_total(employment, category, year, month, exclude_id=None):
    """ما طُولب به في هذه الفئة هذا الشهر — للسقف الشهريّ."""
    from django.db.models import Sum

    from apps.payroll.models import ExpenseClaim, ExpenseStatus

    qs = ExpenseClaim.objects.filter(
        employment=employment, category=category,
        spent_on__year=year, spent_on__month=month,
        status__in=[ExpenseStatus.PENDING, ExpenseStatus.APPROVED,
                    ExpenseStatus.SETTLED])
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.aggregate(t=Sum("amount"))["t"] or ZERO


@transaction.atomic
def submit(*, employment, category, spent_on, amount, description,
           receipt_url):
    """
    يقدّم مطالبةً بتعويض مصروف.

    ⚠️ **والفاتورة إلزامية** — فالمصروف يُثبَت لا يُدّعى.
    """
    from apps.payroll.models import (
        ExpenseClaim, ExpenseStatus, PayrollSettings)

    st = PayrollSettings.objects.filter(
        company_id=employment.company_id).first()
    if st is None:
        raise ExpenseError("لا إعدادات رواتب لهذه الشركة")
    if not st.expenses_enabled:
        raise ExpenseError(
            "المصروفات غير مفعَّلة — تُفعَّل من إعدادات الرواتب")

    if not category.is_active:
        raise ExpenseError("الفئة معطَّلة")
    if not (receipt_url or "").strip():
        raise ExpenseError("أرفق الفاتورة — فالمصروف يُثبَت لا يُدّعى")
    if not (description or "").strip():
        raise ExpenseError("بيّن ما صُرف عليه")

    try:
        amt = Decimal(str(amount))
    except (InvalidOperation, TypeError):
        raise ExpenseError("مبلغ غير صالح")
    if amt <= 0:
        raise ExpenseError("المبلغ مطلوب")

    today = timezone.localdate()
    if spent_on > today:
        raise ExpenseError("لا مطالبة بمصروفٍ لم يقع بعد")

    # ⚠️ **وقِدَم المطالبة محدود**: فمطالبةٌ بعد سنة يتعذّر
    # التحقّق منها، ودفترها أُغلق.
    age = (today - spent_on).days
    if st.expense_max_age_days and age > st.expense_max_age_days:
        raise ExpenseError(
            f"مضى على المصروف {age} يومًا — والحدّ "
            f"{st.expense_max_age_days}")

    if category.max_per_claim and amt > category.max_per_claim:
        raise ExpenseError(
            f"يتجاوز سقف {category.name_ar}: {category.max_per_claim}")

    if category.max_per_month:
        used = month_total(employment, category,
                           spent_on.year, spent_on.month)
        if used + amt > category.max_per_month:
            raise ExpenseError(
                f"يتجاوز سقف الشهر لـ{category.name_ar}: "
                f"المستعمل {used} من {category.max_per_month}")

    claim = ExpenseClaim.objects.create(
        account_id=employment.account_id,
        company_id=employment.company_id,
        claim_no=_next_no(employment.company_id),
        employment=employment, category=category,
        spent_on=spent_on, amount=amt,
        description=description.strip()[:255],
        receipt_url=receipt_url.strip(),
        status=ExpenseStatus.PENDING)

    logger.info("مطالبة مصروف %s بمبلغ %s", claim.claim_no, amt)
    return claim


@transaction.atomic
def decide(*, claim, approve, by_person_id=None, note=""):
    """
    يعتمد المطالبة أو يرفضها.

    ⚠️ **والمرفوضة لا تُصرف**: فالقرار يُحترم، ولا يُلتفّ عليه
    بتغيير الحالة.
    """
    from apps.payroll.models import ExpenseStatus

    if claim.status != ExpenseStatus.PENDING:
        raise ExpenseError(
            f"المطالبة {claim.get_status_display()} — لا تُعاد")

    claim.status = (ExpenseStatus.APPROVED if approve
                    else ExpenseStatus.REJECTED)
    claim.decided_by_person_id = by_person_id
    claim.decided_at = timezone.now()
    claim.decision_note = (note or "")[:255]
    claim.save(update_fields=["status", "decided_by_person_id",
                              "decided_at", "decision_note",
                              "updated_at"])
    return claim


@transaction.atomic
def settle(*, claim, method=None, payroll_run_type="", paid_on=None,
           paid_note=""):
    """
    يسجّل صرف المطالبة — **المعتمدة وحدها**.

    وخارج المسير تنتهي مسؤوليتنا بالتوثيق (ق-134).
    """
    from apps.payroll.models import ExpenseStatus, PayrollSettings

    if claim.status != ExpenseStatus.APPROVED:
        raise ExpenseError(
            "لا تُصرف إلا المعتمدة — والمرفوضة قرارٌ يُحترم")

    st = PayrollSettings.objects.filter(
        company_id=claim.company_id).first()
    claim.method = method or (st.expense_default_method if st
                              else "payroll")

    if claim.method == "outside":
        claim.paid_on = paid_on or timezone.localdate()
        claim.paid_note = (paid_note or "")[:255]
        claim.status = ExpenseStatus.SETTLED
    else:
        claim.payroll_run_type = payroll_run_type or "regular"

    claim.save()
    return claim
