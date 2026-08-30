"""
دالة قراءة العضوية — تكسر حلقة الاعتماد الدائري.

المشكلة: الـmiddleware يحتاج account_id ليضبط السياق، لكنه يقرأه من
جدول العضوية المحمي بـRLS الذي يتطلب سياقًا. حلقة مغلقة.

الحل: دالة محصورة الغرض تقرأ صفًا واحدًا بمعرّف المستخدم فقط.
لا تقرأ بيانات عمل، ولا تقبل معاملات أخرى، ولا تُمنح لـPUBLIC.
"""
from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION app_lookup_membership(p_user_id BIGINT)
RETURNS TABLE (
    membership_id     BIGINT,
    account_id        BIGINT,
    active_company_id BIGINT,
    is_account_owner  BOOLEAN,
    account_status    TEXT
) AS $$
    SELECT m.id, m.account_id, m.active_company_id, m.is_account_owner,
           a.status::TEXT
    FROM accounts_accountmembership m
    JOIN accounts_account a ON a.id = m.account_id
    WHERE m.user_id = p_user_id
    LIMIT 1;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_lookup_membership(BIGINT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_lookup_membership(BIGINT) TO hrm_runtime;

-- الشركات المصرّح بها للعضوية — تُحقن في app.company_ids
CREATE OR REPLACE FUNCTION app_lookup_company_ids(p_membership_id BIGINT)
RETURNS BIGINT[] AS $$
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM accounts_accountmembership m
            WHERE m.id = p_membership_id AND m.is_account_owner
        ) OR EXISTS (
            SELECT 1 FROM accounts_roleassignment ra
            WHERE ra.membership_id = p_membership_id AND ra.scope = 'account'
        )
        THEN ARRAY(
            SELECT c.id FROM accounts_company c
            JOIN accounts_accountmembership m ON m.account_id = c.account_id
            WHERE m.id = p_membership_id
        )
        ELSE ARRAY(
            SELECT DISTINCT x FROM (
                SELECT ra.company_id AS x FROM accounts_roleassignment ra
                WHERE ra.membership_id = p_membership_id AND ra.company_id IS NOT NULL
                UNION
                SELECT m.active_company_id FROM accounts_accountmembership m
                WHERE m.id = p_membership_id AND m.active_company_id IS NOT NULL
            ) s WHERE x IS NOT NULL
        )
    END;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_lookup_company_ids(BIGINT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_lookup_company_ids(BIGINT) TO hrm_runtime;
"""

REVERSE = """
DROP FUNCTION IF EXISTS app_lookup_membership(BIGINT);
DROP FUNCTION IF EXISTS app_lookup_company_ids(BIGINT);
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_access_rls")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
