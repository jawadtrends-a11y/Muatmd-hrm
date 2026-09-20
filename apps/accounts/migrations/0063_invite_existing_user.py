"""
ق-223: بريدٌ مطابقٌ لمستخدمٍ قائم — لا حسابَ ثانٍ.

قرار جواد: إن كان بريد الموظف بريدَ مستخدمٍ قائم فالشخص واحد
**ولا كلمةَ مرورٍ ولا حساب ثانٍ** — تأكيدُ استلامٍ فقط.

والدالّة SECURITY DEFINER كأخواتها: فالمعاينة والقبول يقعان
**قبل الدخول**، ولا سياق حساب — وRLS يحجب الجداول.
"""
from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION app_invite_existing_user(p_token_hash TEXT)
RETURNS BIGINT AS $$
    SELECT u.id
      FROM accounts_joininvite i
      JOIN employees_person p ON p.id = i.person_id
      JOIN auth_user u ON LOWER(u.email) = LOWER(NULLIF(p.email, ''))
     WHERE i.token_hash = p_token_hash
       AND i.status = 'pending'
       AND i.expires_at > now()
       AND u.is_active
     LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_invite_existing_user(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_invite_existing_user(TEXT) TO hrm_runtime;
"""

REVERSE = "DROP FUNCTION IF EXISTS app_invite_existing_user(TEXT);"


class Migration(migrations.Migration):

    dependencies = [("accounts", "0062_invite_owner_and_existing")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
