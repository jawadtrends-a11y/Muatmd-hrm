"""
البحث بالجوال يشمل جوال العضوية (ق-113).

⚠️ العلّة: `AccountMembership` معزول بـRLS — والبحث يقع **قبل أن
يُعرف صاحب المعرّف**، فلا سياق حساب، فتُحجب العضوية ويفشل الدخول
بالجوال. وهي نفس علّة العائد من بوابة الدفع (ق-109).

والدالّة SECURITY DEFINER كما هي: **ترجع اسم المستخدم وحده** لا
بيانات — فمن نادى بها معرّفًا لا يعرف صاحبه لا يزيد علمه شيئًا.
"""
from django.db import migrations

SQL = """
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
      )

    UNION

    -- مالك الحساب من التسجيل الذاتيّ: يدخل قبل أن يُضيف نفسه
    -- موظفًا، فلا ملفّ شخصٍ له بعد وجواله في عضويته.
    SELECT DISTINCT u.username::TEXT
    FROM accounts_accountmembership m
    JOIN auth_user u ON u.id = m.user_id
    WHERE m.login_mobile <> '' AND m.login_mobile = p_ident;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_lookup_login_identifier(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_lookup_login_identifier(TEXT) TO hrm_runtime;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0044_login_mobile"),
        # ⚠️ بعد حذف border_number: 0028 توسّع الدالّة به و0029
        # تنزعه — وهجرتنا تعيد كتابتها، فلا بدّ أن تقع بعدهما
        # وبعد حذف العمود، وإلا اصطدم الترتيب بعمود غير موجود.
        ("employees", "0011_remove_person_border_number"),
    ]
    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
