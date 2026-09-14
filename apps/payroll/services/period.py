"""
مدى المسير وتاريخ الاقتطاع (ق-157).

**بلاغ جواد:** إعداد الرواتب يسبق نهاية الشهر — فشركةٌ باقتطاعٍ
يوم ٢١ يكون **راتب سبتمبر من ٢٢ أغسطس إلى ٢١ سبتمبر**.

⚠️⚠️ **والمدى واحدٌ لكل ما يدخل المسير**: حضورًا وإضافيًّا
وإضافاتٍ وخصومات — **فمدًى للحضور وآخر للخصم يجعل القسيمة لا
تُفسَّر**.

⚠️ **وصفرٌ يعني الشهر التقويميّ** — وهو الافتراض.
"""
from calendar import monthrange
from datetime import date, timedelta


def cutoff_day(company_id):
    """يوم الاقتطاع — أو ٠ للشهر التقويميّ."""
    from apps.payroll.models import PayrollSettings

    st = PayrollSettings.objects.filter(company_id=company_id).first()
    return (st.payroll_cutoff_day or 0) if st else 0


def period_range(year, month, cutoff=0):
    """
    مدى المسير — **(البداية، النهاية) شاملتين**.

    ⚠️ **والاقتطاع يُرجع البداية للشهر السابق**: فاقتطاعُ ٢١ في
    سبتمبر يبدأ من ٢٢ أغسطس.

    ⚠️⚠️ **وأقصاه ٢٨** — فاقتطاعٌ يوم ٣٠ يكسر فبراير، وقد قُيّد
    في النموذج.
    """
    if not cutoff:
        return (date(year, month, 1),
                date(year, month, monthrange(year, month)[1]))

    cutoff = min(int(cutoff), 28)
    end = date(year, month, cutoff)

    # بداية المدى: اليوم التالي لاقتطاع الشهر السابق
    if month == 1:
        prev_y, prev_m = year - 1, 12
    else:
        prev_y, prev_m = year, month - 1
    start = date(prev_y, prev_m, cutoff) + timedelta(days=1)
    return start, end


def run_range(run):
    """
    مدى مسيرٍ بعينه — **بحسب إعداد شركته**.

    ⚠️ **ويُقرأ من الإعدادات لا من المسير**: فمسيرٌ يُعاد حسابه
    بعد تغيّر الاقتطاع يتبع الجديد، **وذاك مقصود**: فالمسير
    المعتمد لا يُعاد حسابه أصلًا.
    """
    return period_range(run.period_year, run.period_month,
                        cutoff_day(run.company_id))


def contains(run, day):
    """أيقع هذا اليوم في مدى المسير؟"""
    start, end = run_range(run)
    return start <= day <= end


def label(year, month, cutoff=0):
    """وصفُ المدى للعرض — فالقسيمة تقول ما تغطّيه."""
    if not cutoff:
        return f"{year}-{month:02d}"
    s, e = period_range(year, month, cutoff)
    return f"{s.isoformat()} → {e.isoformat()}"
