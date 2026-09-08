"""عزل جداول الإعلانات — بلا سياسة تقرأ شركةٌ إعلانات غيرها."""
from django.db import migrations

FORWARD = """
ALTER TABLE notifications_announcement ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_announcement FORCE ROW LEVEL SECURITY;
CREATE POLICY announcement_isolation ON notifications_announcement
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE notifications_announcementattachment ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_announcementattachment FORCE ROW LEVEL SECURITY;
CREATE POLICY announcement_att_isolation
    ON notifications_announcementattachment
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS announcement_isolation ON notifications_announcement;
DROP POLICY IF EXISTS announcement_att_isolation
    ON notifications_announcementattachment;
"""


class Migration(migrations.Migration):
    dependencies = [("notifications", "0003_announcements")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
