"""
حارس: مفاتيح ملف الموظف متطابقة بين الخادم والواجهة (ق-٢٥٨).

⚠️⚠️ **التسمية في العقد جزءٌ من العقد.** تكرّرت هذه العلّة **أربع مرات**:
`/employees/?all=1` يُرجع `id` والواجهة تقرأ `employment_id` · و`job.manager_id`
تُقرأ `direct_manager_id` · و`job.site_id` تُقرأ `primary_site_id`.

وأثرها **صامتٌ وخادع**: الحقل **يُحفظ في القاعدة ولا يظهر أبدًا** — فيظنّ
المستخدم أن الحفظ فشل فيُعيده مرّاتٍ، ولا رسالة خطأ ترشده. ولا يكشفها إلا
عميلٌ حقيقيٌّ يُدخل بياناته.
"""
import re
from pathlib import Path

WEB = Path("web/src/components/EmployeeProfileView.tsx")


def test_every_edit_key_exists_in_the_server_contract():
    """كل `key:` في نموذج التحرير له نظيرٌ يُرسله الخادم."""
    if not WEB.exists():
        return

    api = Path("apps/employees/api.py").read_text(encoding="utf-8")
    served = set(re.findall(r'"([a-z_0-9]+)":', api))
    keys = set(re.findall(r'key: "([a-z_0-9]+)"', WEB.read_text(encoding="utf-8")))

    missing = sorted(k for k in keys if k not in served)
    assert not missing, (
        "⚠️ مفاتيح تقرؤها الواجهة ولا يُرسلها الخادم — **تُحفظ ولا تظهر**:\n"
        + "\n".join(missing))
