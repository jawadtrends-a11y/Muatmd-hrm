"""عزل جداول السلف والعهد والوثائق."""
from django.db import migrations

TABLES = [
    "employees_advance",
    "employees_advanceinstallment",
    "employees_asset",
    "employees_employeedocument",
]

FORWARD = "\n".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_isolation ON {t}
    USING (
        account_id = app_current_account_id()
        AND (
            app_current_company_ids() IS NULL
            OR company_id = ANY(app_current_company_ids())
        )
    )
    WITH CHECK (account_id = app_current_account_id());
"""
    for t in TABLES
)

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_isolation ON {t};
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in TABLES
)


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0003_assets_advances_documents"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
