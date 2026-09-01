"""عزل جداول مواقع العمل بـRLS (ق-62)."""
from django.db import migrations

TABLES = [
    "attendance_worksite",
    "attendance_siteassignment",
    "attendance_punchdevice",
]

SQL = "\n".join(f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS account_isolation ON {t};
CREATE POLICY account_isolation ON {t}
    USING (account_id = current_setting('app.account_id', true)::bigint)
    WITH CHECK (account_id = current_setting('app.account_id', true)::bigint);

GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO hrm_runtime;
""" for t in TABLES)

REVERSE = "\n".join(f"""
DROP POLICY IF EXISTS account_isolation ON {t};
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
""" for t in TABLES)


class Migration(migrations.Migration):
    dependencies = [("attendance", "0003_worksites")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
