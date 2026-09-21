"""عزل أجهزة الجوال (ق-232) — نمط «جداول الحساب: عزل كامل» في 0002 حرفيًّا."""
from django.db import migrations

FORWARD = """
ALTER TABLE notifications_pushdevice ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_pushdevice FORCE ROW LEVEL SECURITY;
CREATE POLICY pushdevice_isolation ON notifications_pushdevice
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS pushdevice_isolation ON notifications_pushdevice;
ALTER TABLE notifications_pushdevice DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("notifications", "0005_pushdevice")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
