"""عزل تفضيلات اللوحة — بالحساب كبقيّة الجداول."""
from django.db import migrations

FORWARD = """
ALTER TABLE core_dashboardpreference ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_dashboardpreference FORCE ROW LEVEL SECURITY;
CREATE POLICY dashboard_pref_isolation ON core_dashboardpreference
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS dashboard_pref_isolation ON core_dashboardpreference;
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0007_dashboard_preference")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
