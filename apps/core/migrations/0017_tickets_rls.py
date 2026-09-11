"""عزل تذاكر الدعم ورسائلها."""
from django.db import migrations

FORWARD = """
ALTER TABLE core_supportticket ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_supportticket FORCE ROW LEVEL SECURITY;
CREATE POLICY ticket_isolation ON core_supportticket
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE core_ticketmessage ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_ticketmessage FORCE ROW LEVEL SECURITY;
CREATE POLICY ticketmsg_isolation ON core_ticketmessage
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS ticket_isolation ON core_supportticket;
DROP POLICY IF EXISTS ticketmsg_isolation ON core_ticketmessage;
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0016_support_tickets")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
