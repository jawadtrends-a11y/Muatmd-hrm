"""
عزل جداول الرواتب.

تمييز مقصود:
  • مكوّنات الأجر وإعدادات الرواتب — جداول شركة، عزل كامل.
  • أنظمة ونسب التأمينات — جداول منصة، يقرأها الجميع ويعدّلها
    المالك فقط. لا account_id فيها (ق-19/1: نسب تشريعية مركزية).
"""
from django.db import migrations

COMPANY_TABLES = ["payroll_paycomponent", "payroll_payrollsettings"]
PLATFORM_TABLES = ["payroll_gosischeme", "payroll_gosirate"]

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
    for t in COMPANY_TABLES
) + "\n".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_read ON {t} FOR SELECT USING (TRUE);
"""
    for t in PLATFORM_TABLES
)

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_isolation ON {t};
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in COMPANY_TABLES
) + "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_read ON {t};
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in PLATFORM_TABLES
)


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0001_payroll_settings"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
