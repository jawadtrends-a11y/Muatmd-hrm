"""عزل جدول الملفات بـRLS (ق-61)."""
from django.db import migrations

SQL = """
ALTER TABLE core_storedfile ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_storedfile FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS account_isolation ON core_storedfile;
CREATE POLICY account_isolation ON core_storedfile
    USING (account_id = current_setting('app.account_id', true)::bigint)
    WITH CHECK (account_id = current_setting('app.account_id', true)::bigint);

GRANT SELECT, INSERT, UPDATE, DELETE ON core_storedfile TO hrm_runtime;
"""

REVERSE = """
DROP POLICY IF EXISTS account_isolation ON core_storedfile;
ALTER TABLE core_storedfile DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0005_storage")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
