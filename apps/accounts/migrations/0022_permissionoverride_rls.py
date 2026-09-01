"""
عزل جدول استثناءات الصلاحيات (ق-67).

الجدول لا يحمل account_id مباشرة — يصل للحساب عبر العضوية، كما
RoleAssignment تمامًا. فالسياسة تفحص عضويته لا عموده.

وجدول الصلاحيات من أخطر ما يُعزل: تسرّبه بين الحسابات يعني أن
استثناءً في شركة قد يُقرأ أو يُطبَّق في أخرى.
"""
from django.db import migrations


FORWARD = """
ALTER TABLE accounts_permissionoverride ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_permissionoverride FORCE ROW LEVEL SECURITY;

CREATE POLICY permissionoverride_isolation ON accounts_permissionoverride
    USING (EXISTS (
        SELECT 1 FROM accounts_accountmembership m
        WHERE m.id = membership_id AND m.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM accounts_accountmembership m
        WHERE m.id = membership_id AND m.account_id = app_current_account_id()
    ));

GRANT SELECT, INSERT, UPDATE, DELETE ON accounts_permissionoverride TO hrm_runtime;
GRANT USAGE, SELECT ON SEQUENCE accounts_permissionoverride_id_seq TO hrm_runtime;
"""

BACKWARD = """
DROP POLICY IF EXISTS permissionoverride_isolation ON accounts_permissionoverride;
ALTER TABLE accounts_permissionoverride DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0021_permissionoverride"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
