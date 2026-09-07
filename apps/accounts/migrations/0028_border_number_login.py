"""
رقم الحدود معرّف دخول (ق-95).

غير السعودي يُصدر له رقم حدود عند أول دخول، وقد تمضي أشهر قبل
إقامته — وهو يعمل ويبصم في تلك المدة. فمن لا إقامة له يدخل
بحدوده.
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
        OR (p.border_number <> '' AND p.border_number = p_ident)
      );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_lookup_login_identifier(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_lookup_login_identifier(TEXT)
    TO hrm_runtime;
"""

BACKWARD = """
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
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0027_login_identifier_lookup"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
