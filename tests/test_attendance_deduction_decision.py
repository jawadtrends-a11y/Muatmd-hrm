"""
حارس: الحساب ليس قرارًا (ق-٢٥٣).

⚠️⚠️ كان المسير يقرأ أيام الغياب من الحضور **ويحسمها مباشرةً** — فبلغ الخصم
في أول مسيرٍ حقيقيّ (١٤ موظفًا) **٥٩٪ من الرواتب**، لأن البصم ناقصٌ لا لأن
الموظفين غابوا. والبصمة تنقص لعطلٍ في الجهاز، أو مهمةٍ خارج الموقع، أو نسيان
— **والغياب في النظام ليس غيابًا في الواقع**.

فوضعان: **آليّ** يُخصم (وللموارد إلغاؤه)، و**يدويّ** لا يُخصم حتى يُقرَّر.
⚠️ **وصفٌّ لكل يوم لا لكل شهر** — فلكل يومٍ سببه.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Company
from apps.accounts.services.provisioning import provision_account
from apps.core.tenancy.context import account_scope
from apps.payroll.models import (AttendanceDeduction,
                                 AttendanceDeductionStatus, PayrollSettings)


@pytest.fixture
def comp(db):
    r = provision_account(slug="ded-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        yield Company.objects.get(id=r.company_id)


def test_default_mode_is_auto(comp):
    """⚠️ الافتراض **آليّ** — فمن لم يضبط شيئًا لا يتغيّر عليه سلوك النظام."""
    st = PayrollSettings.objects.get(company=comp)
    assert st.attendance_deduction_mode == "auto"


def test_one_row_per_day_not_per_month(comp):
    """
    ⚠️⚠️ **يومًا يومًا.** «أعفِ ثلاثة أيام غياب» قرارٌ أعمى — فقد يكون يومٌ
    منها عطلَ جهاز والثاني تغيّبًا حقيقيًّا.
    """
    fields = {f.name for f in AttendanceDeduction._meta.fields}
    assert "work_date" in fields, "⚠️ الخصم مجمَّعٌ بالشهر لا مفصَّلٌ باليوم"
    names = {c.name for c in AttendanceDeduction._meta.constraints}
    assert "uq_attendance_deduction_per_day" in names


def test_waiving_requires_a_reason():
    """⚠️ **الإعفاء يُعلَّل** — فالمراجع يعرف لماذا سقط خصمٌ مستحَقّ."""
    # ⚠️ `@api_view` يلفّ الدالّة فلا يراها `inspect` — فيُقرأ الملفّ نصًّا
    from pathlib import Path

    src = Path("apps/payroll/api.py").read_text(encoding="utf-8")
    i = src.find("def decide_attendance_deduction")
    assert i > 0, "الدالّة غير موجودة"
    body = src[i:i + 3000]
    assert "اكتب سبب الإعفاء" in body, "⚠️ يُعفى بلا سبب — فلا يُراجَع القرار"


def test_engine_reads_the_decision_not_the_raw_days():
    """⭐ **المسير يقرأ القرار**: `applied` وحدها تُحسم."""
    import inspect

    from apps.payroll.services import engine

    src = inspect.getsource(engine.sync_attendance_deductions)
    assert "AttendanceDeductionStatus.APPLIED" in src, (
        "⚠️ المحرّك يجمع كل الخصومات لا المعتمدة وحدها")


def test_no_penalty_on_a_waived_day():
    """
    ⚠️⚠️ **لا جزاء على يومٍ أُعفي خصمُه.** الجزاء التأديبيّ يقوم على مخالفةٍ
    ثابتة — وإعفاءُ الخصم يعني أنها لم تثبت. فمعاقبةُ من أُعفي خصمُه **ظلمٌ
    ومناقضةٌ لقرارٍ اتُّخذ للتوّ**.
    """
    import inspect

    from apps.employees.services import penalties

    src = inspect.getsource(penalties.pending_board)
    assert "not_established" in src, "⚠️ الجزاء يُقترح على يومٍ لم يثبت خصمه"
