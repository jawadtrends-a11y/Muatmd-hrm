"""
دالة مصادقة الجهاز (ق-84).

الجهاز يعرّف نفسه قبل أن يُعرف حسابه، ولا نطاق في السياق بعد —
فالعزل يحجب صفّه عن مصادقته.

والحل دالة بصلاحية مالكها ترجع صفًّا واحدًا يُطابَق برمزه: لا
تقرأ بصمة ولا موظفًا، ولا تُعطّل العزل على شيء آخر.
"""
from django.db import migrations


FORWARD = """
CREATE OR REPLACE FUNCTION app_device_for_auth(p_code text)
RETURNS TABLE (
    id bigint,
    account_id bigint,
    company_id bigint,
    api_key_hash varchar
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT d.id, d.account_id, d.company_id, d.api_key_hash
    FROM attendance_punchdevice d
    WHERE d.device_code = p_code AND d.is_active = true
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION app_device_for_auth(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_device_for_auth(text) TO hrm_runtime;
"""

BACKWARD = "DROP FUNCTION IF EXISTS app_device_for_auth(text);"


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0006_alter_punchdevice_site"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
