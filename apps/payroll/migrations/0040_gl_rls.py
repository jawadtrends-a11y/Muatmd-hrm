"""عزل القيد المحاسبيّ وقوالبه (ق-152)."""
from django.db import migrations

TABLES = [
    ("payroll_glaccountmap", "glmap_isolation"),
    ("payroll_gltemplate", "gltemplate_isolation"),
]

FORWARD = "\n".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {p} ON {t}
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
""" for t, p in TABLES)

REVERSE = "\n".join(
    f"DROP POLICY IF EXISTS {p} ON {t};" for t, p in TABLES)


class Migration(migrations.Migration):
    dependencies = [("payroll", "0039_gl_export")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
