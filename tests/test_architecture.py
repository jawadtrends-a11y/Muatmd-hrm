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
RAW_QUERY_RE = re.compile(r"\b([A-Z]\w+)\.objects\.(filter|all|get|exclude)\b")


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
    # جداول المنصة لا تحمل account_id ولا نطاق — الفلترة عليها بلا معنى
    PLATFORM_MODELS = {
        "Plan", "PlanFeature", "PlanPriceTier", "Feature",
        "NotificationEvent", "NotificationTemplate",
    }

    # نماذج إعدادات الشركة: لا تحمل بيانات موظفين، والعزل
    # بـcompany_id كافٍ فيها
    SETTINGS_MODELS = {
        "LeaveType", "PayComponent", "PayrollSettings", "Shift",
        "BankTemplate", "Holiday", "JobTitle", "ApprovalChain",
        # رموز البنوك (ق-57): حقيقة نظامية مشتركة بين كل الحسابات
        "Bank",
        # الملفات (ق-61): معزولة بـRLS، والوصول عبر مسار محمي
        "StoredFile",
        # رموز المصادقة: مقيّدة بـuser=request.user — لا مجال لتسرّب
        "AuthToken",
    }
    offenders = []
    for path in _python_files("api/*.py", "api.py", "views.py", "views/*.py"):
        src = path.read_text(encoding="utf-8")
        lines = src.splitlines()
        for i, line in enumerate(lines, 1):
            if line.strip().startswith("#"):
                continue
            m = RAW_QUERY_RE.search(line)
            if not m:
                continue
            model = m.group(1)
            if model in PLATFORM_MODELS:
                continue
            # الاستعلام قد يُمرَّر لـGate على سطر مجاور (كتلة متعددة الأسطر)
            window = "\n".join(lines[max(0, i - 4):i + 2])
            if "Gate." in window:
                continue
            # معزول ذاتيًا: الاستعلام مقيَّد بالمستخدم نفسه — الموظف
            # يرى ملفه ورصيده وطلباته، فالبوابة لا تضيف عزلًا.
            # ما يبقى محروسًا: أي استعلام يقرأ بيانات موظفين آخرين.
            if any(k in window for k in (
                    "person=person", "person=getattr", "employment=emp",
                    "approver_employment=emp", "employment=employment",
                    "deputy=emp",
                    # الإشعار يخصّ شخصًا بعينه — المستقبل هو القيد
                    "recipient_person_id=person.id",
                    # الاستثناء يخصّ عضوية بعينها — العضوية هي القيد
                    "membership=membership",
                    # الملكية تُنزع داخل حساب المنفّذ وحده
                    "account_id=me.account_id",
                    # مقيَّد بشركة الموظف الذي مرّ بالبوابة
                    "company_id=emp.company_id",
                    # الكائن الأب مرّ بالبوابة، والاستعلام مقيَّد به:
                    # site جاء من Gate.filter_queryset، وp من emp.person
                    "person=p", "site=site")):
                continue
            # إعدادات الشركة لا بيانات موظفين — company_id يكفي
            if model in SETTINGS_MODELS:
                continue
            offenders.append(f"{path.name}:{i}  {line.strip()[:70]}")
    assert not offenders, (
        "استعلامات خام في طبقة الـAPI — استخدم Gate.filter_queryset:\n"
        + "\n".join(offenders)
    )


def test_all_celery_tasks_are_account_scoped():
    """
    كل مهمة Celery معزولة — بأحد أسلوبين:

      • ترث AccountTask: تعمل داخل حساب واحد يُمرَّر إليها
      • تفتح account_scope صراحةً: مهام منصة تمر على كل الحسابات
        وتدخل نطاق كل واحد على حدة (لقطة الموظفين، تقييم
        الاشتراكات، التجديد التلقائي)

    ما يُرفض: مهمة تلمس بيانات عملاء بلا أي من الاثنين.
    """
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
                if "shared_task" not in dec_src and "app.task" not in dec_src:
                    continue
                if "AccountTask" in dec_src:
                    continue
                body = ast.get_source_segment(src, node) or ""
                if "account_scope(" in body:
                    continue      # معزولة بفتح النطاق صراحةً
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
    # وكتالوج ثالث معزول: قدرات لوحة المنصة (ق-51). قدرات
    # السوبر أدمن لا تُخلط بصلاحيات العملاء — العزل بينهما مقصود،
    # فلها كتالوجها الخاص ROLE_CAPABILITIES.
    from apps.accounts.models_admin import ROLE_CAPABILITIES
    platform_caps = set()
    for caps in ROLE_CAPABILITIES.values():
        platform_caps |= caps

    known = PERMISSION_KEYS | EVENT_KEYS | platform_caps
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


