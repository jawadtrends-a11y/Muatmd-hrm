"""
حرّاس العزل — يفشل البناء عند أي خرق.

ملاحظة جوهرية: اتصال الاختبار الافتراضي يعمل بدور المالك (خارق)
لأنه ينشئ قاعدة الاختبار. لذلك كل اختبار عزل حقيقي يستخدم
runtime_cursor — الاتصال بدور التشغيل المحدود.

راجع الوثيقة المعمارية (2) القسمين 2 و7.2.
"""
import pytest
from django.db import connection

from apps.accounts.models import Account, Company


# ══════════ فحوص بنيوية (تعمل بالمالك — لا تحتاج عزلًا) ══════════

@pytest.mark.django_db
def test_every_business_table_has_rls():
    """كل جدول عمل يحمل RLS مفعّلًا وإجباريًا."""
    exempt = {
        "django_migrations", "django_content_type", "django_session",
        "django_admin_log", "auth_user", "auth_group", "auth_permission",
        "auth_group_permissions", "auth_user_groups",
        "auth_user_user_permissions",
    }
    with connection.cursor() as cur:
        cur.execute("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
        """)
        rows = cur.fetchall()
    unprotected = [
        name for name, enabled, forced in rows
        if name not in exempt and not (enabled and forced)
    ]
    assert not unprotected, f"جداول بلا RLS: {unprotected}"


@pytest.mark.django_db
def test_runtime_role_is_restricted():
    """دور التشغيل نفسه — لا خارق ولا متجاوز لـRLS."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname='hrm_runtime'"
        )
        is_super, bypass = cur.fetchone()
    assert not is_super, "دور التشغيل خارق — العزل معطّل"
    assert not bypass, "دور التشغيل يتجاوز RLS — العزل معطّل"


# ══════════ فحوص العزل الفعلي (بدور التشغيل) ══════════

@pytest.fixture
def two_accounts(db):
    """حسابان بشركتين — يُنشآن بالمالك لتجاوز WITH CHECK."""
    a1 = Account.objects.create(slug="acc-one", display_name_ar="الحساب الأول")
    a2 = Account.objects.create(slug="acc-two", display_name_ar="الحساب الثاني")
    c1 = Company.objects.create(account=a1, code="C1", legal_name_ar="شركة الأول")
    c2 = Company.objects.create(account=a2, code="C1", legal_name_ar="شركة الثاني")
    return a1, a2, c1, c2


def _scoped(cur, account_id):
    cur.execute("SELECT set_config('app.account_id', %s, FALSE)", [str(account_id)])


@pytest.mark.django_db(transaction=True)
def test_no_context_returns_zero_rows(runtime_cursor, two_accounts):
    """بلا سياق: صفر صفوف مهما كان في الجدول (fail closed)."""
    runtime_cursor.execute("SELECT set_config('app.account_id','',FALSE)")
    runtime_cursor.execute("SELECT count(*) FROM accounts_account")
    assert runtime_cursor.fetchone()[0] == 0
    runtime_cursor.execute("SELECT count(*) FROM accounts_company")
    assert runtime_cursor.fetchone()[0] == 0


@pytest.mark.django_db(transaction=True)
def test_account_sees_only_itself(runtime_cursor, two_accounts):
    """كل حساب يرى نفسه فقط."""
    a1, a2, _, _ = two_accounts
    _scoped(runtime_cursor, a1.id)
    runtime_cursor.execute("SELECT id FROM accounts_account")
    assert [r[0] for r in runtime_cursor.fetchall()] == [a1.id]


@pytest.mark.django_db(transaction=True)
def test_cannot_read_other_account_explicitly(runtime_cursor, two_accounts):
    """طلب صف الحساب الآخر بمعرّفه صراحةً لا يُرجع شيئًا."""
    a1, a2, _, c2 = two_accounts
    _scoped(runtime_cursor, a1.id)
    runtime_cursor.execute("SELECT count(*) FROM accounts_account WHERE id=%s", [a2.id])
    assert runtime_cursor.fetchone()[0] == 0
    runtime_cursor.execute("SELECT count(*) FROM accounts_company WHERE id=%s", [c2.id])
    assert runtime_cursor.fetchone()[0] == 0


@pytest.mark.django_db(transaction=True)
def test_cannot_update_other_account(runtime_cursor, two_accounts):
    """التعديل على حساب آخر لا يؤثر على أي صف."""
    a1, a2, _, _ = two_accounts
    _scoped(runtime_cursor, a1.id)
    runtime_cursor.execute(
        "UPDATE accounts_account SET display_name_ar='مخترق' WHERE id=%s", [a2.id]
    )
    assert runtime_cursor.rowcount == 0
    a2.refresh_from_db()
    assert a2.display_name_ar == "الحساب الثاني"


@pytest.mark.django_db(transaction=True)
def test_cannot_insert_into_other_account(runtime_cursor, two_accounts):
    """زرع صف تحت حساب آخر يُرفض بخطأ صريح (WITH CHECK)."""
    import psycopg
    a1, a2, _, _ = two_accounts
    _scoped(runtime_cursor, a1.id)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        runtime_cursor.execute(
            "INSERT INTO accounts_company (account_id, code, legal_name_ar,"
            " legal_name_en, cr_number, unified_national_number, vat_number,"
            " gosi_establishment_no, mol_establishment_no, activity_code,"
            " entity_size, fiscal_year_start_month, is_active,"
            " created_at, updated_at)"
            " VALUES (%s,'HACK','مزروعة','','','','','','','','',1,TRUE,now(),now())",
            [a2.id],
        )
