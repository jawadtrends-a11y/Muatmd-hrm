"""
دالّة سرد الحسابات للمنصّة (ق-107).

المسألة: سياسة العزل `id = app_current_account_id()` تحجب كل حساب
عمّن لا سياق له — ولوحة المنصّة بطبيعتها بلا سياق، فتراها فارغة.

والحلّ دالّة SECURITY DEFINER كالتي في ق-94: لا نُرخي السياسة،
والدالّة ترجع **أرقام الحسابات وملخّصها** لا بياناتها. فمن أراد
بيانات حسابٍ يدخله بالانتحال المسجَّل (ق-46).
"""
from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION app_platform_accounts()
RETURNS TABLE (
    account_id BIGINT,
    slug TEXT,
    display_name_ar TEXT,
    status TEXT,
    is_sandbox BOOLEAN,
    created_at TIMESTAMPTZ
) AS $$
    SELECT a.id, a.slug::TEXT, a.display_name_ar::TEXT,
           a.status::TEXT, a.is_sandbox, a.created_at
    FROM accounts_account a
    ORDER BY a.created_at DESC;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_platform_accounts() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_platform_accounts() TO hrm_runtime;
"""

REVERSE = "DROP FUNCTION IF EXISTS app_platform_accounts();"


class Migration(migrations.Migration):
    dependencies = [("accounts", "0034_invite_preview_trim")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
