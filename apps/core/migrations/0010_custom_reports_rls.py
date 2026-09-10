"""عزل التقارير المخصّصة."""
from django.db import migrations

FORWARD = """
ALTER TABLE core_customreport ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_customreport FORCE ROW LEVEL SECURITY;
CREATE POLICY customreport_isolation ON core_customreport
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = "DROP POLICY IF EXISTS customreport_isolation ON core_customreport;"


class Migration(migrations.Migration):
    dependencies = [("core", "0009_custom_reports")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
