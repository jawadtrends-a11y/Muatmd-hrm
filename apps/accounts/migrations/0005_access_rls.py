"""
عزل جداول الصلاحيات.

ملاحظة: الأدوار النظامية (account IS NULL) قوالب مشتركة تُقرأ
من كل الحسابات، لكن لا تُعدَّل إلا بدور المالك.
"""
from django.db import migrations

FORWARD = """
-- ══ الأدوار ══
ALTER TABLE accounts_role ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_role FORCE ROW LEVEL SECURITY;

CREATE POLICY role_read ON accounts_role FOR SELECT
    USING (account_id IS NULL OR account_id = app_current_account_id());

CREATE POLICY role_write ON accounts_role FOR INSERT
    WITH CHECK (account_id = app_current_account_id());

CREATE POLICY role_update ON accounts_role FOR UPDATE
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

CREATE POLICY role_delete ON accounts_role FOR DELETE
    USING (account_id = app_current_account_id() AND is_system = FALSE);

-- ══ صلاحيات الأدوار ══
ALTER TABLE accounts_rolepermission ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_rolepermission FORCE ROW LEVEL SECURITY;

CREATE POLICY rolepermission_isolation ON accounts_rolepermission
    USING (EXISTS (
        SELECT 1 FROM accounts_role r WHERE r.id = role_id
        AND (r.account_id IS NULL OR r.account_id = app_current_account_id())
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM accounts_role r WHERE r.id = role_id
        AND r.account_id = app_current_account_id()
    ));

-- ══ العضويات ══
ALTER TABLE accounts_accountmembership ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_accountmembership FORCE ROW LEVEL SECURITY;

CREATE POLICY membership_isolation ON accounts_accountmembership
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

-- ══ إسنادات الأدوار ══
ALTER TABLE accounts_roleassignment ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_roleassignment FORCE ROW LEVEL SECURITY;

CREATE POLICY roleassignment_isolation ON accounts_roleassignment
    USING (EXISTS (
        SELECT 1 FROM accounts_accountmembership m
        WHERE m.id = membership_id AND m.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM accounts_accountmembership m
        WHERE m.id = membership_id AND m.account_id = app_current_account_id()
    ));
"""

REVERSE = """
DROP POLICY IF EXISTS role_read ON accounts_role;
DROP POLICY IF EXISTS role_write ON accounts_role;
DROP POLICY IF EXISTS role_update ON accounts_role;
DROP POLICY IF EXISTS role_delete ON accounts_role;
DROP POLICY IF EXISTS rolepermission_isolation ON accounts_rolepermission;
DROP POLICY IF EXISTS membership_isolation ON accounts_accountmembership;
DROP POLICY IF EXISTS roleassignment_isolation ON accounts_roleassignment;
ALTER TABLE accounts_role DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_rolepermission DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_accountmembership DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_roleassignment DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_access_models")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
