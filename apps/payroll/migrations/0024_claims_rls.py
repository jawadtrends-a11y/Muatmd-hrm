"""عزل المخصّصات المعتمدة."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_allowanceclaim ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_allowanceclaim FORCE ROW LEVEL SECURITY;
CREATE POLICY allowclaim_isolation ON payroll_allowanceclaim
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = "DROP POLICY IF EXISTS allowclaim_isolation ON payroll_allowanceclaim;"


class Migration(migrations.Migration):
    dependencies = [("payroll", "0023_allowance_claims")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
