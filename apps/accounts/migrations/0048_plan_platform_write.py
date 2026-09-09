"""
كتابة الباقات من لوحة المنصّة (ق-116).

⚠️ سياسة الباقات قراءةٌ فقط (`USING true` بلا `WITH CHECK`) —
فالكتابة ممنوعة على الجميع، **ولوحة المنصّة منهم**، فيسقط تعديل
الباقة بـ500.

والباقات **كتالوج المنصّة** لا بيانات عميل: يقرؤها الجميع،
ويكتبها **من لا سياق حساب له** — أي اللوحة وحدها. فالعميل يعمل
دائمًا داخل سياق حسابه فلا يكتب ولو نادى المسار.
"""
from django.db import migrations

SQL = """
DROP POLICY IF EXISTS plan_platform_write ON accounts_plan;
CREATE POLICY plan_platform_write ON accounts_plan FOR ALL
    USING (app_current_account_id() IS NULL)
    WITH CHECK (app_current_account_id() IS NULL);

DROP POLICY IF EXISTS pricetier_platform_write ON accounts_planpricetier;
CREATE POLICY pricetier_platform_write ON accounts_planpricetier FOR ALL
    USING (app_current_account_id() IS NULL)
    WITH CHECK (app_current_account_id() IS NULL);

DROP POLICY IF EXISTS planfeature_platform_write ON accounts_planfeature;
CREATE POLICY planfeature_platform_write ON accounts_planfeature FOR ALL
    USING (app_current_account_id() IS NULL)
    WITH CHECK (app_current_account_id() IS NULL);
"""

REVERSE = """
DROP POLICY IF EXISTS plan_platform_write ON accounts_plan;
DROP POLICY IF EXISTS pricetier_platform_write ON accounts_planpricetier;
DROP POLICY IF EXISTS planfeature_platform_write ON accounts_planfeature;
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0047_link_roles_to_employments")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
