"""تنظيف مسافات الاسم في معاينة الدعوة — اسم الأب قد يكون فارغًا."""
from django.db import migrations

SQL = r"""
CREATE OR REPLACE FUNCTION app_invite_preview(p_token_hash TEXT)
RETURNS TABLE (
    invite_id BIGINT, person_name TEXT,
    company_name_ar TEXT, company_name_en TEXT,
    account_locale TEXT, is_usable BOOLEAN
) AS $$
    SELECT i.id,
           REGEXP_REPLACE(TRIM(CONCAT_WS(' ', p.first_name_ar,
                p.father_name_ar, p.family_name_ar)),
                '\s+', ' ', 'g')::TEXT,
           c.legal_name_ar::TEXT, c.legal_name_en::TEXT,
           a.default_locale::TEXT,
           (i.status = 'pending' AND i.expires_at > now())
    FROM accounts_joininvite i
    JOIN employees_person p ON p.id = i.person_id
    JOIN accounts_company c ON c.id = i.company_id
    JOIN accounts_account a ON a.id = i.account_id
    WHERE i.token_hash = p_token_hash;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_invite_preview(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_invite_preview(TEXT) TO hrm_runtime;
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0033_join_invite_rls")]
    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
