"""عزل جداول الإشعارات."""
from django.db import migrations

FORWARD = """
-- جدول منصة: الأحداث يعرّفها المطوّر، يقرأها الجميع
ALTER TABLE notifications_notificationevent ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notificationevent FORCE ROW LEVEL SECURITY;
CREATE POLICY event_read ON notifications_notificationevent
    FOR SELECT USING (TRUE);

-- القوالب: الافتراضية للجميع، والمخصصة لحسابها
ALTER TABLE notifications_notificationtemplate ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notificationtemplate FORCE ROW LEVEL SECURITY;
CREATE POLICY template_read ON notifications_notificationtemplate
    FOR SELECT USING (account_id IS NULL OR account_id = app_current_account_id());
CREATE POLICY template_write ON notifications_notificationtemplate
    FOR INSERT WITH CHECK (account_id = app_current_account_id());
CREATE POLICY template_update ON notifications_notificationtemplate
    FOR UPDATE USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
CREATE POLICY template_delete ON notifications_notificationtemplate
    FOR DELETE USING (account_id = app_current_account_id());

-- جداول الحساب: عزل كامل
ALTER TABLE notifications_notificationpreference ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notificationpreference FORCE ROW LEVEL SECURITY;
CREATE POLICY pref_isolation ON notifications_notificationpreference
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE notifications_notification ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notification FORCE ROW LEVEL SECURITY;
CREATE POLICY notification_isolation ON notifications_notification
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE notifications_notificationdelivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notificationdelivery FORCE ROW LEVEL SECURITY;
CREATE POLICY delivery_isolation ON notifications_notificationdelivery
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS event_read ON notifications_notificationevent;
DROP POLICY IF EXISTS template_read ON notifications_notificationtemplate;
DROP POLICY IF EXISTS template_write ON notifications_notificationtemplate;
DROP POLICY IF EXISTS template_update ON notifications_notificationtemplate;
DROP POLICY IF EXISTS template_delete ON notifications_notificationtemplate;
DROP POLICY IF EXISTS pref_isolation ON notifications_notificationpreference;
DROP POLICY IF EXISTS notification_isolation ON notifications_notification;
DROP POLICY IF EXISTS delivery_isolation ON notifications_notificationdelivery;
ALTER TABLE notifications_notificationevent DISABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notificationtemplate DISABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notificationpreference DISABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notification DISABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_notificationdelivery DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_notification_models"),
        ("accounts", "0001_initial"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
