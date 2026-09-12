"""عزل المصروفات وفئاتها."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_expensecategory ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_expensecategory FORCE ROW LEVEL SECURITY;
CREATE POLICY expcat_isolation ON payroll_expensecategory
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE payroll_expenseclaim ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_expenseclaim FORCE ROW LEVEL SECURITY;
CREATE POLICY expclaim_isolation ON payroll_expenseclaim
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS expcat_isolation ON payroll_expensecategory;
DROP POLICY IF EXISTS expclaim_isolation ON payroll_expenseclaim;
"""


class Migration(migrations.Migration):
    dependencies = [("payroll", "0033_expenses")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
