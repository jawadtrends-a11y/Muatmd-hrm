"""
حرّاس اتساق الواجهة مع الخادم.

الحرّاس الأخرى تفحص بايثون وحدها، فمفاتيح الصلاحيات الخاطئة في
TypeScript تمر صامتة — وقد وقع الخطأ ثلاث مرات في يوم واحد:
requests.create_own و organization.view كلاهما غير مسجّل، فقسم
كامل من القائمة كان يختفي عن كل المستخدمين بلا أي إشارة.
"""
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "web" / "src"


def _ts_files():
    if not WEB.exists():
        return []
    return [p for p in WEB.rglob("*.ts*") if p.is_file()]


@pytest.mark.django_db
def test_frontend_permission_keys_registered():
    """
    كل مفتاح صلاحية في الواجهة مسجّل في كتالوج الخادم.

    المفتاح الخاطئ لا يرفع خطأ — الشاشة تختفي بصمت.
    """
    from apps.core.access.catalog import PERMISSION_KEYS

    files = _ts_files()
    if not files:
        pytest.skip("مجلد الواجهة غير موجود")

    modules = sorted({k.split(".")[0] for k in PERMISSION_KEYS})
    pattern = re.compile(
        r'["\'](' + "|".join(modules) + r')\.[a-z_]+["\']')

    unknown = set()
    for path in files:
        for m in pattern.finditer(path.read_text(encoding="utf-8")):
            key = m.group(0).strip("\"'")
            if key not in PERMISSION_KEYS:
                unknown.add(f"{path.name}: {key}")

    assert not unknown, (
        "مفاتيح صلاحيات في الواجهة غير مسجّلة بالكتالوج "
        "— الشاشة ستختفي بصمت:\n" + "\n".join(sorted(unknown))
    )


def test_frontend_api_paths_end_with_slash():
    """
    كل مسار API في الواجهة ينتهي بشرطة.

    بلا الشرطة يرد Django بـ301، وطلب POST يفقد جسمه عند
    التحويل — فيفشل بصمت.
    """
    files = _ts_files()
    if not files:
        pytest.skip("مجلد الواجهة غير موجود")

    # المسارات المُمرَّرة لدوال الـAPI
    call = re.compile(
        r'(?:apiGet|apiPost|apiPut|apiPatch|apiDelete|endpoint=)'
        r'[<(\s"]*["\'](/[^"\']*?)["\']')

    offenders = []
    for path in files:
        for m in call.finditer(path.read_text(encoding="utf-8")):
            url = m.group(1)
            if "?" in url or url.endswith("/") or "${" in url:
                continue
            offenders.append(f"{path.name}: {url}")

    assert not offenders, (
        "مسارات بلا شرطة نهائية — ستُحوَّل بـ301 وتفقد جسم "
        "الطلب:\n" + "\n".join(sorted(offenders))
    )
