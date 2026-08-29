"""
دوال مساعدة لسياسات RLS.

تُكتب مرة وتُستخدم في كل هجرة تفعّل RLS على جدول جديد.
راجع الوثيقة المعمارية (2) القسم 2.
"""
from django.db import migrations

FORWARD = """
-- يقرأ الحساب الحالي من سياق الجلسة.
-- عند غيابه يرجع NULL فتفشل كل المقارنات → صفر صفوف (fail closed).
CREATE OR REPLACE FUNCTION app_current_account_id() RETURNS BIGINT AS $$
    SELECT NULLIF(current_setting('app.account_id', TRUE), '')::BIGINT;
$$ LANGUAGE SQL STABLE;

-- قائمة الشركات المصرّح بها. الفراغ يعني "كل شركات الحساب".
CREATE OR REPLACE FUNCTION app_current_company_ids() RETURNS BIGINT[] AS $$
    SELECT CASE
        WHEN COALESCE(current_setting('app.company_ids', TRUE), '') = '' THEN NULL
        ELSE string_to_array(current_setting('app.company_ids', TRUE), ',')::BIGINT[]
    END;
$$ LANGUAGE SQL STABLE;
"""

REVERSE = """
DROP FUNCTION IF EXISTS app_current_account_id();
DROP FUNCTION IF EXISTS app_current_company_ids();
"""


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
