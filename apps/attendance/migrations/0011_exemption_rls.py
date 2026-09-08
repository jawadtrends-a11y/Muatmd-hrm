"""عزل جدول الإعفاءات."""
from django.db import migrations

FORWARD = """
ALTER TABLE attendance_attendanceexemption ENABLE ROW LEVEL SECURITY;
ALTER TABLE attendance_attendanceexemption FORCE ROW LEVEL SECURITY;
CREATE POLICY exemption_isolation ON attendance_attendanceexemption
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""
REVERSE = """
DROP POLICY IF EXISTS exemption_isolation ON attendance_attendanceexemption;
"""


class Migration(migrations.Migration):
    dependencies = [("attendance", "0010_exemption_and_default_shift")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