def test_every_api_module_is_routed():
    """
    كل ملف API له مسار مسجّل في config/urls.py.

    وقعنا في هذا مرتين: billing.py كُتب بلا مسار فلم يعمل قط،
    ومسار سُجّل بلا ملف فتعطّل النظام. هذا الحارس يمنع الحالتين.
    راجع الوثيقة المعمارية (2) القسم 7.2 — «لا مسارات ناقصة».
    """
    import re

    urls_path = Path(APPS_DIR).parent / "config" / "urls.py"
    if not urls_path.exists():
        urls_path = Path("/app/config/urls.py")
    urls_src = urls_path.read_text(encoding="utf-8")

    api_modules = []
    for path in APPS_DIR.rglob("api.py"):
        if "__pycache__" not in path.parts:
            api_modules.append(path)
    for path in APPS_DIR.rglob("api/*.py"):
        if path.name != "__init__.py" and "__pycache__" not in path.parts:
            api_modules.append(path)

    unrouted = []
    for path in api_modules:
        views = re.findall(r"^def (\w+)\(request", path.read_text(encoding="utf-8"),
                           re.MULTILINE)
        public = [v for v in views if not v.startswith("_")]
        if not public:
            continue
        if not any(v in urls_src for v in public):
            unrouted.append(f"{path.relative_to(APPS_DIR)}: {public[:3]}")

    assert not unrouted, (
        "ملفات API بلا مسارات مسجّلة — كُتبت ولن تعمل:\n" + "\n".join(unrouted)
    )


def test_all_routed_views_are_importable():
    """كل مسار مسجّل يشير لدالة موجودة فعلًا."""
    from django.urls import get_resolver

    patterns = get_resolver().url_patterns
    assert len(patterns) >= 15, f"عدد المسارات {len(patterns)} أقل من المتوقع"
    from django.urls.resolvers import URLPattern
    for p in patterns:
        if not isinstance(p, URLPattern):
            continue          # URLResolver (مثل admin/) لا يحمل callback
        assert callable(p.callback), f"مسار بلا دالة: {p.pattern}"


def test_no_orphan_permissions():
    """
    كل صلاحية في الكتالوج يمنحها دور افتراضي واحد على الأقل.

    الصلاحية بلا دور معطّلة عمليًا: الكود يفحصها فترفض دائمًا،
    فتبدو الميزة موجودة وهي لا تعمل. حدث فعلًا مع
    persons.view_cross_company (ق-30) ولم ينتبه أحد لسبرنتين.
    """
    from apps.accounts.services.roles import DEFAULT_ROLES
    from apps.core.access.catalog import PERMISSION_KEYS

    # المالك يملك "*" — لو حسبناه لصار كل شيء ممنوحًا ولما كشف
    # الحارس شيئًا أبدًا. الفحص على الأدوار التي تمنح صلاحيات صراحةً.
    granted = set()
    for code, spec in DEFAULT_ROLES.items():
        perms = spec["permissions"]
        if perms == "*":
            continue
        granted |= set(perms)

    # صلاحيات ملكية بحتة — للمدير العام وحده بقرار موثّق (ق-31)
    OWNER_ONLY = {"account.manage", "company.create"}

    orphans = PERMISSION_KEYS - granted - OWNER_ONLY
    assert not orphans, (
        "صلاحيات مسجّلة بلا دور يمنحها — معطّلة عمليًا:\n"
        + "\n".join(sorted(orphans))
    )


def test_no_orphan_notification_events():
    """كل حدث إشعار له قالب — وإلا ظهر إشعار بلا نص."""
    from apps.notifications.catalog import EVENT_KEYS
    from apps.notifications.services.templates import TEMPLATES

    orphans = EVENT_KEYS - set(TEMPLATES)
    assert not orphans, (
        "أحداث بلا قوالب:\n" + "\n".join(sorted(orphans))
    )


def test_no_native_date_input():
    """
    لا <input type="date"> في الشاشات — DateField وحده.

    العنصر الأصلي يعرض تقويم المتصفح بالإنجليزية وبصيغة
    MM/DD/YYYY، والقارئ السعودي يقرأ 08/25/2026 فيظنه اليوم الثامن
    من الشهر الخامس والعشرين. وDateField يعرض DD/MM/YYYY بأسماء
    عربية، ولوحته تخرج من أي حاوية تقصّها.
    """
    from pathlib import Path

    web = Path("web/src")
    if not web.exists():
        return

    offenders = []
    for f in sorted(web.rglob("*.tsx")):
        if f.name == "DateField.tsx":
            continue      # المكوّن نفسه يلفّ العنصر الأصلي
        for i, line in enumerate(
                f.read_text(encoding="utf-8").split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith(("*", "//", "/*")):
                continue
            if 'type="date"' in line:
                offenders.append(f"{f.relative_to(web)}:{i}")

    assert not offenders, (
        "تقويم المتصفح الأصلي في الشاشات — استخدم DateField:\n"
        + "\n".join(offenders)
    )
