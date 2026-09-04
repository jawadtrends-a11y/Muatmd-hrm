"""
عزل جدول التغييرات الوظيفية (ق-82).

يحمل account_id من CompanyScopedModel — وتسرّبه يكشف ترقيات
شركة وفصولها في أخرى.
"""
from django.db import migrations


FORWARD = """
ALTER TABLE employees_jobchange ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_jobchange FORCE ROW LEVEL SECURITY;

CREATE POLICY jobchange_isolation ON employees_jobchange
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON employees_jobchange TO hrm_runtime;
GRANT USAGE, SELECT ON SEQUENCE employees_jobchange_id_seq TO hrm_runtime;
"""

BACKWARD = """
DROP POLICY IF EXISTS jobchange_isolation ON employees_jobchange;
ALTER TABLE employees_jobchange DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0007_jobchange"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
