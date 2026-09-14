"""
ترقيم موحّد للقوائم (ق-166).

**قرار جواد:** نبني للمستقبل لا للحجم الحاليّ — **فشركةٌ بألف موظف
لا تُرسَل في ردٍّ واحد**.

⚠️⚠️ **وصيغةٌ واحدة لكل المسارات**: فترقيمٌ مختلفٌ في كل مسار
**يجعل الواجهة تخمّن**.
"""

#: الأحجام المتاحة — وتطابق ما تعرضه الواجهة
PAGE_SIZES = (10, 25, 50, 100)
DEFAULT_SIZE = 10

#: ⚠️ **سقفٌ صلب**: فطلبُ ٥٠٠٠٠ صفّ يُسقط الخادم — والسقف حمايةٌ
# لا تقييد.
MAX_SIZE = 200


def page_params(request, default_size=DEFAULT_SIZE,
                max_size=MAX_SIZE):
    """
    يقرأ `page` و`page_size` — **بقيمٍ آمنة دائمًا**.

    ⚠️ **وقيمةٌ خاطئة لا تُسقط الطلب**: فـ`page=abc` يرجع للأولى،
    **لا لخطأ ٥٠٠**.
    """
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        page = 1

    try:
        size = int(request.GET.get("page_size") or default_size)
    except (TypeError, ValueError):
        size = default_size

    return page, max(1, min(size, max_size))


def paginate(queryset, request, *, default_size=DEFAULT_SIZE,
             max_size=MAX_SIZE):
    """
    يقطّع قائمةً ويُرجع (الصفحة، البيانات الوصفية).

    ⚠️ **والعدّ قبل التقطيع**: فالواجهة تحتاج الإجمالي لترسم
    التنقّل — **وبلاه لا تعرف أثمّة صفحةٌ تالية**.

    ⚠️ **والصفحة تُقيَّد بالأقصى**: فمن طلب صفحةً ٩٩ في قائمةٍ من
    ثلاث **يرى الثالثة لا فراغًا**.
    """
    page, size = page_params(request, default_size, max_size)

    total = queryset.count() if hasattr(queryset, "count") else len(
        queryset)
    pages = max(1, -(-total // size))
    page = min(page, pages)

    start = (page - 1) * size
    rows = list(queryset[start:start + size])

    return rows, {
        "page": page,
        "page_size": size,
        "total": total,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }


def paginated_response(rows, meta, key="rows"):
    """
    ⚠️ **صيغةٌ واحدة**: `{rows, meta}` — فالواجهة تقرأ واحدةً لا
    عشرًا.
    """
    return {key: rows, "meta": meta}
