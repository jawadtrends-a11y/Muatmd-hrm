"""عزل سلسلة موافقات المسير."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_payrollapprovalstep ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_payrollapprovalstep FORCE ROW LEVEL SECURITY;
CREATE POLICY payrollstep_isolation ON payroll_payrollapprovalstep
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE payroll_payrollapproval ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_payrollapproval FORCE ROW LEVEL SECURITY;
CREATE POLICY payrollapproval_isolation ON payroll_payrollapproval
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS payrollstep_isolation ON payroll_payrollapprovalstep;
DROP POLICY IF EXISTS payrollapproval_isolation ON payroll_payrollapproval;
"""


class Migration(migrations.Migration):
    dependencies = [("payroll", "0035_payroll_approval_chain")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
