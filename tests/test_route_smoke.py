"""
حارس الشاشات — كل مسارٍ يفتح أو يُمنع بأدب (ق-147).

⚠️⚠️ **فجوةٌ كشفها جواد**: ٩٧٠ حارسًا يفحصون المنطق، **ولا أحدَ
يفحص أن الشاشات تفتح** — فكسرٌ في الواجهة أو المسار يمرّ خضراءَ
كلّها.

**وهذا الحارس يمرّ على كل مسارٍ بأدوارٍ مختلفة**، ويتأكّد:

١. **لا خطأ خادم** — فـ٥٠٠ علّةٌ لا سياسة.
٢. **ما يجب أن يُتاح متاح** — كملفّ الموظف نفسه.
٣. **ما يُمنع يُمنع بأدب** — ٤٠٣ أو ٤٠٢، لا انهيارًا.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent

#: مساراتٌ يجب أن يفتحها **كل موظف** — ولو بلا صلاحيةٍ إدارية.
#
# ⚠️ فهذه شاشاته هو: طلباته وقسائمه وملفّه.
EMPLOYEE_ROUTES = [
    "/api/me/workspace/",
    "/api/me/dashboard/",
    "/api/me/requests/",
    "/api/me/request-types/",
    "/api/me/approvals/",
    "/api/me/leaves/",
    "/api/me/payslips/",
    "/api/me/companies/",
    "/api/me/job-changes/",
    "/api/directory/",
    "/api/me/training/",
    "/api/me/reviews/",
    "/api/me/activities/",
    "/api/me/presence/",
]

#: مساراتٌ إدارية — تُمنع بأدب لمن لا يملكها
ADMIN_ROUTES = [
    "/api/employees/",
    "/api/org/departments/",
    "/api/org/job-titles/",
    "/api/sites/",
    "/api/access/roles/",
    "/api/payroll/runs/",
    "/api/payroll/settings/",
    "/api/attendance/shifts/",
    "/api/penalties/",
    "/api/advances/",
    "/api/reports/",
]

#: ⚠️ **ما يُمنع بالباقة** يردّ ٤٠٢ لا ٥٠٠
FEATURE_ROUTES = [
    "/api/activities/",
    "/api/presence/",
    "/api/performance/kpis/",
    "/api/expenses/",
    "/api/recurring/",
    "/api/deferrals/",
    "/api/custom-request-types/",
    "/api/allowances/",
    "/api/training/courses/",
    "/api/training/nominations/",
    "/api/training/requests/",
]

#: أخطاءُ الخادم — ما عداها سياسةٌ لا علّة
SERVER_ERRORS = (500, 501, 502, 503)


@pytest.fixture
def env(db):
    """حسابٌ بثلاثة أدوار: موظف عاديّ ومشرف وموارد."""
    r = provision_account(slug="smoke-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        def hire(first, family, nid, mob, no, role_code, username):
            p, _ = create_person(
                account=acc, first_name_ar=first, family_name_ar=family,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("8000"))])
            u = User.objects.create_user(username=username, password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            if role_code:
                RoleAssignment.objects.create(
                    membership=m, employment=e,
                    role=Role.objects.get(account=acc, code=role_code),
                    company=comp, scope=Scope.COMPANY.value)
            return u, e

        staff_u, staff_e = hire("سعد", "الحارثي", "1077788899",
                                "0507778889", "S-1", "employee",
                                "smoke.staff")
        hr_u, hr_e = hire("ريم", "السلمي", "1088899900",
                          "0508889990", "S-2", "hr_manager",
                          "smoke.hr")

        yield {"account_id": r.account_id, "comp": comp,
               "staff": staff_u, "staff_emp": staff_e,
               "hr": hr_u, "hr_emp": hr_e}


def _check(client, path, label):
    """
    ⚠️ **لا خطأ خادم** — فـ٥٠٠ علّةٌ لا سياسة.
    """
    res = client.get(path)
    assert res.status_code not in SERVER_ERRORS, (
        f"{label}: {path} انهار بـ{res.status_code} — "
        f"{res.content[:200]}")
    return res


def test_employee_routes_open_for_staff(env, client):
    """
    ⚠️⚠️ الأهمّ: **شاشات الموظف تفتح له**.

    فطلباته وقسائمه وملفّه ليست إداريةً — وحجبُها يجعل النظام
    عديم النفع لمن لا يملك صلاحية.
    """
    client.force_login(env["staff"])
    broken = []
    for path in EMPLOYEE_ROUTES:
        res = _check(client, path, "موظف")
        if res.status_code not in (200, 204, 402, 404):
            broken.append((path, res.status_code))
    assert not broken, f"مسارات موظفٍ محجوبة: {broken}"


def test_own_profile_opens_for_staff(env, client):
    """
    ⚠️⚠️ **وملفّه هو يفتح له** — وهي العلّة التي كشفها جواد:
    «ملفي» كان يُعيد للرئيسية لأن المسار إداريّ.
    """
    client.force_login(env["staff"])
    res = _check(client, f"/api/employees/{env['staff_emp'].id}/",
                 "ملفّه")
    assert res.status_code == 200, (
        f"لا يرى ملفّه — {res.status_code}")


def test_admin_routes_refuse_politely(env, client):
    """
    ⚠️ **وما يُمنع يُمنع بأدب**: ٤٠٣ لا انهيارًا.

    فالمنع سياسة، والانهيار علّة.
    """
    client.force_login(env["staff"])
    rude = []
    for path in ADMIN_ROUTES:
        res = _check(client, path, "منع")
        if res.status_code not in (200, 403, 402, 404):
            rude.append((path, res.status_code))
    assert not rude, f"مُنعت بغير أدب: {rude}"


def test_admin_routes_open_for_hr(env, client):
    """**والإدارية تفتح للموارد** — فمن يملكها يصل إليها."""
    client.force_login(env["hr"])
    broken = []
    for path in ADMIN_ROUTES:
        res = _check(client, path, "موارد")
        if res.status_code not in (200, 204, 402, 404):
            broken.append((path, res.status_code))
    assert not broken, f"محجوبةٌ عن الموارد: {broken}"


def test_feature_routes_never_crash(env, client):
    """
    ⚠️ **وما يُمنع بالباقة يردّ ٤٠٢ لا ٥٠٠**.

    فحارس الميزة سياسةٌ معلَنة، وانهيارُه علّة.
    """
    for who in ("staff", "hr"):
        client.force_login(env[who])
        for path in FEATURE_ROUTES:
            res = _check(client, path, f"ميزة/{who}")
            assert res.status_code in (200, 204, 402, 403, 404), (
                f"{path} ردّ {res.status_code} لـ{who}")


def test_no_route_returns_404_by_typo(env, client):
    """
    ⚠️ **ولا مسارَ في القائمة يردّ ٤٠٤**: فذاك يعني مسارًا
    مكتوبًا في الواجهة وغير مسجَّلٍ في الخادم — كـcost-centers.
    """
    client.force_login(env["hr"])
    missing = []
    for path in EMPLOYEE_ROUTES + ADMIN_ROUTES:
        if client.get(path).status_code == 404:
            missing.append(path)
    assert not missing, f"مسارات غير مسجَّلة: {missing}"


# ══════════ شاشات الواجهة (ق-147) ══════════
#
# ⚠️⚠️ **وعلّة «ملفي» كانت هنا لا في الخادم**: المسار يردّ ٢٠٠،
# **والواجهة تُعيد للرئيسية** لأن حارس القائمة يطابق البادئة.
#
# فنفحص منطق الحارس نفسه — لا الشاشة المبنيّة.

def _nav_guard_redirects(pathname, nav_hrefs, own_employment_id,
                         allowed_hrefs):
    """
    محاكاةُ حارس القائمة في AppShell.

    ⚠️ **وملفّ الموظف نفسه استثناء** — وهو ما فات علينا.
    """
    if pathname == "/":
        return False
    if own_employment_id and pathname == f"/employees/{own_employment_id}":
        return False

    matches = [h for h in nav_hrefs
               if h != "/" and (pathname == h
                                or pathname.startswith(h + "/"))]
    if not matches:
        return False
    item = sorted(matches, key=len, reverse=True)[0]
    return item not in allowed_hrefs


NAV_HREFS = ["/", "/employees", "/attendance", "/leaves", "/requests",
             "/payroll", "/reports", "/settings", "/me/requests",
             "/me/payslips", "/directory"]


def test_own_profile_is_not_redirected():
    """
    ⚠️⚠️ **وملفّ الموظف نفسه لا يُعاد** — وهي علّة جواد بعينها:
    «ملفي» يشير إلى /employees/<id> فيطابق البند الإداريّ.
    """
    # موظفٌ لا يملك /employees
    assert _nav_guard_redirects(
        "/employees/56", NAV_HREFS, own_employment_id=56,
        allowed_hrefs=["/me/requests", "/directory"]) is False


def test_other_profile_is_redirected():
    """**وملفّ غيره يُعاد** — فالاستثناء لنفسه لا لسواه."""
    assert _nav_guard_redirects(
        "/employees/99", NAV_HREFS, own_employment_id=56,
        allowed_hrefs=["/me/requests"]) is True


def test_allowed_route_passes():
    """وما يملكه يمرّ."""
    assert _nav_guard_redirects(
        "/me/requests", NAV_HREFS, own_employment_id=56,
        allowed_hrefs=["/me/requests"]) is False


def test_home_never_redirects():
    """⚠️ **والرئيسية لا تُفحص** — وإلا صارت الحلقة لا نهائية."""
    assert _nav_guard_redirects(
        "/", NAV_HREFS, own_employment_id=56,
        allowed_hrefs=[]) is False


def test_appshell_has_the_own_profile_exception():
    """
    ⚠️ **والحارس الفعليّ يحمل الاستثناء** — فالمحاكاة أعلاه لا
    تكفي: تفحص منطقًا كتبتُه هنا لا ما في الشاشة.
    """
    import pathlib

    src = pathlib.Path("/app/web/src/components/AppShell.tsx")
    if not src.exists():
        src = pathlib.Path("web/src/components/AppShell.tsx")
    if not src.exists():
        pytest.skip("ملفّ الواجهة غير متاح في هذه البيئة")

    text = src.read_text(encoding="utf-8")

    # ⚠️ **والعبارة وحدها لا تكفي**: رابط «ملفي» يحويها كذلك —
    # فنفحص أنها **داخل الحارس**، أي مقترنةً بـpathname وreturn.
    i = text.find("router.replace(\"/\")")
    assert i > 0, "لا حارس قائمةٍ في الشاشة"

    guard_block = text[max(0, i - 1200):i]
    assert "pathname === `/employees/${ws.person.employment_id}`" in (
        guard_block), (
        "حارس القائمة بلا استثناءٍ لملفّ الموظف نفسه — "
        "فـ«ملفي» يُعيده للرئيسية")


# ══════════ جرد المزايا (ق-150) ══════════

def test_unguarded_features_have_no_matching_routes():
    """
    ⚠️⚠️ **حارسٌ يمنع إعادة بناء ما هو قائم**.

    **فأربع مرّات** كدنا نبني ميزةً مبنيّةً سلفًا: قوالب التصدير،
    والدرجات الوظيفية، وأجهزة البصمة، وتصدير المسير — **لأن علَم
    `is_implemented` لم يُرفع عنها**.

    فالحارس يقارن كل ميزةٍ غير معلَّمة بمسارات الخادم: **إن وُجد
    مسارٌ يحمل اسمها، فالأرجح أنها مبنيّةٌ ولم تُعلَّم**.
    """
    from django.urls import get_resolver

    from apps.core.features.catalog import FEATURES

    all_paths = []

    def walk(resolver, prefix=""):
        for p in resolver.url_patterns:
            pat = prefix + str(getattr(p, "pattern", ""))
            if hasattr(p, "url_patterns"):
                walk(p, pat)
            else:
                all_paths.append(pat)

    walk(get_resolver())
    joined = " ".join(all_paths).lower()

    # ⚠️ **مزايا لا مسارَ لها بطبيعتها** — حدودٌ وروابط خارجية
    # وأمورٌ تُقاس بمنطقٍ لا بمسار.
    EXPECTED_UNROUTED = {
        "max_companies", "max_employees",       # قيمٌ لا مزايا
        "api_access", "erp_integration",        # روابط خارجية
        "third_party_services", "whatsapp_ess",
        "gov_qiwa", "gov_mudad", "gov_muqeem", "gov_gosi",
        "nitaqat_simulator", "compliance_dashboard",
        "support_group_courses",
    }

    suspects = []
    for f in FEATURES:
        if f.implemented or f.key in EXPECTED_UNROUTED:
            continue
        # اسمٌ مشتقّ من المفتاح: biometric_devices → devices
        parts = [p for p in f.key.split("_") if len(p) > 3]
        if any(p in joined for p in parts):
            suspects.append(f.key)

    assert not suspects, (
        f"مزايا غير معلَّمة ولها مسارات — أمبنيّةٌ سلفًا؟ {suspects}")
