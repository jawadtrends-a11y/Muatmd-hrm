"""عزل جداول الجزاءات."""
from django.db import migrations

FORWARD = """
ALTER TABLE employees_violationtype ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_violationtype FORCE ROW LEVEL SECURITY;
CREATE POLICY violationtype_isolation ON employees_violationtype
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE employees_penalty ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_penalty FORCE ROW LEVEL SECURITY;
CREATE POLICY penalty_isolation ON employees_penalty
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

-- الدرجة تابعة لبندها، والبند معزول — فتُحرَس به
ALTER TABLE employees_penaltydegree ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_penaltydegree FORCE ROW LEVEL SECURITY;
CREATE POLICY penaltydegree_isolation ON employees_penaltydegree
    USING (EXISTS (SELECT 1 FROM employees_violationtype v
                    WHERE v.id = violation_id
                      AND v.account_id = app_current_account_id()))
    WITH CHECK (EXISTS (SELECT 1 FROM employees_violationtype v
                         WHERE v.id = violation_id
                           AND v.account_id = app_current_account_id()));
"""

REVERSE = """
DROP POLICY IF EXISTS violationtype_isolation ON employees_violationtype;
DROP POLICY IF EXISTS penalty_isolation ON employees_penalty;
DROP POLICY IF EXISTS penaltydegree_isolation ON employees_penaltydegree;
"""


class Migration(migrations.Migration):
    dependencies = [("employees", "0014_penalties")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
