"""
حرّاس تاريخ الاقتطاع (ق-157).

**بلاغ جواد:** إعداد الرواتب يسبق نهاية الشهر — فشركةٌ باقتطاعٍ
يوم ٢١ يكون **راتب سبتمبر من ٢٢ أغسطس إلى ٢١ سبتمبر**.

⚠️⚠️ **والمدى واحدٌ لكل ما يدخل المسير**: حضورًا وإضافيًّا
وإضافاتٍ وخصومات — **فمدًى للحضور وآخر للخصم يجعل القسيمة لا
تُفسَّر**.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import (
    PayComponent, PayrollRunType, PayrollSettings)
from apps.payroll.services import engine
from apps.payroll.services.period import (
    cutoff_day, label, period_range, run_range)


@pytest.fixture
def env(db):
    r = provision_account(slug="cut-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        p, _ = create_person(
            account=acc, first_name_ar="بندر", family_name_ar="الزهراني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044556677", mobile="0504455667")
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="C-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic, Decimal("12000"))])

        st = PayrollSettings.objects.filter(company=comp).first()

        yield {"account_id": r.account_id, "comp": comp, "emp": emp,
               "settings": st}


def _set_cutoff(env, day):
    env["settings"].payroll_cutoff_day = day
    env["settings"].save(update_fields=["payroll_cutoff_day"])


# ══════════ حساب المدى ══════════

def test_zero_means_calendar_month():
    """
    ⚠️ **وصفرٌ يعني الشهر التقويميّ** — وهو الافتراض، فمن لم
    يضبطه لا يتغيّر عليه شيء.
    """
    assert period_range(2026, 9, 0) == (date(2026, 9, 1),
                                        date(2026, 9, 30))


def test_cutoff_shifts_the_range_back():
    """
    ⚠️⚠️ الأهمّ: **اقتطاعُ ٢١ يبدأ من ٢٢ الشهر السابق** — وهو
    مثال جواد بعينه.
    """
    assert period_range(2026, 9, 21) == (date(2026, 8, 22),
                                         date(2026, 9, 21))


def test_january_crosses_the_year():
    """**ويناير يعبر السنة** — فبدايته في ديسمبر الماضي."""
    assert period_range(2026, 1, 21) == (date(2025, 12, 22),
                                         date(2026, 1, 21))


def test_cutoff_is_capped_at_28():
    """
    ⚠️ **وأقصاه ٢٨**: فاقتطاعٌ يوم ٣٠ يكسر فبراير — ولو مرّ
    لانهار المسير في شهرٍ واحد من كل سنة.
    """
    s, e = period_range(2026, 2, 30)
    assert e == date(2026, 2, 28)
    assert s == date(2026, 1, 29)


def test_ranges_do_not_overlap_or_gap():
    """
    ⚠️⚠️ **ولا فجوةَ بين مدَيين ولا تداخل**: فيومٌ يقع في مسيرين
    يُدفع مرّتين، ويومٌ بلا مسير لا يُدفع أبدًا.
    """
    from datetime import timedelta

    prev_end = None
    for m in range(1, 13):
        s, e = period_range(2026, m, 21)
        if prev_end is not None:
            assert s == prev_end + timedelta(days=1), (
                f"فجوة أو تداخل عند الشهر {m}: {prev_end} ثم {s}")
        prev_end = e


# ══════════ أثره في المسير ══════════

def test_run_follows_company_cutoff(env):
    """ومدى المسير يتبع إعداد شركته."""
    with account_scope(env["account_id"]):
        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        _set_cutoff(env, 0)
        assert run_range(run) == (date(2026, 9, 1), date(2026, 9, 30))

        _set_cutoff(env, 21)
        assert run_range(run) == (date(2026, 8, 22), date(2026, 9, 21))


def test_payslip_records_its_period(env):
    """
    ⚠️ **والقسيمة تحمل مداها**: فمن يقرؤها يعرف ما تغطّيه — وبلاه
    يُسأل المحاسب عن أرقامٍ لا يفسّرها.
    """
    with account_scope(env["account_id"]):
        _set_cutoff(env, 21)
        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        run.refresh_from_db()
        assert run.payslips.count() == 1, run.status

        slip = run.payslips.first()
        att = (slip.calculation_trace or {}).get("attendance", {})
        assert att.get("period") == "2026-08-22 → 2026-09-21", att
        assert att.get("source") == "attendance_days_cutoff"


def test_without_cutoff_summary_is_used(env):
    """
    **وبلا اقتطاعٍ يبقى الملخّص الشهريّ** — فلا نُغيّر على من لم
    يطلب (قرار جواد: الملخّص يبقى تقويميًّا لغرضه).
    """
    with account_scope(env["account_id"]):
        _set_cutoff(env, 0)
        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        slip = run.payslips.first()
        att = (slip.calculation_trace or {}).get("attendance", {})
        assert att.get("source") in ("monthly_summary", "no_summary")


def test_attendance_outside_range_is_excluded(env):
    """
    ⚠️⚠️ **وغيابٌ خارج المدى لا يُحتسب**: فيومُ ٢٥ سبتمبر يقع في
    مسير أكتوبر حين يكون الاقتطاع ٢١ — **واحتسابُه هنا يخصم
    مرّتين**.
    """
    from apps.attendance.models import AttendanceDay, DayStatus

    with account_scope(env["account_id"]):
        _set_cutoff(env, 21)

        # يومٌ داخل المدى، وآخر خارجه
        AttendanceDay.objects.create(
            account_id=env["account_id"], company=env["comp"],
            employment=env["emp"], work_date=date(2026, 9, 10),
            status=DayStatus.ABSENT)
        AttendanceDay.objects.create(
            account_id=env["account_id"], company=env["comp"],
            employment=env["emp"], work_date=date(2026, 9, 25),
            status=DayStatus.ABSENT)

        run = engine.create_run(company=env["comp"],
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        slip = run.payslips.first()
        att = (slip.calculation_trace or {}).get("attendance", {})
        assert att.get("unpaid_absence_days") == "1", (
            f"احتُسب غيابٌ خارج المدى: {att}")


def test_label_describes_the_range(env):
    """والوصف يُبيّن المدى — فالقسيمة تقول ما تغطّيه."""
    assert label(2026, 9, 0) == "2026-09"
    assert label(2026, 9, 21) == "2026-08-22 → 2026-09-21"


def test_cutoff_day_reads_settings(env):
    """ويُقرأ من إعدادات الشركة لا من ثابتٍ في الكود."""
    with account_scope(env["account_id"]):
        _set_cutoff(env, 23)
        assert cutoff_day(env["comp"].id) == 23
        _set_cutoff(env, 0)
        assert cutoff_day(env["comp"].id) == 0
