"""عزل جداول تقييم الأداء (ق-146)."""
from django.db import migrations

TABLES = [
    ("employees_reviewcycle", "cycle_isolation"),
    ("employees_kpi", "kpi_isolation"),
    ("employees_kpiassignment", "kpiassign_isolation"),
    ("employees_peerreview", "peerreview_isolation"),
    ("employees_behaviorrating", "behavior_isolation"),
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
    dependencies = [("employees", "0026_performance")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
