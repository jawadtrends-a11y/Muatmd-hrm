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

        from apps.accounts.models_billing import CompanySubscription

        bundle = {k: True for k in CORE_FEATURE_KEYS}
        sub = (CompanySubscription.objects
               .filter(company_id=company_id,
                       status__in=["trial", "active", "past_due", "grace"])
               .select_related("plan").first())
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
