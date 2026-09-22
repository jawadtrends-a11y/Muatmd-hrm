"""
المرور على كلّ الحسابات — للمهامّ المجدولة (ق-234).

⚠️⚠️⚠️ **ستّ مهامّ من ثمانٍ مجدولة كانت معطّلةً صامتة**: كلّها تبدأ بـ
`Account.objects…` أو `AccountSubscription.objects…` **بلا سياق حساب** —
والجدولان معزولان (RLS)، **فترى صفرًا وتنتهي «ناجحة»**. فلم يُصعَّد طلب،
ولم تنتهِ تجربة، ولم يُجدَّد اشتراكٌ ولم تُخصم بطاقة.

**والقاعدة**: الحسابات تُسرد من `app_platform_accounts()` (تتجاوز العزل
بأمان، وصلاحيتها ممنوحة) — **وكلّ استعلامٍ آخر داخل سياق حسابه**.
"""
from django.db import connection

from apps.core.tenancy.context import account_scope


def all_account_ids() -> list[int]:
    with connection.cursor() as cur:
        cur.execute("SELECT account_id FROM app_platform_accounts()")
        return [r[0] for r in cur.fetchall()]


def across_accounts(qs_fn, *fields):
    """
    يمرّ على كلّ حسابٍ بسياقه ويُرجع صفوف الاستعلام.

    ⚠️ `qs_fn` **دالّةٌ تُنشئ الاستعلام** لا استعلامٌ جاهز: فالاستعلام الواحد
    يحفظ نتيجته بعد أوّل تقييم — **فيُعيد نتيجة الحساب الأول لكلّ حساب**.
    """
    for acc in all_account_ids():
        with account_scope(acc):
            rows = list(qs_fn().values_list(*fields))
        yield from rows
