"""
دالة حلّ معرّف الدخول — تكسر حلقة العزل قبل المصادقة (ق-94).

المشكلة: الموظف يدخل بهويته أو جواله، والبحث عنهما في جدول
الأشخاص محميّ بـRLS الذي يتطلب سياق حساب — والسياق لا يُضبط إلا
بعد أن نعرف من هو. حلقة مغلقة كحلقة العضوية (ق-6).

الحل: دالة محصورة الغرض تُرجع اسم المستخدم وحده — لا اسمًا ولا
راتبًا ولا أي بيانات عمل. ومن يعرف رقم هوية يعرف صاحبها أصلًا،
فلا تسريب.
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

BACKWARD = """
DROP FUNCTION IF EXISTS app_lookup_login_identifier(TEXT);
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_approverscope_updated_at_alter_approverscope_account_and_more"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
