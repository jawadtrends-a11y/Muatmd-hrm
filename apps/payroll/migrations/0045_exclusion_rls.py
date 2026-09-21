"""عزل الاستبعادات من المسير (ق-228) — على نمط 0028 حرفيًّا."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_payrollexclusion ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_payrollexclusion FORCE ROW LEVEL SECURITY;
CREATE POLICY exclusion_isolation ON payroll_payrollexclusion
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = "DROP POLICY IF EXISTS exclusion_isolation ON payroll_payrollexclusion;"


class Migration(migrations.Migration):
    dependencies = [("payroll", "0044_payrollexclusion")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
