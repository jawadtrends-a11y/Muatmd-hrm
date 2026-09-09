"""
بوابة المزايا — البوابة الأولى من الثلاث.

    1. هل باقة الشركة تشمل الميزة؟   ← هنا
    2. هل دور المستخدم يملك الصلاحية؟ ← Gate
    3. أي صفوف يُسمح برؤيتها؟          ← Scope + RLS

خطأ الميزة يرجع 402 لا 403 — لأن «باقتك لا تشمل هذا، هذه الترقية»
رسالة مختلفة تمامًا عن «راجع مديرك».
"""
from django.core.cache import cache
from rest_framework.exceptions import APIException

from apps.core.features.catalog import CORE_FEATURE_KEYS, FEATURE_KEYS

CACHE_TTL = 300


class FeatureNotInPlan(APIException):
    status_code = 402          # Payment Required
    default_code = "feature_not_in_plan"
    default_detail = "هذه الميزة غير متاحة في باقتكم الحالية"


class UnknownFeature(ValueError):
    """مفتاح ميزة غير مسجّل — خطأ برمجي لا حالة تشغيل."""


class Features:
    """مصدر الحقيقة الوحيد: هل هذه الميزة متاحة لهذه الشركة؟"""

    @staticmethod
    def _cache_key(company_id):
        return f"features:company:{company_id}"

    @classmethod
    def bundle(cls, company_id: int) -> dict:
        """حزمة مزايا الشركة، مخزّنة مؤقتًا."""
        if company_id is None:
            return {}
        key = cls._cache_key(company_id)
        cached = cache.get(key)
        if cached is not None:
            return cached

        # ⚠️ ق-117: الاشتراك في **AccountSubscription** لا
        # CompanySubscription — والثاني مهجور فارغ. فكانت البوّابة
        # تقرأ جدولًا خاويًا وتُرجع المزايا الأساسية للجميع:
        # **الباقة أسعارٌ بلا أثر**، ومن دفع للأساسية استعمل مزايا
        # المؤسسية.
        from apps.accounts.models import Company
        from apps.accounts.models_billing_v2 import (
            AccountSubscription, SubscriptionState)

        # ق-118: **لا مزايا مجّانية دائمة** (قرار جواد) — والستّ
        # التي كانت «أساسية مجّانية» هي **الباقة الأساسية** نفسها،
        # تُنال بالاشتراك. والمجّانيّ الوحيد تجربةُ سبعة أيام عليها.
        #
        # فبلا اشتراك سارٍ لا تُفتح ميزة: من انتهى اشتراكه يقرأ ولا
        # يعمل، وإلا بقي لبّ النظام مجّانًا فأُفرغ الاشتراك من معناه.
        bundle = {}
        account_id = (Company.objects.filter(id=company_id)
                      .values_list("account_id", flat=True).first())
        sub = (AccountSubscription.objects
               .filter(account_id=account_id,
                       state__in=[SubscriptionState.TRIAL,
                                  SubscriptionState.ACTIVE,
                                  SubscriptionState.PAST_DUE,
                                  SubscriptionState.GRACE])
               .select_related("plan").first())
        # التجربة بلا باقة مختارة تُمنح **الأساسية** — أدنى المعروضة
        # ترتيبًا، فالمجرّب يرى ما سيشتريه لا أكثر.
        if sub and sub.plan_id is None:
            if sub.state == SubscriptionState.TRIAL:
                from apps.accounts.models_billing import Plan
                trial_plan = (Plan.objects
                              .filter(is_public=True, is_active=True)
                              .order_by("tier_order", "id").first())
                if trial_plan is not None:
                    for pf in trial_plan.features.all():
                        bundle[pf.feature_key] = (
                            True if pf.value == "true"
                            else False if pf.value == "false"
                            else pf.value)
            sub = None
        if sub:
            for pf in sub.plan.features.all():
                bundle[pf.feature_key] = (
                    True if pf.value == "true"
                    else False if pf.value == "false"
                    else pf.value
                )
        cache.set(key, bundle, CACHE_TTL)
        return bundle

    @classmethod
    def invalidate(cls, company_id: int):
        """يُستدعى عند تغيير الباقة أو الاشتراك."""
        cache.delete(cls._cache_key(company_id))

    @classmethod
    def value(cls, company_id: int, feature_key: str):
        if feature_key not in FEATURE_KEYS:
            raise UnknownFeature(f"ميزة غير مسجّلة: {feature_key}")
        return cls.bundle(company_id).get(feature_key)

    @classmethod
    def enabled(cls, company_id: int, feature_key: str) -> bool:
        v = cls.value(company_id, feature_key)
        return v not in (None, False, "false", "0", 0)

    @classmethod
    def limit(cls, company_id: int, feature_key: str, default: int = 0) -> int:
        v = cls.value(company_id, feature_key)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    @classmethod
    def require(cls, company_id: int, feature_key: str):
        if not cls.enabled(company_id, feature_key):
            raise FeatureNotInPlan({
                "detail": "هذه الميزة غير متاحة في باقتكم الحالية",
                "feature": feature_key,
                "upgrade_url": "/settings/subscription",
            })
        return True


def requires_feature(feature_key: str):
    """مزخرِف للـviews — يُستخدم مع requires_permission لا بدلًا منه."""
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ctx = getattr(request, "account_ctx", None)
            company_id = getattr(ctx, "active_company_id", None)
            Features.require(company_id, feature_key)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def upgrade_hint(company_id: int, feature_key: str) -> dict | None:
    """
    أصغر باقة تفتح هذه الميزة (ق-117).

    **لا أي باقة أعلى**: من هو على الأساسية ويريد ميزةً توفّرها
    «المميزة» يُرشَّح للمميزة لا للمؤسسية — فترشيحُ الأغلى بلا
    داعٍ يُنفّره، وقد لا تكون فيها أصلًا.

    ويرجع None إن كانت الميزة مفتوحة له، أو لم تفتحها باقةٌ
    معروضة.
    """
    from apps.accounts.models import Company
    from apps.accounts.models_billing import Plan

    if Features.enabled(company_id, feature_key):
        return None

    account_id = (Company.objects.filter(id=company_id)
                  .values_list("account_id", flat=True).first())
    current_order = -1
    from apps.accounts.models_billing_v2 import AccountSubscription
    sub = (AccountSubscription.objects
           .filter(account_id=account_id).select_related("plan").first())
    if sub and sub.plan:
        current_order = sub.plan.tier_order

    for plan in Plan.objects.filter(
            is_public=True, is_active=True).order_by("tier_order", "id"):
        if plan.tier_order <= current_order:
            continue
        pf = plan.features.filter(feature_key=feature_key).first()
        if pf is None:
            continue
        # القيمة العددية تُقبل كذلك: حدٌّ أكبر ترقيةٌ أيضًا
        if pf.value in ("false", "0", ""):
            continue
        tier = plan.price_tiers.order_by("from_employees").first()
        return {
            "feature": feature_key,
            "plan_id": plan.id,
            "plan_code": plan.code,
            "plan_name": plan.name_ar,
            "monthly": (str(tier.price_per_employee_monthly)
                        if tier else None),
            "annual": (str(tier.price_per_employee_yearly)
                       if tier else None),
            "upgrade_url": "/subscribe",
        }
    return None
