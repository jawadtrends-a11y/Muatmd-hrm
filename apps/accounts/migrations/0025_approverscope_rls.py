"""
عزل جدول تخصيصات الاعتماد (ق-74).

تسرّبه يكشف بنية الاعتماد في شركة أخرى: من يقرّر في ماذا.
"""
from django.db import migrations


FORWARD = """
ALTER TABLE accounts_approverscope ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_approverscope FORCE ROW LEVEL SECURITY;

CREATE POLICY approverscope_isolation ON accounts_approverscope
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON accounts_approverscope
    TO hrm_runtime;
GRANT USAGE, SELECT ON SEQUENCE accounts_approverscope_id_seq
    TO hrm_runtime;
"""

BACKWARD = """
DROP POLICY IF EXISTS approverscope_isolation ON accounts_approverscope;
ALTER TABLE accounts_approverscope DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_approverscope"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
