"""عزل الوسوم والمهام."""
from django.db import migrations

FORWARD = """
ALTER TABLE employees_employeetag ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_employeetag FORCE ROW LEVEL SECURITY;
CREATE POLICY emptag_isolation ON employees_employeetag
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE employees_employeetagassignment ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_employeetagassignment FORCE ROW LEVEL SECURITY;
CREATE POLICY emptagassign_isolation ON employees_employeetagassignment
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE employees_task ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_task FORCE ROW LEVEL SECURITY;
CREATE POLICY task_isolation ON employees_task
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS emptag_isolation ON employees_employeetag;
DROP POLICY IF EXISTS emptagassign_isolation ON employees_employeetagassignment;
DROP POLICY IF EXISTS task_isolation ON employees_task;
"""


class Migration(migrations.Migration):
    dependencies = [("employees", "0021_tags_and_tasks")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
