"""
لوحة السوبر أدمن (ق-46، ق-51).

**الافتراض: ملخص لا بيانات.** الدخول لبيانات العميل عبر الانتحال.
**كل عملية تحتاج قدرة محددة** — والأدوار الثلاثة تُفحص هنا.
"""
from datetime import date, timedelta
from decimal import Decimal

from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.models import Account, Company, Plan
from apps.accounts.models_billing_v2 import (
    AccountSubscription, BillingCycle, Discount, DiscountKind, DiscountScope,
    Invoice, InvoiceStatus, Payment, SubscriptionState,
)
from apps.accounts.models_platform import get_settings
from apps.accounts.services import billing_v2 as billing
from apps.core.tenancy.context import account_scope


def requires(capability):
    """
    يحدد القدرة المطلوبة للنقطة (ق-51).

    الأدوار الثلاثة: viewer يقرأ، support يفعّل ويمدّد،
    owner كل شيء. الفحص هنا لا في كل سطر.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            user = getattr(request, "platform_user", None)
            if user is None:
                return Response(
                    {"detail": "يلزم الدخول للوحة المنصة",
                     "code": "platform_auth_required"}, status=401)
            if not user.can(capability):
                return Response({
                    "detail": (f"دورك ({user.get_role_display()}) "
                               "لا يسمح بهذه العملية"),
                    "code": "insufficient_capability",
                    "required": capability,
                }, status=403)
            return view_func(request, *args, **kwargs)

        wrapper.__name__ = view_func.__name__
        wrapper.__doc__ = view_func.__doc__
        wrapper.required_capability = capability
        return wrapper
    return decorator


def _confirmed(request):
    """
    ق-46: تحذير صريح قبل كل كتابة في حساب عميل.

    الواجهة ترسل confirm=true بعد عرض التحذير — يمنع التعديل
    بالخطأ عند نسيان السياق.
    """
    return str(request.data.get("confirm", "")).lower() in ("1", "true", "yes")


def _need_confirm(account):
    return Response({
        "detail": (f"أنت على وشك التعديل في حساب العميل "
                   f"«{account.display_name_ar}» — أكّد للمتابعة"),
        "code": "confirmation_required",
        "account": account.display_name_ar,
    }, status=428)


def _log(request, action, *, account=None, detail=None, success=True):
    from apps.accounts.models_admin import PlatformAuditLog
    user = request.platform_user
    PlatformAuditLog.objects.create(
        user=user, user_name=user.full_name, action=action,
        target_account_id=account.id if account else None,
        target_label=account.display_name_ar if account else "",
        detail=detail or {}, success=success,
        ip_address=request.META.get("REMOTE_ADDR"))


# ══════════════════ لوحة المؤشرات ══════════════════

@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("dashboard.view")
def admin_dashboard(request):
    """مؤشرات المنصة — الشاشة الرئيسية."""
    from django.db.models import Count, Sum

    today = date.today()
    month_start = today.replace(day=1)

    subs = AccountSubscription.objects.values("state").annotate(n=Count("id"))
    revenue = Invoice.objects.filter(
        status=InvoiceStatus.PAID, paid_at__date__gte=month_start
    ).aggregate(total=Sum("total"))["total"] or Decimal("0")

    return Response({
        "accounts_total": Account.objects.count(),
        "subscriptions_by_state": {s["state"]: s["n"] for s in subs},
        "revenue_this_month": str(revenue),
        "overdue_invoices": Invoice.objects.filter(
            status=InvoiceStatus.ISSUED, due_date__lt=today).count(),
        "expiring_soon": AccountSubscription.objects.filter(
            state=SubscriptionState.ACTIVE,
            current_period_end__lte=today + timedelta(days=15),
            current_period_end__gte=today).count(),
        "failed_payments_this_month": Payment.objects.filter(
            status="failed", created_at__date__gte=month_start).count(),
    })


# ══════════════════ الحسابات ══════════════════

@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("accounts.view")
def accounts_list(request):
    """
    قائمة الحسابات بملخصاتها (ق-46).

    ملخص لا بيانات: عدد الموظفين وحالة الاشتراك — بلا رواتب
    ولا أسماء موظفين. الدخول للبيانات عبر الانتحال.
    """
    from apps.employees.models import Employment, EmploymentStatus

    rows = []
    for acc in Account.objects.all().order_by("-created_at"):
        with account_scope(acc.id):
            sub = AccountSubscription.objects.filter(account=acc).first()
            companies = Company.objects.filter(account=acc).count()
            employees = Employment.objects.filter(
                account=acc, status=EmploymentStatus.ACTIVE).count()
            unpaid = Invoice.objects.filter(
                account=acc, status=InvoiceStatus.ISSUED).count()

        end = billing.effective_end(sub) if sub else None
        rows.append({
            "account_id": acc.id, "slug": acc.slug,
            "name": acc.display_name_ar,
            "is_sandbox": acc.is_sandbox,
            "created_at": acc.created_at,
            "companies": companies, "employees": employees,
            "subscription": {
                "state": sub.state if sub else None,
                "state_label": (sub.get_state_display() if sub
                                else "بلا اشتراك"),
                "plan": sub.plan.name_ar if sub and sub.plan else None,
                "cycle": sub.get_cycle_display() if sub else None,
                "payment_method": (sub.get_payment_method_display()
                                   if sub else None),
                "period_end": sub.current_period_end if sub else None,
                "grace_until": sub.grace_until if sub else None,
                "days_left": (end - date.today()).days if end else None,
                "auto_renew": sub.auto_renew if sub else False,
            },
            "unpaid_invoices": unpaid,
        })

    states = {}
    for r in rows:
        s = r["subscription"]["state"] or "none"
        states[s] = states.get(s, 0) + 1

    return Response({"total": len(rows), "by_state": states,
                     "accounts": rows})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("accounts.view")
def account_detail(request, account_id):
    """تفاصيل حساب — اشتراكه وفواتيره ومدفوعاته."""
    from apps.employees.models import Employment, EmploymentStatus
    from apps.payroll.models import PayrollRun

    acc = Account.objects.filter(id=account_id).first()
    if acc is None:
        return Response({"detail": "الحساب غير موجود"}, status=404)

    with account_scope(acc.id):
        sub = AccountSubscription.objects.filter(account=acc).first()
        companies = [
            {"id": c.id, "code": c.code, "name": c.legal_name_ar,
             "employees": Employment.objects.filter(
                 company=c, status=EmploymentStatus.ACTIVE).count()}
            for c in Company.objects.filter(account=acc)
        ]
        runs = [
            {"run_no": r.run_no,
             "period": f"{r.period_year}-{r.period_month:02d}",
             "status": r.get_status_display(),
             "employees": r.employee_count}
            for r in PayrollRun.objects.filter(
                account=acc).order_by("-period_year", "-period_month")[:6]
        ]
        invoices = [
            {"id": i.id, "invoice_no": i.invoice_no, "total": str(i.total),
             "status": i.get_status_display(), "due": i.due_date,
             "paid_at": i.paid_at}
            for i in Invoice.objects.filter(account=acc).order_by("-id")[:12]
        ]
        payments = list(Payment.objects.filter(account=acc).order_by("-id")[:10])

    _log(request, "account.view", account=acc)

    return Response({
        "account": {"id": acc.id, "slug": acc.slug,
                    "name": acc.display_name_ar,
                    "is_sandbox": acc.is_sandbox,
                    "created_at": acc.created_at},
        "subscription": {
            "state": sub.state, "state_label": sub.get_state_display(),
            "plan": sub.plan.name_ar if sub.plan else None,
            "plan_code": sub.plan.code if sub.plan else None,
            "cycle": sub.cycle, "payment_method": sub.payment_method,
            "period_start": sub.current_period_start,
            "period_end": sub.current_period_end,
            "grace_until": sub.grace_until, "auto_renew": sub.auto_renew,
            "custom_price": (str(sub.custom_price)
                             if sub.custom_price else None),
            "setup_fee": str(sub.setup_fee_amount),
            "setup_fee_charged": sub.setup_fee_charged,
            "activation_note": sub.activation_note,
        } if sub else None,
        "companies": companies,
        "recent_runs": runs,
        "invoices": invoices,
        "payments": [
            {"id": p.id, "amount": str(p.amount),
             "status": p.get_status_display(), "method": p.source_type,
             "at": p.created_at, "recurring": p.is_recurring,
             "failure": p.failure_message}
            for p in payments
        ],
    })


# ══════════════════ إدارة الاشتراك ══════════════════

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("subscription.activate")
def admin_activate(request, account_id):
    """
    تفعيل إداري بلا دفع إلكتروني (ق-48).

    للشركات التي تدفع بتحويل بنكي — تُصدر لها فاتورة ضريبية
    يدويًا من «معتمد المحاسبي».
    """
    acc = Account.objects.filter(id=account_id).first()
    if acc is None:
        return Response({"detail": "الحساب غير موجود"}, status=404)
    if not _confirmed(request):
        return _need_confirm(acc)

    plan = Plan.objects.filter(code=request.data.get("plan_code", "")).first()
    if plan is None:
        return Response({"detail": "باقة غير معروفة"}, status=400)

    cycle = request.data.get("cycle", BillingCycle.MONTHLY)
    try:
        start = date.fromisoformat(
            request.data.get("period_start") or str(date.today()))
    except ValueError:
        return Response({"detail": "تاريخ غير صالح"}, status=400)

    with account_scope(acc.id):
        sub = AccountSubscription.objects.filter(account=acc).first()
        if sub is None:
            sub = billing.start_trial(acc)
        sub = billing.activate_manually(
            subscription=sub, plan=plan, cycle=cycle, period_start=start,
            activated_by=None,
            payment_method=request.data.get("payment_method"),
            note=request.data.get("note", ""),
            custom_price=(Decimal(str(request.data["custom_price"]))
                          if request.data.get("custom_price") else None),
            setup_fee=(Decimal(str(request.data["setup_fee"]))
                       if request.data.get("setup_fee") else None))

    _log(request, "subscription.activate", account=acc,
         detail={"plan": plan.code, "cycle": cycle,
                 "until": str(sub.current_period_end),
                 "note": request.data.get("note", "")})

    return Response({
        "state": sub.state, "plan": plan.name_ar,
        "period_end": sub.current_period_end,
        "payment_method": sub.get_payment_method_display(),
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("subscription.extend")
def admin_extend(request, account_id):
    """تمديد يدوي بلا حد (ق-48)."""
    acc = Account.objects.filter(id=account_id).first()
    if acc is None:
        return Response({"detail": "الحساب غير موجود"}, status=404)
    if not _confirmed(request):
        return _need_confirm(acc)

    try:
        until = date.fromisoformat(request.data["until"])
    except (KeyError, ValueError):
        return Response({"detail": "تاريخ التمديد مطلوب"}, status=400)

    with account_scope(acc.id):
        sub = AccountSubscription.objects.filter(account=acc).first()
        if sub is None:
            return Response({"detail": "لا اشتراك"}, status=404)
        try:
            billing.extend_grace(subscription=sub, until=until,
                                 extended_by=None,
                                 note=request.data.get("note", ""))
        except billing.BillingError as e:
            return Response({"detail": str(e)}, status=400)

    _log(request, "subscription.extend", account=acc,
         detail={"until": str(until), "note": request.data.get("note", "")})
    return Response({"grace_until": sub.grace_until, "state": sub.state})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("invoice.mark_paid")
def admin_mark_invoice_paid(request, invoice_id):
    """تعليم فاتورة مدفوعة يدويًا — عند التحويل البنكي (ق-48)."""
    inv = Invoice.objects.filter(id=invoice_id).first()
    if inv is None:
        return Response({"detail": "الفاتورة غير موجودة"}, status=404)

    acc = Account.objects.get(id=inv.account_id)
    if not _confirmed(request):
        return _need_confirm(acc)

    with account_scope(inv.account_id):
        billing.mark_paid(inv, actor=None,
                          note=request.data.get("note", "سداد يدوي"))

    _log(request, "invoice.mark_paid", account=acc,
         detail={"invoice_no": inv.invoice_no, "total": str(inv.total)})
    return Response({"invoice_no": inv.invoice_no, "status": inv.status})


# ══════════════════ الخصومات ══════════════════

@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("discounts.manage")
def admin_discounts(request):
    """إدارة الخصومات الثلاثة (ق-47)."""
    if request.method == "GET":
        return Response([
            {"id": d.id, "code": d.code, "name_ar": d.name_ar,
             "scope": d.scope, "scope_label": d.get_scope_display(),
             "kind": d.kind, "value": str(d.value),
             "account_id": d.account_id,
             "applies_to_cycle": d.applies_to_cycle,
             "covers_setup_fee": d.covers_setup_fee,
             "valid_from": d.valid_from, "valid_until": d.valid_until,
             "max_uses": d.max_uses, "used_count": d.used_count,
             "is_active": d.is_active}
            for d in Discount.objects.all().order_by("-created_at")
        ])

    code = (request.data.get("code") or "").strip().upper()
    if not code:
        return Response({"detail": "الكود مطلوب"}, status=400)
    if Discount.objects.filter(code__iexact=code).exists():
        return Response({"detail": f"الكود مستخدم: {code}"}, status=409)

    try:
        d = Discount.objects.create(
            code=code, name_ar=request.data.get("name_ar", code),
            scope=request.data.get("scope", DiscountScope.COUPON),
            kind=request.data.get("kind", DiscountKind.PERCENT),
            value=Decimal(str(request.data.get("value", 0))),
            account_id=request.data.get("account_id") or None,
            applies_to_cycle=request.data.get("applies_to_cycle", ""),
            covers_setup_fee=bool(request.data.get("covers_setup_fee")),
            valid_from=(date.fromisoformat(request.data["valid_from"])
                        if request.data.get("valid_from") else None),
            valid_until=(date.fromisoformat(request.data["valid_until"])
                         if request.data.get("valid_until") else None),
            max_uses=request.data.get("max_uses") or None,
            note=request.data.get("note", ""))
    except (ValueError, TypeError) as e:
        return Response({"detail": f"بيانات غير صالحة: {e}"}, status=400)

    _log(request, "discount.create",
         detail={"code": code, "value": str(d.value), "scope": d.scope})
    return Response({"id": d.id, "code": d.code}, status=201)


@api_view(["PUT", "DELETE"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("discounts.manage")
def admin_discount_detail(request, discount_id):
    """تعديل خصم أو تعطيله — إخفاء لا حذف (ق-46)."""
    d = Discount.objects.filter(id=discount_id).first()
    if d is None:
        return Response({"detail": "الخصم غير موجود"}, status=404)

    if request.method == "DELETE":
        d.is_active = False
        d.save(update_fields=["is_active", "updated_at"])
        _log(request, "discount.deactivate", detail={"code": d.code})
        return Response({"deactivated": True})

    for f in ("name_ar", "value", "valid_until", "max_uses",
              "is_active", "covers_setup_fee"):
        if f in request.data:
            setattr(d, f, request.data[f])
    d.save()
    _log(request, "discount.update", detail={"code": d.code})
    return Response({"id": d.id, "is_active": d.is_active})


# ══════════════════ إعدادات المنصة ══════════════════

@api_view(["GET", "PUT"])
@authentication_classes([])
@permission_classes([AllowAny])
@requires("platform.settings")
def platform_settings(request):
    """إعدادات المنصة — الضريبة والتجربة والمحاولات (ق-50)."""
    ps = get_settings()

    if request.method == "PUT":
        changed = {}
        for f in ("vat_rate", "vat_number", "trial_days",
                  "trial_max_employees", "grace_days_after_expiry",
                  "renewal_alert_monthly", "renewal_alert_annual",
                  "invoice_due_days", "manual_retry_limit",
                  "manual_retry_cooldown_hours", "auto_retry_hours",
                  "accounting_api_url", "accounting_enabled",
                  "support_email", "support_mobile"):
            if f in request.data:
                changed[f] = {"from": str(getattr(ps, f)),
                              "to": str(request.data[f])}
                setattr(ps, f, request.data[f])
        ps.save()
        if changed:
            _log(request, "platform.settings", detail=changed)

    return Response({
        "vat_rate": str(ps.vat_rate), "vat_number": ps.vat_number,
        "trial_days": ps.trial_days,
        "trial_max_employees": ps.trial_max_employees,
        "grace_days_after_expiry": ps.grace_days_after_expiry,
        "renewal_alert_monthly": ps.renewal_alert_monthly,
        "renewal_alert_annual": ps.renewal_alert_annual,
        "invoice_due_days": ps.invoice_due_days,
        "manual_retry_limit": ps.manual_retry_limit,
        "manual_retry_cooldown_hours": ps.manual_retry_cooldown_hours,
        "auto_retry_hours": ps.auto_retry_hours,
        "auto_retry_schedule": ps.auto_retry_schedule,
        "accounting_api_url": ps.accounting_api_url,
        "accounting_enabled": ps.accounting_enabled,
        "support_email": ps.support_email,
        "support_mobile": ps.support_mobile,
    })
