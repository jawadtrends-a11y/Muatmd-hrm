"""عزل نبضات التواجد وخلاصاته."""
from django.db import migrations

FORWARD = """
ALTER TABLE attendance_presenceping ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_presenceping FORCE ROW LEVEL SECURITY;
CREATE POLICY ping_isolation ON attendance_presenceping
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE attendance_presenceday ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_presenceday FORCE ROW LEVEL SECURITY;
CREATE POLICY presday_isolation ON attendance_presenceday
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS ping_isolation ON attendance_presenceping;
DROP POLICY IF EXISTS presday_isolation ON attendance_presenceday;
"""


class Migration(migrations.Migration):
    dependencies = [("attendance", "0013_presence_tracking")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
