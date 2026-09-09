"""
دالّة أقصى مرجع مطالبة (ق-112).

⚠️ المولّد كان يعدّ الصفوف **داخل عزل الحساب** — فيبدأ كل حساب من
واحد وتتصادم المراجع بين الحسابات، ويعيد الترقيم للوراء عند أي
حذف فيصطدم بقيد التفرّد.

والدالّة ترجع **رقمًا واحدًا** لا بيانات — أقلّ ما يلزم.
"""
from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION app_max_invoice_seq(p_prefix TEXT)
RETURNS BIGINT AS $$
    SELECT COALESCE(MAX(
        NULLIF(regexp_replace(i.invoice_no, '^.*-', ''), '')::BIGINT
    ), 0)
    FROM accounts_invoice i
    WHERE i.invoice_no LIKE p_prefix || '%';
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_max_invoice_seq(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_max_invoice_seq(TEXT) TO hrm_runtime;
"""

REVERSE = "DROP FUNCTION IF EXISTS app_max_invoice_seq(TEXT);"


class Migration(migrations.Migration):
    dependencies = [("accounts", "0041_overage_invoice")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
