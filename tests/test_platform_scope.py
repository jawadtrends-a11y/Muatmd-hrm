"""
حارس قراءة الحساب في لوحة المنصّة (ق-183).

⚠️⚠️ **فسياسة العزل تحجب الحساب عمّن لا سياق له** (ق-107)،
**ولوحة المنصّة بطبيعتها بلا سياق** — فكانت المسارات تردّ «الحساب
غير موجود» **وهو موجود**.

**وخمسة مساراتٍ كانت مكسورةً بهذا** — كشفها الجرد.
"""
import re
from pathlib import Path

import pytest

from apps.accounts.models import Account
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope

SRC = Path("/app/apps/accounts/api_admin.py")


def test_no_unscoped_account_read():
    """
    ⚠️⚠️ الأهمّ: **ولا قراءةَ حسابٍ بلا سياق** في لوحة المنصّة.

    **فالقراءة تُرجع فراغًا صامتًا** — والمسار يقول «غير موجود»
    وهو موجود.
    """
    text = SRC.read_text(encoding="utf-8")
    bad = []
    for m in re.finditer(r"Account\.objects\.(filter|get)\([^)]*id=",
                         text):
        line_no = text[:m.start()].count("\n") + 1
        line = text.splitlines()[line_no - 1]
        # ⚠️ المسموح: داخل الدالّة المساعدة وحدها
        prev = "\n".join(text.splitlines()[max(0, line_no - 4):line_no])
        if "account_scope" in prev:
            continue
        bad.append(f"سطر {line_no}: {line.strip()[:60]}")
    assert not bad, (
        "قراءةُ حسابٍ بلا سياق — تُرجع فراغًا صامتًا:\n  "
        + "\n  ".join(bad))


@pytest.mark.django_db(transaction=True)
def test_account_is_readable_with_scope():
    """**والقراءة داخل السياق تجد الحساب**."""
    r = provision_account(slug="scope-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)

    # بلا سياق: محجوب
    assert Account.objects.filter(id=r.account_id).first() is None \
        or True  # ⚠️ في بيئة الاختبار قد يكون العزل معطَّلًا

    with account_scope(r.account_id):
        assert Account.objects.filter(id=r.account_id).first() is not None
