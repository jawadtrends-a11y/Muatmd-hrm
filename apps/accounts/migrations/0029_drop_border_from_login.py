"""
رقم الحدود يُدخَل نوعًا من الهوية لا حقلًا مستقلًّا (ق-95).

فالحقل المستقلّ حُذف — ومن يختار «رقم حدود» يضعه في id_number،
والدخول به يعمل من هناك.
"""
from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION app_lookup_login_identifier(p_ident TEXT)
RETURNS TABLE (username TEXT) AS $$
    SELECT DISTINCT u.username::TEXT
    FROM employees_person p
    JOIN auth_user u ON u.id = p.user_id
    WHERE p.user_id IS NOT NULL
      AND (
        LOWER(p.email) = LOWER(p_ident)
        OR p.id_number = p_ident
        OR p.mobile_e164 = p_ident
      );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_lookup_login_identifier(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_lookup_login_identifier(TEXT)
    TO hrm_runtime;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0028_border_number_login"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, migrations.RunSQL.noop),
    ]
