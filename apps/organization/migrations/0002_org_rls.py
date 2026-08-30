"""
عزل جداول الهيكل التنظيمي.

كلها جداول شركة — عزل على مستويين: الحساب مطلق، والشركة ضمن
المصرّح به. لا جدول منصة هنا إطلاقًا (قرار المالك في العطل).
"""
from django.db import migrations

TABLES = [
    "organization_branch",
    "organization_department",
    "organization_costcenter",
    "organization_jobtitle",
    "organization_holiday",
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
        ("organization", "0001_org_models"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
