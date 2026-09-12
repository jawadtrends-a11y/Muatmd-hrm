"""عزل أنواع الطلبات المخصّصة وحقولها."""
from django.db import migrations

FORWARD = """
ALTER TABLE leaves_customrequesttype ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaves_customrequesttype FORCE ROW LEVEL SECURITY;
CREATE POLICY customreqtype_isolation ON leaves_customrequesttype
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE leaves_customrequestfield ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaves_customrequestfield FORCE ROW LEVEL SECURITY;
CREATE POLICY customreqfield_isolation ON leaves_customrequestfield
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS customreqtype_isolation ON leaves_customrequesttype;
DROP POLICY IF EXISTS customreqfield_isolation ON leaves_customrequestfield;
"""


class Migration(migrations.Migration):
    dependencies = [("leaves", "0015_custom_request_types")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
