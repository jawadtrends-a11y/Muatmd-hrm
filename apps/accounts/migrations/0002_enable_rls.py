"""
تفعيل عزل الصفوف على جداول الحسابات.

FORCE ROW LEVEL SECURITY يُخضع حتى مالك الجدول للسياسة.
راجع الوثيقة المعمارية (2) القسم 2.
"""
from django.db import migrations

FORWARD = """
-- ══ جدول الحسابات ══
-- الحساب يرى نفسه فقط. سطر واحد لكل جلسة.
ALTER TABLE accounts_account ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_account FORCE ROW LEVEL SECURITY;

CREATE POLICY account_self_isolation ON accounts_account
    USING (id = app_current_account_id())
    WITH CHECK (id = app_current_account_id());

-- ══ جدول الشركات ══
-- عزل على مستويين: الحساب مطلق، والشركة ضمن المصرّح به.
ALTER TABLE accounts_company ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_company FORCE ROW LEVEL SECURITY;

CREATE POLICY company_isolation ON accounts_company
    USING (
        account_id = app_current_account_id()
        AND (
            app_current_company_ids() IS NULL
            OR id = ANY(app_current_company_ids())
        )
    )
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS account_self_isolation ON accounts_account;
DROP POLICY IF EXISTS company_isolation ON accounts_company;
ALTER TABLE accounts_account DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_company DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("core", "0001_rls_helpers"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
