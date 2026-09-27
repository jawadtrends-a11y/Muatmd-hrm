"""
حارس: تسوية الخصوم المتأخّرة بأثرٍ رجعيّ (ق-٢٦٦).

⚠️⚠️ **الخصم يتبع تاريخه، والمسير يقرأ شهره وحده.** فتصحيحٌ لشهرٍ **مغلق** —
عطلةٌ تُدخَل متأخّرة، أو **إجازةٌ معتمدةٌ تُلغى** — يُنشئ خصمًا بتاريخٍ مضى
**لا يصل أيّ مسيرٍ أبدًا، فيضيع المال**.

⭐ **قرار جواد:** ما صُرف في مسيرٍ مغلق لا يُمسّ، **والفرق يُسوّى في المسير
التالي**. فمن ألغى إجازةً من عشرة أيّام وأعاد تقديمها على خمسةٍ منها، لا يظهر
خصم؛ ومن لم يُعد، يظهر خصمُ الخمسة بأثرٍ رجعيّ.
"""
from pathlib import Path

ENG = Path("apps/payroll/services/engine.py")


def test_run_reads_unsettled_backlog():
    """⭐ المسير يضمّ كلّ معتمَدٍ سابقٍ لم يُسوَّ — لا خصومَ شهره وحدها."""
    s = ENG.read_text(encoding="utf-8")
    assert "_settle_backlog" in s, "⚠️ الخصم المتأخّر لا يصل أيّ مسير"
    assert "settled_in_run__isnull=True" in s
    assert "work_date__lt=start" in s, "⚠️ لا يُقيَّد بما قبل المدى"


def test_pending_backlog_is_not_charged():
    """⚠️ **المعلّق لا يُضمّ** — قرارُه لم يُتّخذ بعد."""
    s = ENG.read_text(encoding="utf-8")
    i = s.index("def _settle_backlog")
    body = s[i:i + 1400]
    assert "AttendanceDeductionStatus.APPLIED" in body, (
        "⚠️ يُحسب المعلّق كأنّه مُقرَّر")


def test_marking_happens_on_approval_not_calculation():
    """
    ⚠️⚠️ **الوسم عند الاعتماد لا الاحتساب**: المسير يُحتسب مرارًا قبل أن
    يُعتمد — فوسمُه عند الاحتساب يُخرج الخصم من المتأخّرات **وهو لم يُصرف**،
    فيضيع نهائيًّا.
    """
    s = ENG.read_text(encoding="utf-8")
    i = s.index("def approve_run")
    body = s[i:i + 2500]
    assert "settled_in_run=run" in body, "⚠️ الاعتماد لا يَسِم المتأخّرات"

    j = s.index("def _settle_backlog")
    calc = s[j:j + 1400]
    assert "settled_in_run=run" not in calc, (
        "⚠️ الاحتساب يَسِم — فيضيع الخصم قبل صرفه")


def test_settled_is_never_charged_twice():
    """⭐ الموسوم لا يعود متأخّرًا — فلا يُصرف مرّتين."""
    s = ENG.read_text(encoding="utf-8")
    assert "settled_in_run__isnull=True" in s
