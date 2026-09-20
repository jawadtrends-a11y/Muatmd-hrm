"""
ق-223: والمستخدم القائم يُربط **إن كان حرًّا** لا مرتبطًا بغيره.

⚠️ فمستخدمٌ له ملفٌّ أصلًا **لا يُربط بملفٍّ ثانٍ** — و`user`
فريدٌ في `employees_person`. وبلا هذا الشرط **ينهار القبول بـ500**
بدل رسالةٍ تُسمّي المطلوب، وموظفان ببريدٍ واحد واقعٌ لا نادر.
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
       AND NOT EXISTS (SELECT 1 FROM employees_person q
                        WHERE q.user_id = u.id)
     LIMIT 1;
$$ LANGUAGE sql SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_invite_existing_user(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_invite_existing_user(TEXT) TO hrm_runtime;
"""

REVERSE = "-- لا رجوع."


class Migration(migrations.Migration):

    dependencies = [("accounts", "0063_invite_existing_user")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
