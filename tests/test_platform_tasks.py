"""
حرّاس المهامّ المجدولة (ق-234).

⚠️⚠️⚠️ **ستّ مهامّ من ثمانٍ كانت معطّلةً صامتة** — تسرد الحسابات بـ`Account.objects`
بلا سياق، والجدول معزول: **فترى صفرًا وتنتهي «ناجحة»**. فلم يُصعَّد طلب، ولم
تنتهِ تجربة، ولم يُجدَّد اشتراك. وهذه الحرّاس تمنع عودتها.
"""
import re
from pathlib import Path

import pytest

from apps.accounts.models import Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.platform import across_accounts, all_account_ids


@pytest.fixture
def two(db):
    return [provision_account(slug=f"pt-{i}", display_name_ar="حساب",
                              company_name_ar="شركة", is_sandbox=True).account_id
            for i in (1, 2)]


def test_accounts_visible_without_context(two):
    """⚠️⚠️ الأهمّ: **المهامّ ترى الحسابات بلا سياق** — وكانت ترى صفرًا."""
    ids = all_account_ids()
    assert set(two) <= set(ids)


def test_across_accounts_reads_each_account(two):
    """
    ⚠️ **وكلّ حسابٍ يُقرأ بسياقه لا بنتيجة الأوّل** — فالاستعلام الجاهز يحفظ
    نتيجته بعد أوّل تقييم، ولهذا تستقبل الدالّة مُنشئًا لا استعلامًا.
    """
    seen = {acc for (acc,) in across_accounts(lambda: Company.objects.all(), "account_id")}
    assert set(two) <= seen


def test_no_task_lists_isolated_tables_without_context():
    """⚠️⚠️ **لا مهمّة تسرد جدولًا معزولًا بلا سياق** — فيُكسر الاختبار قبل الإنتاج."""
    bad = []
    # الموظفون داخل مهمّةٍ بسياق حسابها سليمون — والعلّة سرد الحسابات والاشتراكات
    pat = re.compile(r"(for .+ in |list\()\s*(Account|AccountSubscription)\.objects")
    for f in Path("apps").rglob("tasks*.py"):
        if f.name == "tasks_demo.py":
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if pat.search(code):
                bad.append(f"{f}:{i}  {line.strip()}")
    assert not bad, "سردٌ بلا سياق — استعمل all_account_ids/across_accounts:\n" + "\n".join(bad)
