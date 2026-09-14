"""
حرّاس البحث والترقيم (ق-١٦٦ و١٦٧).

**بلاغ جواد:** لا خيارات بحثٍ وفلترة، **ولا فلترةَ عددية
للنتائج** — وشركةٌ بألف موظف لا تُعرض في صفحةٍ واحدة.

⚠️⚠️ **والبحث في الخادم لا العميل**: فالعميل لا يملك إلا صفحته،
**وبحثٌ فيها يُخفي من في الصفحات الأخرى**.
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
from apps.core.pagination import PAGE_SIZES, paginate, page_params
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.payroll.models import PayComponent

NAMES = [
    ("مشعل", "الدوسري", "1011100011", "0501100011"),
    ("غادة", "العمري", "1022200022", "0502200022"),
    ("تركي", "الزهراني", "1033300033", "0503300033"),
    ("ليان", "المالكي", "1044400044", "0504400044"),
    ("بسام", "الحازمي", "1055500055", "0505500055"),
]


@pytest.fixture
def env(db):
    r = provision_account(slug="srch-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        first = None
        for i, (fn, ln, nid, mob) in enumerate(NAMES):
            p, _ = create_person(
                account=acc, first_name_ar=fn, family_name_ar=ln,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=f"S-{i:02d}",
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("8000"))])
            if first is None:
                first = (p, e)

        u = User.objects.create_user(username="srch.hr", password="x")
        first[0].user = u
        first[0].save(update_fields=["user"])
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, employment=first[1],
            role=Role.objects.get(account=acc, code="hr_manager"),
            company=comp, scope=Scope.COMPANY.value)

        yield {"account_id": r.account_id, "user": u}


# ══════════ الترقيم ══════════

def test_page_params_survive_garbage():
    """
    ⚠️ **وقيمةٌ خاطئة لا تُسقط الطلب**: فـ`page=abc` يرجع للأولى
    **لا لخطأ ٥٠٠**.
    """
    class R:
        GET = {"page": "abc", "page_size": "xyz"}

    page, size = page_params(R())
    assert page == 1
    assert size in PAGE_SIZES or size > 0


def test_page_size_is_capped():
    """
    ⚠️ **وسقفٌ صلب**: فطلبُ ٥٠٠٠٠ صفّ **يُسقط الخادم** — والسقف
    حمايةٌ لا تقييد.
    """
    class R:
        GET = {"page_size": "99999"}

    _p, size = page_params(R())
    assert size <= 200


def test_response_has_meta(env, client):
    """
    ⚠️⚠️ **وصيغةٌ موحّدة `{rows, meta}`** — فترقيمٌ مختلفٌ في كل
    مسار **يجعل الواجهة تخمّن**.
    """
    client.force_login(env["user"])
    j = client.get("/api/employees/?page_size=2").json()
    assert "rows" in j and "meta" in j, j
    m = j["meta"]
    for k in ("page", "page_size", "total", "pages",
              "has_next", "has_prev"):
        assert k in m, f"ناقص: {k}"
    assert len(j["rows"]) == 2
    assert m["total"] == 5


def test_pages_do_not_overlap(env, client):
    """
    ⚠️⚠️ **ولا تكرارَ بين صفحتين ولا فجوة**: فصفٌّ يظهر مرّتين
    **يُربك العدّ**، وصفٌّ لا يظهر أبدًا **يضيع**.
    """
    client.force_login(env["user"])
    seen = []
    for p in (1, 2, 3):
        j = client.get(f"/api/employees/?page_size=2&page={p}").json()
        seen += [r["employee_no"] for r in j["rows"]]
    assert len(seen) == len(set(seen)), f"تكرار: {seen}"
    assert len(seen) == 5, seen


def test_page_beyond_last_returns_last(env, client):
    """
    ⚠️ **وصفحةٌ بعد الأخيرة تُرجع الأخيرة**: فمن طلب ٩٩ في قائمةٍ
    من ثلاث **يرى الثالثة لا فراغًا**.
    """
    client.force_login(env["user"])
    j = client.get("/api/employees/?page_size=2&page=99").json()
    assert j["rows"], "صفحةٌ فارغة"
    assert j["meta"]["page"] == j["meta"]["pages"]


def test_all_bypasses_pagination(env, client):
    """
    ⚠️ **و`all=1` يتجاوز الترقيم** — للقوائم المنسدلة: فمن يختار
    موظفًا **يحتاج الكلّ لا صفحة**.
    """
    client.force_login(env["user"])
    j = client.get("/api/employees/?all=1").json()
    assert isinstance(j, list), "لم يتجاوز الترقيم"
    assert len(j) == 5


# ══════════ البحث ══════════

def test_search_by_employee_no(env, client):
    """والبحث بالرقم الوظيفيّ."""
    client.force_login(env["user"])
    j = client.get("/api/employees/?q=S-02").json()
    assert j["meta"]["total"] == 1
    assert j["rows"][0]["employee_no"] == "S-02"


def test_search_by_first_name(env, client):
    """
    ⚠️⚠️ **والبحث بالاسم الأول** — فكان في **اسم العائلة وحده**،
    ومن يبحث باسمه الأول **لا يجده** (بلاغ جواد).
    """
    client.force_login(env["user"])
    j = client.get("/api/employees/?q=غادة").json()
    assert j["meta"]["total"] == 1, j["meta"]


def test_search_by_id_number(env, client):
    """وبرقم الهوية."""
    client.force_login(env["user"])
    j = client.get("/api/employees/?q=1033300033").json()
    assert j["meta"]["total"] == 1


def test_search_narrows_the_total(env, client):
    """
    ⚠️ **والإجمالي يتبع البحث**: فإجمالٌ ثابتٌ مع بحثٍ **يجعل
    التنقّل يعد صفحاتٍ فارغة**.
    """
    client.force_login(env["user"])
    wide = client.get("/api/employees/").json()["meta"]["total"]
    narrow = client.get("/api/employees/?q=تركي").json()["meta"]["total"]
    assert narrow < wide
    assert narrow == 1


def test_search_finds_nothing_gracefully(env, client):
    """وبحثٌ بلا نتيجة يُرجع فراغًا لا خطأً."""
    client.force_login(env["user"])
    j = client.get("/api/employees/?q=لاأحدبهذاالاسم").json()
    assert j["rows"] == []
    assert j["meta"]["total"] == 0
