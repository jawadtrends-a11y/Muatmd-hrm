"""عزل خصومات البصمات (ق-٢٥٣) — على نمط 0045 حرفيًّا."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_attendancededuction ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_attendancededuction FORCE ROW LEVEL SECURITY;
CREATE POLICY attendance_deduction_isolation ON payroll_attendancededuction
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = ("DROP POLICY IF EXISTS attendance_deduction_isolation "
           "ON payroll_attendancededuction;")


class Migration(migrations.Migration):
    dependencies = [("payroll", "0050_attendance_deduction")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
