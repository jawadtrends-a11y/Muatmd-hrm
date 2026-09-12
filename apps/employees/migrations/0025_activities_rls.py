"""عزل أنشطة العمل (ق-143)."""
from django.db import migrations

FORWARD = """
ALTER TABLE employees_workactivity ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_workactivity FORCE ROW LEVEL SECURITY;
CREATE POLICY activity_isolation ON employees_workactivity
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = "DROP POLICY IF EXISTS activity_isolation ON employees_workactivity;"


class Migration(migrations.Migration):
    dependencies = [("employees", "0024_work_activities")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
