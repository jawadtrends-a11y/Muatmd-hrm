"""عزل كتالوج المخصّصات واستحقاقاتها."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_claimableallowance ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_claimableallowance FORCE ROW LEVEL SECURITY;
CREATE POLICY claimallow_isolation ON payroll_claimableallowance
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE payroll_allowanceeligibility ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_allowanceeligibility FORCE ROW LEVEL SECURITY;
CREATE POLICY alloweligib_isolation ON payroll_allowanceeligibility
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS claimallow_isolation ON payroll_claimableallowance;
DROP POLICY IF EXISTS alloweligib_isolation ON payroll_allowanceeligibility;
"""


class Migration(migrations.Migration):
    dependencies = [("payroll", "0021_claimable_allowances")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
