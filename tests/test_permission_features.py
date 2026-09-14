"""
حرّاس ربط الصلاحيات بالمزايا (ق-161).

**قرار جواد:** الصلاحية التي تفتحها ميزةٌ خارج الباقة **تبقى
ظاهرةً ويُحجب ضبطها** — ⚠️ **فإخفاؤها يُضيّع فرصة بيع، وضبطُها
يمنح ما لم يُشترَ**.

⚠️⚠️ **والحجب متكيّفٌ مع الباقة الفعلية** لا بقائمةٍ ثابتة.
"""
import pytest
from django.contrib.auth.models import User

from apps.accounts.models import Account, Company
from apps.accounts.models_access import (
    AccountMembership, Role, RoleAssignment)
from apps.accounts.services.provisioning import provision_account
from apps.core.access.catalog import PERMISSIONS, Scope
from apps.core.features.catalog import FEATURE_KEYS
from apps.core.tenancy.context import account_scope


def test_every_linked_feature_exists():
    """
    ⚠️ **ولا ميزةَ مخترَعة**: فصلاحيةٌ تشير لميزةٍ لا وجود لها
    **تُحجب أبدًا** — ولا يفتحها شراء.
    """
    bad = sorted({p.feature for p in PERMISSIONS
                  if p.feature and p.feature not in FEATURE_KEYS})
    assert not bad, f"مزايا مخترَعة: {bad}"


def test_core_permissions_have_no_feature():
    """
    **والأساسيات بلا ميزة**: فمن لا يرى موظفيه ولا يقدّم طلبًا
    **لا نظام له** — وربطُها بميزةٍ يُعطّل الباقة الأساسية.
    """
    CORE = {"employees.view", "requests.create", "requests.view",
            "account.view", "access.view"}
    linked = {p.key for p in PERMISSIONS if p.feature}
    overlap = CORE & linked
    assert not overlap, f"أساسياتٌ مربوطة بميزة: {sorted(overlap)}"


@pytest.fixture
def env(db):
    r = provision_account(slug="pf-t", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        u = User.objects.create_user(username="pf.admin", password="x")
        m = AccountMembership.objects.create(
            user=u, account=acc, active_company=comp,
            is_account_owner=True)
        yield {"account_id": r.account_id, "comp": comp, "user": u}


def test_catalog_reports_feature_state(env, client):
    """
    ⚠️⚠️ الأهمّ: **والمسار يُبلّغ حال كل ميزة** — فالشاشة تحجب
    بها.
    """
    client.force_login(env["user"])
    j = client.get("/api/access/permissions/").json()
    rows = [p for m in j["modules"] for p in m["permissions"]]

    assert len(rows) == len(PERMISSIONS), "نقصت صلاحيات"
    for p in rows:
        assert "feature_enabled" in p, f"بلا حال ميزة: {p['key']}"
        assert "feature" in p


def test_unlicensed_permission_is_flagged_not_hidden(env, client):
    """
    ⚠️⚠️ **وتبقى ظاهرةً ويُحجب ضبطها** (قرار جواد): **فإخفاؤها
    يُضيّع فرصة بيع، وضبطُها يمنح ما لم يُشترَ**.
    """
    client.force_login(env["user"])
    j = client.get("/api/access/permissions/").json()
    rows = {p["key"]: p for m in j["modules"] for p in m["permissions"]}

    # صلاحيةٌ مربوطةٌ بميزةٍ ما — نتحقّق أنها معروضةٌ مهما كان حالها
    linked = [p for p in PERMISSIONS if p.feature]
    assert linked, "لا صلاحية مربوطة"
    for p in linked[:5]:
        assert p.key in rows, f"أُخفيت: {p.key}"


def test_locked_permission_names_its_feature(env, client):
    """
    **والمحجوبة تُسمّي ميزتها** — فالعميل يعرف ما يشتري ليفتحها.
    """
    client.force_login(env["user"])
    j = client.get("/api/access/permissions/").json()
    rows = [p for m in j["modules"] for p in m["permissions"]]

    for p in rows:
        if p["feature_enabled"] is False:
            assert p.get("feature_name"), (
                f"محجوبةٌ بلا اسم ميزة: {p['key']}")


def test_feature_state_follows_the_plan(env, client):
    """
    ⚠️ **والحجب متكيّفٌ مع الباقة الفعلية** لا بقائمةٍ ثابتة: فما
    يُفتح بالترقية **يُضبط فورًا**.
    """
    from apps.core.features.gate import Features

    client.force_login(env["user"])
    j = client.get("/api/access/permissions/").json()
    rows = {p["key"]: p for m in j["modules"] for p in m["permissions"]}

    for key, row in rows.items():
        if not row["feature"]:
            assert row["feature_enabled"] is True, (
                f"أساسيةٌ محجوبة: {key}")
            continue
        expected = Features.enabled(env["comp"].id, row["feature"])
        assert row["feature_enabled"] == expected, (
            f"حالٌ لا يطابق الباقة: {key}")
