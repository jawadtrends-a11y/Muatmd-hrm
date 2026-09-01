"""
حارس صندوق الاعتمادات — طبقة الـAPI فوق محرّك الاعتماد.

الفجوة التي يسدّها: test_approvals.py يحرس المحرّك كاملًا لكن بلا
استدعاء HTTP واحد. فالخدمة محروسة والمسار الذي يستدعيها عارٍ —
وهناك عاش الخلل: الاستعلام كان يرشّح بـApprovalDecision.PENDING،
وهو عضو غير موجود (الأعضاء: approved/rejected/delegated). والقيمة
الفعلية لِما لم يُقرَّر بعد هي السلسلة الفارغة "" كما يستخدمها
محرّك decide نفسه.

فـ/api/me/approvals/ كان ينهار بـ500 عند أول فتح من معتمِد —
وهو أول ما يفتحه كل مدير.
"""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client

from apps.accounts.models import Account, Company
from apps.accounts.models_access import AccountMembership, Role, RoleAssignment
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import Scope
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import create_employment, create_person
from apps.leaves.models import Request, RequestStatus, RequestType
from apps.leaves.services.approvals import submit_request


@pytest.fixture
def env(db):
    """مدير مربوط بحساب دخول، وموظف تحته، وطلب معلّق بانتظاره."""
    r = provision_account(slug="inbox-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)

        # المستخدم يُربط بالشخص — بدونه _my_employment ترجع None
        # فتخرج الدالة مبكرًا ولا تلمس الكود المقصود
        u = User.objects.create_user(username="inbox.mgr", password="x")
        role = Role.objects.get(account=acc, code="supervisor")
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp)
        RoleAssignment.objects.create(
            membership=m, role=role, company=comp, scope=Scope.TEAM.value)

        pm, _ = create_person(
            account=acc, first_name_ar="خالد", family_name_ar="الحربي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011122233", mobile="0501112223", user=u)
        mgr, _, _ = create_employment(person=pm, company=comp,
                                      employee_no="M-1",
                                      join_date=date(2020, 1, 1))

        pe, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1044455566", mobile="0504445556")
        emp, _, _ = create_employment(person=pe, company=comp,
                                      employee_no="E-1",
                                      join_date=date(2022, 1, 1),
                                      direct_manager=mgr)

        req = Request.objects.create(
            account=acc, company=comp, request_no="R-1",
            employment=emp, request_type=RequestType.LEAVE,
            payload={"days": 3})
        submit_request(req)

        yield {"account_id": r.account_id, "user": u, "req": req}


@pytest.mark.django_db(transaction=True)
def test_approvals_inbox_returns_pending(env):
    """المعتمِد يفتح صندوقه فيرى الطلب المنتظر — لا انهيارًا."""
    c = Client()
    c.force_login(env["user"])
    resp = c.get("/api/me/approvals/")

    assert resp.status_code == 200, (
        f"صندوق الاعتمادات ينهار ({resp.status_code}) — "
        f"راجع قيمة «لم يُقرَّر» في الاستعلام")

    rows = resp.json()
    assert any(r["request_no"] == "R-1" for r in rows), (
        "الطلب المعلّق لا يظهر في صندوق معتمِده")
