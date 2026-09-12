"""عزل البنود المؤجَّلة."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_payslipdeferral ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_payslipdeferral FORCE ROW LEVEL SECURITY;
CREATE POLICY defer_isolation ON payroll_payslipdeferral
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = "DROP POLICY IF EXISTS defer_isolation ON payroll_payslipdeferral;"


class Migration(migrations.Migration):
    dependencies = [("payroll", "0027_payslip_deferrals")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
