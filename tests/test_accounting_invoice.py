"""
حرّاس تكامل الفوترة مع معتمد المحاسبي (ق-111).

⚠️ أخطرها الأول: **لا فاتورة تُصدر ما لم يُفعَّل المفتاح صراحةً** —
فالفاتورة تدخل دفاتر معتمد الحقيقية، ولا يجوز أن تُنشأ في التطوير
ولا بالخطأ.
"""
import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services import accounting_invoice as ai
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope


@pytest.fixture
def company(db):
    r = provision_account(slug="acc-inv", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        yield Company.objects.get(id=r.company_id)


def test_disabled_by_default(company, settings):
    """
    ⚠️ الأهمّ: المفتاح مطفأ افتراضًا — فلا استدعاء ولا فاتورة.

    ومن نسي إطفاءه في بيئة تطوير يُنشئ فواتير في دفاتر حقيقية.
    """
    assert getattr(settings, "ACCOUNTING_INVOICE_ENABLED", False) is False


def test_incomplete_data_is_skipped(company):
    """من لم يُكمل بياناته النظامية لا تصدر فاتورته."""
    ok, missing = ai.readiness(company)
    assert not ok
    assert "الرقم الضريبي" in missing
    assert "رقم المبنى" in missing


def test_complete_data_is_ready(company):
    """المكتمل جاهز — والحقول الستّة هي الشرط."""
    Company.objects.filter(id=company.id).update(
        vat_number="300000000000003", building_number="1234",
        street="طريق الملك فهد", district="العليا",
        city="الرياض", postal_code="12211")
    company.refresh_from_db()
    ok, missing = ai.readiness(company)
    assert ok, missing


def test_short_vat_number_is_refused(company):
    """الرقم الضريبي خمس عشرة خانة — والهيئة ترفض غيره."""
    Company.objects.filter(id=company.id).update(
        vat_number="30000", building_number="1234",
        street="طريق", district="حي", city="الرياض",
        postal_code="12211")
    company.refresh_from_db()
    ok, missing = ai.readiness(company)
    assert not ok
    assert any("١٥" in m for m in missing)
