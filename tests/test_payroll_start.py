"""
حارس: لا مسير قبل أول شهرٍ في النظام (ق-٢٥٢).

⚠️⚠️ العميل المنتقل من نظامٍ آخر **صرف شهوره السابقة هناك**. وبلا هذا الحدّ
يقبل المحرّك مسيرًا لأي شهرٍ مضى — **فيُصرف الشهر مرتين**. وقد نُقلت لسدرة
البنيان بصمات أربعة أشهر، **وكلها كانت قابلة لأن تُحوَّل مسيرًا**.
وما قبل البداية **تاريخٌ للعلم لا للصرف**: الحضور محسوبٌ ومعروض، والمسير ممنوع.
"""
import pytest

from apps.accounts.models import Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.payroll.models import PayrollSettings
from apps.payroll.services.engine import PayrollError, create_run


@pytest.fixture
def comp(db):
    r = provision_account(slug="start-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        yield Company.objects.get(id=r.company_id)


def _set_start(comp, year, month):
    st = PayrollSettings.objects.get(company=comp)
    st.payroll_start_year, st.payroll_start_month = year, month
    st.save(update_fields=["payroll_start_year", "payroll_start_month"])


def test_run_before_start_is_refused(comp):
    _set_start(comp, 2026, 10)
    with pytest.raises(PayrollError) as e:
        create_run(company=comp, run_type="regular", year=2026, month=8)
    assert "10/2026" in str(e.value), "⚠️ الرسالة لا تسمّي أول شهرٍ مسموح"


def test_run_at_start_is_allowed(comp):
    _set_start(comp, 2026, 10)
    r = create_run(company=comp, run_type="regular", year=2026, month=10)
    assert r.period_month == 10


def test_zero_means_no_limit(comp):
    """حسابٌ بدأ من النظام نفسه — صفرٌ يعني بلا حدّ."""
    _set_start(comp, 0, 0)
    r = create_run(company=comp, run_type="regular", year=2025, month=3)
    assert r.period_year == 2025


def test_provisioning_leaves_it_open(comp):
    """
    ⚠️ **التأسيس لا يفرضها.** جُرّب ضبطها بشهر التأسيس فمُنعت الحسابات
    الجديدة من كل ماضيها — ومن أسّس متأخرًا قد يحتاج شهرًا سابقًا فعلًا.
    فتبقى صفرًا (بلا حدّ) **حتى يحدّدها العميل** في قواعد المسير.
    """
    st = PayrollSettings.objects.get(company=comp)
    assert st.payroll_start_year == 0, "⚠️ التأسيس يفرض حدًّا لم يطلبه العميل"
