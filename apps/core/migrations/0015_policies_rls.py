"""عزل السياسات وإقراراتها."""
from django.db import migrations

FORWARD = """
ALTER TABLE core_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_policy FORCE ROW LEVEL SECURITY;
CREATE POLICY policy_isolation ON core_policy
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE core_policyacknowledgement ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_policyacknowledgement FORCE ROW LEVEL SECURITY;
CREATE POLICY policyack_isolation ON core_policyacknowledgement
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS policy_isolation ON core_policy;
DROP POLICY IF EXISTS policyack_isolation ON core_policyacknowledgement;
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0014_policies")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
