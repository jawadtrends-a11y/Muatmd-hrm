"""
⚠️ قيمةٌ افتراضية لعمود الشعار (ق-164).

**فدالّة التهيئة تُنشئ الشركة بـINSERT صريح** — ودرسُ ق-١٦٠ يتكرّر
لولا هذا.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("accounts", "0056_company_logo")]
    operations = [
        migrations.RunSQL(
            "ALTER TABLE accounts_company "
            "ALTER COLUMN logo_id SET DEFAULT NULL;",
            "ALTER TABLE accounts_company "
            "ALTER COLUMN logo_id DROP DEFAULT;",
        ),
    ]
