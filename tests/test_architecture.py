"""
حرّاس معمارية — يفشل البناء عند خرق قاعدة بنيوية.

هذه ليست اختبارات ميزات، بل حماية للقرارات التي بُني عليها النظام.
راجع الوثيقة المعمارية (2) القسم 7.
"""
import ast
import re
from pathlib import Path

import pytest

# المسار داخل الحاوية /app، وفي CI جذر المستودع. نجرّب الاثنين.
_CANDIDATES = [Path("/app/apps"), Path(__file__).resolve().parent.parent / "apps"]
APPS_DIR = next((p for p in _CANDIDATES if p.is_dir()), None)
assert APPS_DIR is not None, (
    "لم يُعثر على مجلد apps — الحرّاس تفحص فراغًا وهذا أمان زائف"
)
RAW_QUERY_RE = re.compile(r"\b[A-Z]\w+\.objects\.(filter|all|get|exclude)\b")


def _python_files(*subpaths):
    for sub in subpaths:
        for p in APPS_DIR.rglob(sub):
            if "migrations" not in p.parts and "__pycache__" not in p.parts:
                yield p


def test_no_raw_queryset_in_api_views():
    """
    ممنوع Model.objects.filter() خامًا في طبقة الـAPI.
    كل قراءة تمر بـGate.filter_queryset — الأمان في الطبقة الخلفية.
    """
    offenders = []
    for path in _python_files("api/*.py", "views.py", "views/*.py"):
        src = path.read_text(encoding="utf-8")
        for i, line in enumerate(src.splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if RAW_QUERY_RE.search(line) and "Gate." not in line:
                offenders.append(f"{path.name}:{i}  {line.strip()[:70]}")
    assert not offenders, (
        "استعلامات خام في طبقة الـAPI — استخدم Gate.filter_queryset:\n"
        + "\n".join(offenders)
    )


def test_all_celery_tasks_are_account_scoped():
    """كل مهمة Celery ترث AccountTask — وإلا عملت بلا عزل."""
    offenders = []
    for path in _python_files("tasks.py", "tasks/*.py", "tasks_*.py"):
        if path.name == "tasks.py" and path.parent.name == "core":
            continue  # ملف الأساس نفسه
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for dec in node.decorator_list:
                dec_src = ast.get_source_segment(src, dec) or ""
                if "shared_task" in dec_src or "app.task" in dec_src:
                    if "AccountTask" not in dec_src:
                        offenders.append(f"{path.name}: {node.name}")
    assert not offenders, (
        "مهام Celery بلا AccountTask — تعمل بلا عزل:\n" + "\n".join(offenders)
    )


def test_no_hardcoded_permission_strings_outside_catalog():
    """
    كل مفتاح صلاحية مستخدم في الكود مسجّل في الكتالوج.
    يمنع الصلاحيات اليتيمة التي لا يمنحها أي دور.
    """
    from apps.core.access.catalog import PERMISSION_KEYS
    from apps.notifications.catalog import EVENT_KEYS

    # النظام يحمل كتالوجين بنفس النمط <وحدة>.<فعل>:
    #   الصلاحيات (employees.view) وأحداث الإشعارات (leave.approved).
    # المفتاح المشروع هو المسجّل في أيٍّ منهما؛ ما عداه يتيم.
    known = PERMISSION_KEYS | EVENT_KEYS
    modules = sorted({k.split(".")[0] for k in known})
    pattern = re.compile(r'["\'](' + "|".join(modules) + r')\.[a-z_]+["\']')

    unknown = set()
    for path in _python_files("*.py"):
        if path.name == "catalog.py":
            continue
        for m in pattern.finditer(path.read_text(encoding="utf-8")):
            key = m.group(0).strip("\"'")
            if key not in known:
                unknown.add(f"{path.name}: {key}")
    assert not unknown, (
        "مفاتيح غير مسجّلة في كتالوج الصلاحيات ولا كتالوج الأحداث:\n"
        + "\n".join(sorted(unknown))
    )


def test_every_model_with_account_field_inherits_base():
    """كل نموذج يحمل account يرث من الأساس — يضمن اتساق العزل."""
    from django.apps import apps as dj_apps
    from apps.core.models import AccountScopedModel

    # نماذج الحساب نفسه — لا تحمل مرجعًا لحساب آخر
    exempt = {"Account", "Company", "AccountMembership"}
    offenders = []
    for model in dj_apps.get_models():
        if not model._meta.app_label.startswith(("core", "accounts", "employees",
                                                 "payroll", "attendance",
                                                 "leaves", "organization",
                                                 "notifications")):
            continue
        if model.__name__ in exempt:
            continue
        account_field = next(
            (f for f in model._meta.fields if f.name == "account"), None
        )
        if account_field is None:
            continue
        # نمط مقصود: account قابل للفراغ = النموذج يحمل قوالب افتراضية
        # للمنصة (Role، NotificationTemplate). لا يمكن توريثه من أساس
        # يفرض account إلزاميًا. عزله يتم بسياسة RLS تسمح بـIS NULL.
        if account_field.null:
            continue
        if not issubclass(model, AccountScopedModel):
            offenders.append(f"{model._meta.app_label}.{model.__name__}")
    assert not offenders, (
        "نماذج تحمل account بلا وراثة AccountScopedModel:\n" + "\n".join(offenders)
    )


def test_guards_actually_scan_files():
    """
    حارس الحرّاس: يتأكد أن الفحص يرى ملفات فعلية.

    بدونه، لو تغيّر المسار في بيئة أخرى لمرّت كل الحرّاس بلا فحص
    شيء — أمان زائف. هذا الاختبار يمنع ذلك.
    """
    files = list(_python_files("*.py"))
    assert len(files) >= 20, (
        f"الحرّاس ترى {len(files)} ملفًا فقط في {APPS_DIR} — "
        "الفحص لا يعمل على ملفات حقيقية"
    )
    names = {f.name for f in files}
    for expected in ("models.py", "gate.py", "catalog.py", "tasks.py"):
        assert expected in names, f"ملف متوقع مفقود من الفحص: {expected}"
