"""
اختيار الاسم بلغة الطلب (ق-64).

النماذج تحمل name_ar وname_en وname_ur — لكن المسارات كانت
ترسل العربي وحده، فيرى مستخدم الإنجليزية أسماء عربية وسط
واجهة إنجليزية.

**القاعدة:** الخادم يختار، لا الواجهة. فالواجهة ترسل لغتها
في ترويسة Accept-Language، والخادم يرجع الاسم جاهزًا.

**والارتداد للعربية مقصود:** الاسم العربي هو المُدخَل دائمًا،
والإنجليزي اختياري — فالفراغ يعني «لم يُترجم» لا «لا اسم».
"""

SUPPORTED = ("ar", "en", "ur", "hi", "tl", "bn")


def request_locale(request) -> str:
    """
    لغة الطلب — من الترويسة أو تفضيل المستخدم.

    الأولوية: معامل صريح ← ترويسة ← تفضيل الشخص ← العربية.
    """
    explicit = (request.GET.get("lang") or "").strip().lower()
    if explicit in SUPPORTED:
        return explicit

    header = (request.META.get("HTTP_ACCEPT_LANGUAGE") or "").lower()
    for code in SUPPORTED:
        if header.startswith(code):
            return code

    person = getattr(getattr(request, "user", None), "person", None)
    pref = getattr(person, "preferred_locale", "") or ""
    if pref in SUPPORTED:
        return pref

    return "ar"


def localized(obj, field="name", locale="ar", default=""):
    """
    اسم الكائن بلغة معيّنة، مع ارتداد للعربية.

        localized(dept, locale="en")  →  name_en أو name_ar

    الأردية والهندية وغيرها ترتد للإنجليزية ثم العربية — فمن
    لا يقرأ العربية يرى الإنجليزية على الأقل.
    """
    if obj is None:
        return default

    chain = {
        "ar": ("ar",),
        "en": ("en", "ar"),
        "ur": ("ur", "en", "ar"),
        "hi": ("hi", "en", "ar"),
        "tl": ("tl", "en", "ar"),
        "bn": ("bn", "en", "ar"),
    }.get(locale, ("ar",))

    for code in chain:
        value = getattr(obj, f"{field}_{code}", "") or ""
        if value:
            return value

    return getattr(obj, field, "") or default


class LocaleMixin:
    """
    يضيف .localized_name للنماذج ثنائية اللغة.

    يُستخدم حين يكون السياق معروفًا بلا تمرير locale.
    """

    def localized_name(self, locale="ar"):
        return localized(self, "name", locale)
