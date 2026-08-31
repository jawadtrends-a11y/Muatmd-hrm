"""
عزل جداول الفوترة.

Discount استثناء: قد يكون عامًا (بلا حساب) فيُعزل بشرط مختلف —
كود الخصم العام يجب أن يراه كل الحسابات.
InvoiceLine يرث عزله من الفاتورة.
"""
from django.db import migrations

ACCOUNT_TABLES = [
    "accounts_invoice",
    "accounts_payment",
    "accounts_savedcard",
    "accounts_accountsubscription",
]

FORWARD = "\n".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_isolation ON {t}
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""
    for t in ACCOUNT_TABLES
) + """
-- سطور الفاتورة ترث عزل الفاتورة
ALTER TABLE accounts_invoiceline ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_invoiceline FORCE ROW LEVEL SECURITY;
CREATE POLICY accounts_invoiceline_isolation ON accounts_invoiceline
    USING (EXISTS (
        SELECT 1 FROM accounts_invoice i
        WHERE i.id = invoice_id
          AND i.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM accounts_invoice i
        WHERE i.id = invoice_id
          AND i.account_id = app_current_account_id()
    ));

-- الخصم: العام يراه الجميع، والمخصص يراه صاحبه وحده
ALTER TABLE accounts_discount ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_discount FORCE ROW LEVEL SECURITY;
CREATE POLICY accounts_discount_isolation ON accounts_discount
    USING (account_id IS NULL OR account_id = app_current_account_id())
    WITH CHECK (account_id IS NULL OR account_id = app_current_account_id());
"""

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_isolation ON {t};
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in ACCOUNT_TABLES + ["accounts_invoiceline", "accounts_discount"]
)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0011_billing_v2"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
