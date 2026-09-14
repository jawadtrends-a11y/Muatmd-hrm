"""
قيمةٌ افتراضية في القاعدة لصلاحيات مدير الإدارة (ق-160).

⚠️⚠️ **فدالّة التهيئة تُنشئ الشركة بـINSERT صريح** — لا تعرف
الحقل الجديد، **فينهار كل إنشاء حساب**.

**والافتراض في القاعدة أنظف من تعديل الدالّة**: فكل INSERT قائمٍ
يكتفي، ولا نطارد مواضعها.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0053_dept_manager_perms")]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE accounts_company "
            "ALTER COLUMN dept_manager_permissions SET DEFAULT '[]'::jsonb;",
            "ALTER TABLE accounts_company "
            "ALTER COLUMN dept_manager_permissions DROP DEFAULT;",
        ),
    ]
