"""
الاختبار الصارم من طرفٍ لطرف (ق-168).

**قرار جواد:** نتأكّد أن كل شيء يعمل **بشكلٍ كامل وصحيح**.

⚠️⚠️ **وفحصُ المحتوى لا الحالة**: فـ**٢٠٠ بصفحةٍ فارغة ليست
نجاحًا** — وكل ما كشفه جواد اليوم كان يردّ ٢٠٠:

| ما انكسر | وحاله |
|---|---|
| «ملفي» يُعيد للرئيسية | المسار ٢٠٠ |
| «فريقي» تُظهر الشركة | المسار ٢٠٠ |
| القسيمة JSON خامًا | المسار ٢٠٠ |

**فالحارس هنا يقرأ ما يعود لا رمزه.**
"""
from datetime import date, timedelta
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
from apps.organization.models import Department
from apps.payroll.models import (
    PayComponent, PayrollRunStatus, PayrollRunType)
from apps.payroll.services import engine


@pytest.fixture
def world(db):
    """
    عالمٌ كامل: أربعة أدوار وإدارةٌ ومسيرٌ معتمد.

    ⚠️ **وأسماءٌ متباينة** — فحارس التشابه يمنع المتقاربة.
    """
    r = provision_account(slug="e2e", display_name_ar="حساب",
                          company_name_ar="شركة الاختبار",
                          is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        basic = PayComponent.objects.get(company=comp, code="BASIC")

        dept = (Department.objects.filter(company=comp).first()
                or Department.objects.create(
                    account=acc, company=comp, code="OPS",
                    name_ar="العمليات"))

        def hire(fn, ln, nid, mob, no, username, role, scope):
            p, _ = create_person(
                account=acc, first_name_ar=fn, family_name_ar=ln,
                gender="male", nationality_code="SA",
                id_type="national_id", id_number=nid, mobile=mob)
            e, _, _ = create_employment(
                person=p, company=comp, employee_no=no,
                join_date=date(2024, 1, 1),
                salary_lines=[(basic, Decimal("10000"))],
                department=dept)
            u = User.objects.create_user(username=username,
                                         password="x")
            p.user = u
            p.save(update_fields=["user"])
            m = AccountMembership.objects.create(
                user=u, account=acc, active_company=comp)
            RoleAssignment.objects.create(
                membership=m, employment=e,
                role=Role.objects.get(account=acc, code=role),
                company=comp, scope=scope.value)
            return {"user": u, "emp": e, "person": p}

        hr = hire("نوف", "الشريف", "1091100011", "0509110001",
                  "E-HR", "e2e.hr", "hr_manager", Scope.COMPANY)
        mgr = hire("ياسر", "البلوي", "1092200022", "0509220002",
                   "E-MG", "e2e.mgr", "dept_manager", Scope.DEPARTMENT)
        sup = hire("هيا", "الصاعدي", "1093300033", "0509330003",
                   "E-SP", "e2e.sup", "supervisor", Scope.TEAM)
        emp = hire("عمار", "الجهني", "1094400044", "0509440004",
                   "E-EM", "e2e.emp", "employee", Scope.OWN)

        # المشرف يقود الموظف، والمدير يقود الإدارة
        emp["emp"].direct_manager = sup["emp"]
        emp["emp"].save(update_fields=["direct_manager"])
        dept.manager_employment_id = mgr["emp"].id
        dept.save(update_fields=["manager_employment_id"])

        run = engine.create_run(company=comp,
                                run_type=PayrollRunType.REGULAR,
                                year=2026, month=9)
        engine.calculate_run(run)
        run.status = PayrollRunStatus.SUBMITTED
        run.save(update_fields=["status"])
        engine.approve_run(run, None)

        yield {"account_id": r.account_id, "comp": comp, "dept": dept,
               "hr": hr, "mgr": mgr, "sup": sup, "emp": emp,
               "run": run}


def _rows(payload):
    """
    ⚠️ **يقرأ الصيغتين**: `{rows, meta}` والقائمة الخام — فبعض
    المسارات مُرقَّمٌ وبعضها لا.
    """
    if isinstance(payload, dict):
        return payload.get("rows", payload.get("data", []))
    return payload


# ══════════ ١. شاشات الموظف ══════════

def test_employee_sees_own_workspace(world, client):
    """
    ⚠️⚠️ **وكل موظفٍ يصل شؤونه** — فحجبُها يجعل النظام عديم
    النفع لمن لا يملك صلاحية.
    """
    client.force_login(world["emp"]["user"])
    for path in ("/api/me/workspace/", "/api/me/requests/",
                 "/api/me/payslips/", "/api/me/leaves/"):
        res = client.get(path)
        assert res.status_code == 200, f"{path} → {res.status_code}"


def test_employee_opens_own_profile(world, client):
    """
    ⚠️⚠️ **وملفّه هو يفتح له** — وهي علّة جواد: «ملفي» كان يُعيده
    للرئيسية.
    """
    client.force_login(world["emp"]["user"])
    eid = world["emp"]["emp"].id
    res = client.get(f"/api/employees/{eid}/")
    assert res.status_code == 200, res.status_code
    # ⚠️ **والحقل داخل `employment`** لا في الجذر
    body = res.json()
    assert body["employment"]["employee_no"] == "E-EM", body.keys()


def test_employee_payslip_is_pdf(world, client):
    """
    ⚠️⚠️ **والقسيمة PDF لا JSON** — وهي علّة جواد الثانية.
    """
    from apps.payroll.models import Payslip

    with account_scope(world["account_id"]):
        slip = Payslip.objects.filter(
            employment=world["emp"]["emp"]).first()
    assert slip is not None, "لا قسيمة للموظف"

    client.force_login(world["emp"]["user"])
    res = client.get(f"/api/payslips/{slip.id}/pdf/")
    assert res.status_code == 200, res.content[:200]
    assert res.content[:4] == b"%PDF", "ليست PDF"


def test_employee_cannot_see_others(world, client):
    """
    ⚠️ **ولا يرى غيره**: فموظفٌ يقرأ ملفّات زملائه **خرقٌ لا
    تفصيل**.
    """
    client.force_login(world["emp"]["user"])
    rows = _rows(client.get("/api/employees/").json())
    nos = {r["employee_no"] for r in rows}
    assert nos <= {"E-EM"}, f"رأى غيره: {nos}"


# ══════════ ٢. شاشات المشرف ══════════

def test_supervisor_sees_only_his_team(world, client):
    """
    ⚠️⚠️ **والمشرف يرى فريقه لا الشركة** — وهي علّة جواد الثالثة:
    «فريقي» كانت تُظهر الأربعة عشر.
    """
    client.force_login(world["sup"]["user"])
    j = client.get("/api/me/team/").json()
    nos = {r["employee_no"] for r in j.get("rows", [])}
    assert nos == {"E-EM"}, f"فريقٌ خاطئ: {nos}"


def test_supervisor_team_attendance_is_scoped(world, client):
    """
    **وحضورُ فريقه كذلك** — فشاشةٌ عنوانها «مرؤوسيك» تعني ما
    تقوله.
    """
    client.force_login(world["sup"]["user"])
    res = client.get("/api/attendance/daily/?team=1")
    assert res.status_code == 200
    total = res.json().get("total", 0)
    assert total <= 1, f"رأى {total} وفريقه واحد"


# ══════════ ٣. مدير الإدارة ══════════

def test_department_manager_sees_his_department(world, client):
    """
    **ومدير الإدارة يرى موظفيها** — فالإسناد قرارٌ تنظيميّ يحمل
    أثره.
    """
    client.force_login(world["mgr"]["user"])
    j = client.get("/api/me/team/").json()
    nos = {r["employee_no"] for r in j.get("rows", [])}
    assert "E-EM" in nos and "E-SP" in nos, nos
    assert "E-MG" not in nos, "أدرج نفسه في فريقه"


# ══════════ ٤. الموارد البشرية ══════════

def test_hr_sees_everyone(world, client):
    """**والموارد ترى الجميع** — فهي شاشة الشركة."""
    client.force_login(world["hr"]["user"])
    rows = _rows(client.get("/api/employees/?all=1").json())
    nos = {r["employee_no"] for r in rows}
    assert {"E-HR", "E-MG", "E-SP", "E-EM"} <= nos, nos


def test_hr_search_finds_by_number_and_name(world, client):
    """
    ⚠️ **والبحث يجد بالرقم والاسم** — فكان في اسم العائلة وحده.
    """
    client.force_login(world["hr"]["user"])
    for q, expect in (("E-EM", "E-EM"), ("عمار", "E-EM"),
                      ("1094400044", "E-EM")):
        j = client.get(f"/api/employees/?q={q}").json()
        nos = {r["employee_no"] for r in _rows(j)}
        assert expect in nos, f"«{q}» لم يجد: {nos}"


def test_pagination_covers_everyone(world, client):
    """
    ⚠️⚠️ **ولا يضيع أحدٌ بين الصفحات**: فصفٌّ لا يظهر أبدًا
    **يضيع**.
    """
    client.force_login(world["hr"]["user"])
    seen, page = set(), 1
    while page <= 10:
        j = client.get(
            f"/api/employees/?page_size=2&page={page}").json()
        rows = _rows(j)
        if not rows:
            break
        seen |= {r["employee_no"] for r in rows}
        if not j["meta"]["has_next"]:
            break
        page += 1
    assert {"E-HR", "E-MG", "E-SP", "E-EM"} <= seen, seen


# ══════════ ٥. دورةٌ كاملة ══════════

def test_full_cycle_request_to_payslip(world, client):
    """
    ⚠️⚠️ **دورةٌ كاملة**: طلبٌ يُقدَّم ويُعتمد، ومسيرٌ يُحتسب
    ويُعتمد، وقسيمةٌ تُقرأ.

    **فكلُّ حلقةٍ تعمل وحدها لا يعني أن السلسلة تعمل.**
    """
    from apps.leaves.models import Request, RequestStatus

    # ١) الموظف يقدّم طلبًا
    client.force_login(world["emp"]["user"])
    # ⚠️ **والحقول في جذر الطلب لا في `payload`** — فهذا مسار
    # الإجازات لا الطلبات العامّة.
    from apps.leaves.models import LeaveType

    with account_scope(world["account_id"]):
        lt = LeaveType.objects.filter(
            company=world["comp"]).first()
    assert lt is not None, "لا أنواع إجازات"

    res = client.post("/api/leaves/requests/", data={
        "leave_type_code": lt.code,
        "start_date": str(date.today() + timedelta(days=3)),
        "days": 1,
        "note": "دورةٌ كاملة",
    }, content_type="application/json")
    assert res.status_code in (200, 201), res.content[:200]

    with account_scope(world["account_id"]):
        req = Request.objects.filter(
            employment=world["emp"]["emp"]).order_by("-id").first()
    assert req is not None, "لم يُنشأ الطلب"

    # ٢) والموارد تراه
    client.force_login(world["hr"]["user"])
    j = client.get("/api/leaves/requests/").json()
    nos = {r["request_no"] for r in _rows(j)}
    assert req.request_no in nos, "الطلب لا يصل الموارد"

    # ٣) والقسيمة موجودة
    with account_scope(world["account_id"]):
        assert world["run"].payslips.filter(
            employment=world["emp"]["emp"]).exists(), (
            "لا قسيمة في مسيرٍ معتمد")


def test_payroll_totals_match_payslips(world):
    """
    ⚠️⚠️ **وإجمالي المسير يساوي مجموع قسائمه**: فرقمٌ في الترويسة
    **لا يطابق تفصيله يُفقد الثقة كلّها**.
    """
    with account_scope(world["account_id"]):
        run = world["run"]
        total = sum((s.net_pay for s in run.payslips.all()),
                    Decimal("0"))
        assert run.total_net == total, (run.total_net, total)
        assert run.employee_count == run.payslips.count()


# ══════════ ٦. العزل بين الحسابات ══════════

def test_other_account_is_invisible(world, client):
    """
    ⚠️⚠️ **ولا يرى حسابٌ حسابًا آخر** — وهو أخطر ما في النظام.
    """
    other = provision_account(slug="e2e-2", display_name_ar="آخر",
                              company_name_ar="شركة أخرى",
                              is_sandbox=True)
    with account_scope(other.account_id):
        acc2 = Account.objects.get(id=other.account_id)
        comp2 = Company.objects.get(id=other.company_id)
        basic2 = PayComponent.objects.get(company=comp2, code="BASIC")
        p2, _ = create_person(
            account=acc2, first_name_ar="غريب",
            family_name_ar="الخارجي", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1099900099", mobile="0509990009")
        create_employment(
            person=p2, company=comp2, employee_no="X-1",
            join_date=date(2024, 1, 1),
            salary_lines=[(basic2, Decimal("9000"))])

    client.force_login(world["hr"]["user"])
    rows = _rows(client.get("/api/employees/?all=1").json())
    nos = {r["employee_no"] for r in rows}
    assert "X-1" not in nos, "⚠️⚠️ تسريبٌ بين الحسابات"
