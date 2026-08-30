"""
حرّاس معمارية — يفشل البناء عند خرق قاعدة بنيوية.

هذه ليست اختبارات ميزات، بل حماية للقرارات التي بُني عليها النظام.
راجع الوثيقة المعمارية (2) القسم 7.
"""
import ast
import re
from pathlib import Path

import pytest

APPS_DIR = Path("/app/apps")
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

    pattern = re.compile(
        r'["\'](' + "|".join(
            sorted({k.split(".")[0] for k in PERMISSION_KEYS})
        ) + r')\.[a-z_]+["\']'
    )
    unknown = set()
    for path in _python_files("*.py"):
        if "catalog.py" in path.name or path.parts[-2] == "tests":
            continue
        for m in pattern.finditer(path.read_text(encoding="utf-8")):
            key = m.group(0).strip("\"'")
            if key not in PERMISSION_KEYS:
                unknown.add(f"{path.name}: {key}")
    assert not unknown, "مفاتيح صلاحيات غير مسجّلة:\n" + "\n".join(sorted(unknown))


def test_every_model_with_account_field_inherits_base():
    """كل نموذج يحمل account يرث من الأساس — يضمن اتساق العزل."""
    from django.apps import apps as dj_apps
    from apps.core.models import AccountScopedModel

    exempt = {"Account", "Company", "Role", "AccountMembership"}
    offenders = []
    for model in dj_apps.get_models():
        if not model._meta.app_label.startswith(("core", "accounts", "employees",
                                                 "payroll", "attendance",
                                                 "leaves", "organization",
                                                 "notifications")):
            continue
        if model.__name__ in exempt:
            continue
        has_account = any(f.name == "account" for f in model._meta.fields)
        if has_account and not issubclass(model, AccountScopedModel):
            offenders.append(f"{model._meta.app_label}.{model.__name__}")
    assert not offenders, (
        "نماذج تحمل account بلا وراثة AccountScopedModel:\n" + "\n".join(offenders)
    )
