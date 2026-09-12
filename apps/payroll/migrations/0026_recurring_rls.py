"""عزل البنود المكرّرة."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_recurringadjustment ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_recurringadjustment FORCE ROW LEVEL SECURITY;
CREATE POLICY recur_isolation ON payroll_recurringadjustment
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = "DROP POLICY IF EXISTS recur_isolation ON payroll_recurringadjustment;"


class Migration(migrations.Migration):
    dependencies = [("payroll", "0025_recurring_adjustments")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
