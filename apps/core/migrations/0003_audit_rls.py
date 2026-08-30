"""عزل سجل العمليات — شركة لا ترى سجل أخرى."""
from django.db import migrations

FORWARD = """
ALTER TABLE core_auditentry ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_auditentry FORCE ROW LEVEL SECURITY;
CREATE POLICY core_auditentry_isolation ON core_auditentry
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS core_auditentry_isolation ON core_auditentry;
ALTER TABLE core_auditentry DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_audit_entry"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
