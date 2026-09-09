"""
دالّة قراءة حساب الفاتورة — لعودة الدفع (ق-109).

المسألة: العميل يعود من البنك **بلا جلسة**، فلا سياق حساب وRLS
يحجب الفاتورة — فيسقط تأكيد دفعةٍ نجحت فعلًا.

والدالّة ترجع **رقم الحساب وحده** لا بيانات الفاتورة: به يُضبط
السياق ثم يُقرأ الباقي بالعزل الطبيعيّ.
"""
from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION app_invoice_account(p_invoice_id BIGINT)
RETURNS TABLE (account_id BIGINT) AS $$
    SELECT i.account_id FROM accounts_invoice i WHERE i.id = p_invoice_id;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_invoice_account(BIGINT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_invoice_account(BIGINT) TO hrm_runtime;
"""

REVERSE = "DROP FUNCTION IF EXISTS app_invoice_account(BIGINT);"


class Migration(migrations.Migration):
    dependencies = [("accounts", "0037_setup_fee")]
    operations = [migrations.RunSQL(SQL, REVERSE)]
