"""حرّاس مسار إنشاء الحساب."""
import pytest
from django.db import connection

from apps.accounts.services.provisioning import (
    ProvisioningError, provision_account, get_account_summary,
)


@pytest.mark.django_db(transaction=True)
def test_provision_creates_account_and_company():
    r = provision_account(
        slug="test-group", display_name_ar="مجموعة اختبار",
        company_name_ar="شركة الاختبار", is_sandbox=True,
    )
    s = get_account_summary(r.account_id)
    assert s["slug"] == "test-group"
    assert s["status"] == "trial"
    assert s["companies"] == ["شركة الاختبار"]


@pytest.mark.django_db(transaction=True)
def test_provision_rejects_invalid_slug():
    for bad in ["ab", "a", "اسم-عربي", "with space", "-leading", "trailing-"]:
        with pytest.raises(ProvisioningError):
            provision_account(slug=bad, display_name_ar="س", company_name_ar="ش")


@pytest.mark.django_db(transaction=True)
def test_provision_normalizes_case():
    """الحروف الكبيرة تُحوّل لصغيرة بدل الرفض — تسامح مقصود."""
    r = provision_account(
        slug="Mixed-CASE", display_name_ar="مجموعة", company_name_ar="شركة",
    )
    assert get_account_summary(r.account_id)["slug"] == "mixed-case"


@pytest.mark.django_db
def test_provision_function_not_public():
    """دالة SECURITY DEFINER يجب ألا تكون متاحة لـPUBLIC."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT has_function_privilege('public',
                'app_provision_account(text,text,text,text,boolean)', 'EXECUTE')
        """)
        assert cur.fetchone()[0] is False, "الدالة مفتوحة للجميع — خطر أمني"
