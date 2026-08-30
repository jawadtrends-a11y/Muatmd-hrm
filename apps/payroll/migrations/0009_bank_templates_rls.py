"""عزل قوالب البنوك. BankColumn يرث عزله من القالب."""
from django.db import migrations

FORWARD = """
ALTER TABLE payroll_banktemplate ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_banktemplate FORCE ROW LEVEL SECURITY;
CREATE POLICY payroll_banktemplate_isolation ON payroll_banktemplate
    USING (
        account_id = app_current_account_id()
        AND (
            app_current_company_ids() IS NULL
            OR company_id = ANY(app_current_company_ids())
        )
    )
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE payroll_bankcolumn ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_bankcolumn FORCE ROW LEVEL SECURITY;
CREATE POLICY payroll_bankcolumn_isolation ON payroll_bankcolumn
    USING (EXISTS (
        SELECT 1 FROM payroll_banktemplate t
        WHERE t.id = template_id
          AND t.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM payroll_banktemplate t
        WHERE t.id = template_id
          AND t.account_id = app_current_account_id()
    ));
"""

REVERSE = """
DROP POLICY IF EXISTS payroll_banktemplate_isolation ON payroll_banktemplate;
DROP POLICY IF EXISTS payroll_bankcolumn_isolation ON payroll_bankcolumn;
ALTER TABLE payroll_banktemplate DISABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_bankcolumn DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0008_bank_templates"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
