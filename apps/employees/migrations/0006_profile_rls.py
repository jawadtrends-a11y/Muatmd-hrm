"""عزل جداول ملف الموظف بـRLS (ق-63)."""
from django.db import migrations

TABLES = [
    "employees_dependent",
    "employees_emergencycontact",
    "employees_jobgrade",
    "employees_jobstep",
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
    dependencies = [("employees", "0005_profile_expansion")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
