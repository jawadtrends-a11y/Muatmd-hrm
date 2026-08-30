"""
عزل جداول الموظفين.

تمييز مهم:
  • Person على مستوى الحساب — الشخص واحد مهما تعددت شركاته
  • Employment و SalaryStructure على مستوى الشركة — العزل المالي
    المطلق (ق-3): مديرة الموارد في شركة لا ترى راتبه في أخرى
  • SalaryLine يرث عزله من الهيكل
"""
from django.db import migrations

FORWARD = """
-- ══ الشخص: عزل على مستوى الحساب ══
ALTER TABLE employees_person ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_person FORCE ROW LEVEL SECURITY;
CREATE POLICY person_isolation ON employees_person
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

-- ══ الارتباط الوظيفي: عزل على مستويين ══
ALTER TABLE employees_employment ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_employment FORCE ROW LEVEL SECURITY;
CREATE POLICY employment_isolation ON employees_employment
    USING (
        account_id = app_current_account_id()
        AND (
            app_current_company_ids() IS NULL
            OR company_id = ANY(app_current_company_ids())
        )
    )
    WITH CHECK (account_id = app_current_account_id());

-- ══ هيكل الراتب: عزل مالي مطلق ══
ALTER TABLE employees_salarystructure ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_salarystructure FORCE ROW LEVEL SECURITY;
CREATE POLICY salarystructure_isolation ON employees_salarystructure
    USING (
        account_id = app_current_account_id()
        AND (
            app_current_company_ids() IS NULL
            OR company_id = ANY(app_current_company_ids())
        )
    )
    WITH CHECK (account_id = app_current_account_id());

-- ══ بنود الراتب: ترث عزل الهيكل ══
ALTER TABLE employees_salaryline ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_salaryline FORCE ROW LEVEL SECURITY;
CREATE POLICY salaryline_isolation ON employees_salaryline
    USING (EXISTS (
        SELECT 1 FROM employees_salarystructure s
        WHERE s.id = structure_id
          AND s.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM employees_salarystructure s
        WHERE s.id = structure_id
          AND s.account_id = app_current_account_id()
    ));
"""

REVERSE = """
DROP POLICY IF EXISTS person_isolation ON employees_person;
DROP POLICY IF EXISTS employment_isolation ON employees_employment;
DROP POLICY IF EXISTS salarystructure_isolation ON employees_salarystructure;
DROP POLICY IF EXISTS salaryline_isolation ON employees_salaryline;
ALTER TABLE employees_person DISABLE ROW LEVEL SECURITY;
ALTER TABLE employees_employment DISABLE ROW LEVEL SECURITY;
ALTER TABLE employees_salarystructure DISABLE ROW LEVEL SECURITY;
ALTER TABLE employees_salaryline DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0001_employee_models"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
