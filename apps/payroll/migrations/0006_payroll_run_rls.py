"""عزل جداول المسير. PayslipLine يرث عزله من القسيمة."""
from django.db import migrations

COMPANY_TABLES = ["payroll_payrollrun", "payroll_payslip"]

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
) + """
ALTER TABLE payroll_payslipline ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_payslipline FORCE ROW LEVEL SECURITY;
CREATE POLICY payroll_payslipline_isolation ON payroll_payslipline
    USING (EXISTS (
        SELECT 1 FROM payroll_payslip p
        WHERE p.id = payslip_id
          AND p.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM payroll_payslip p
        WHERE p.id = payslip_id
          AND p.account_id = app_current_account_id()
    ));
"""

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_isolation ON {t};
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in COMPANY_TABLES + ["payroll_payslipline"]
)


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0005_payroll_run_models"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
