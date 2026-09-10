"""
كتابة المزايا من لوحة المنصّة (ق-125).

⚠️ سياسة `accounts_feature` قراءةٌ فقط — كسياسة الباقات (ق-116).
فإضافة ميزةٍ من اللوحة تسقط بـ500.

والمزايا **كتالوج المنصّة** لا بيانات عميل: يقرؤها الجميع،
ويكتبها **من لا سياق حساب له** — أي اللوحة وحدها.
"""
from django.db import migrations

SQL = """
DROP POLICY IF EXISTS feature_platform_write ON accounts_feature;
CREATE POLICY feature_platform_write ON accounts_feature FOR ALL
    USING (app_current_account_id() IS NULL)
    WITH CHECK (app_current_account_id() IS NULL);
"""

REVERSE = "DROP POLICY IF EXISTS feature_platform_write ON accounts_feature;"


class Migration(migrations.Migration):
    dependencies = [("accounts", "0050_seed_features_plans")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
