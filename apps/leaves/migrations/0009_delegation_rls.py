"""
عزل جدول الإنابات (ق-75).

يحمل account_id من CompanyScopedModel، فالسياسة مباشرة كسائر
جداول الأعمال — وتسرّبه يعني أن إنابة شركة تُقرأ في أخرى.
"""
from django.db import migrations


FORWARD = """
ALTER TABLE leaves_delegation ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaves_delegation FORCE ROW LEVEL SECURITY;

CREATE POLICY delegation_isolation ON leaves_delegation
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON leaves_delegation TO hrm_runtime;
GRANT USAGE, SELECT ON SEQUENCE leaves_delegation_id_seq TO hrm_runtime;
"""

BACKWARD = """
DROP POLICY IF EXISTS delegation_isolation ON leaves_delegation;
ALTER TABLE leaves_delegation DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("leaves", "0008_delegation"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
