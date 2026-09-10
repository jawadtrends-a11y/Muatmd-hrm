"""عزل قوالب الخطابات والصادر منها."""
from django.db import migrations

FORWARD = """
ALTER TABLE core_lettertemplate ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_lettertemplate FORCE ROW LEVEL SECURITY;
CREATE POLICY lettertemplate_isolation ON core_lettertemplate
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE core_issuedletter ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_issuedletter FORCE ROW LEVEL SECURITY;
CREATE POLICY issuedletter_isolation ON core_issuedletter
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS lettertemplate_isolation ON core_lettertemplate;
DROP POLICY IF EXISTS issuedletter_isolation ON core_issuedletter;
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0012_letter_templates")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
