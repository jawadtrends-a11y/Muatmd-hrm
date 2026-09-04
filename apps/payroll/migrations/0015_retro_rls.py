"""
عزل جدول التسويات الرجعية (ق-69).

يحمل account_id من CompanyScopedModel — وتسرّبه يكشف فروق رواتب
شركة في أخرى.
"""
from django.db import migrations


FORWARD = """
ALTER TABLE payroll_retroadjustment ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_retroadjustment FORCE ROW LEVEL SECURITY;

CREATE POLICY retro_isolation ON payroll_retroadjustment
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON payroll_retroadjustment
    TO hrm_runtime;
GRANT USAGE, SELECT ON SEQUENCE payroll_retroadjustment_id_seq
    TO hrm_runtime;
"""

BACKWARD = """
DROP POLICY IF EXISTS retro_isolation ON payroll_retroadjustment;
ALTER TABLE payroll_retroadjustment DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("payroll", "0014_retroadjustment"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
