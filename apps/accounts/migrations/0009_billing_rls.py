"""
عزل جداول الفوترة.

تمييز مقصود:
  • جداول المنصة (المزايا، الباقات، الأسعار) — يقرأها الجميع،
    ويعدّلها المالك (السوبر أدمن) فقط. لا account_id فيها.
  • جداول الحساب (الاشتراكات، لقطات العدد) — عزل كامل.
"""
from django.db import migrations

FORWARD = """
-- ══ جداول المنصة: قراءة عامة، كتابة للمالك فقط ══
ALTER TABLE accounts_feature ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_feature FORCE ROW LEVEL SECURITY;
CREATE POLICY feature_read ON accounts_feature FOR SELECT USING (TRUE);

ALTER TABLE accounts_plan ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_plan FORCE ROW LEVEL SECURITY;
CREATE POLICY plan_read ON accounts_plan FOR SELECT USING (TRUE);

ALTER TABLE accounts_planpricetier ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_planpricetier FORCE ROW LEVEL SECURITY;
CREATE POLICY pricetier_read ON accounts_planpricetier FOR SELECT USING (TRUE);

ALTER TABLE accounts_planfeature ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_planfeature FORCE ROW LEVEL SECURITY;
CREATE POLICY planfeature_read ON accounts_planfeature FOR SELECT USING (TRUE);

-- ══ جداول الحساب: عزل كامل ══
ALTER TABLE accounts_companysubscription ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_companysubscription FORCE ROW LEVEL SECURITY;
CREATE POLICY subscription_isolation ON accounts_companysubscription
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

ALTER TABLE accounts_companyheadcountdaily ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_companyheadcountdaily FORCE ROW LEVEL SECURITY;
CREATE POLICY headcount_isolation ON accounts_companyheadcountdaily
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = """
DROP POLICY IF EXISTS feature_read ON accounts_feature;
DROP POLICY IF EXISTS plan_read ON accounts_plan;
DROP POLICY IF EXISTS pricetier_read ON accounts_planpricetier;
DROP POLICY IF EXISTS planfeature_read ON accounts_planfeature;
DROP POLICY IF EXISTS subscription_isolation ON accounts_companysubscription;
DROP POLICY IF EXISTS headcount_isolation ON accounts_companyheadcountdaily;
ALTER TABLE accounts_feature DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_plan DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_planpricetier DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_planfeature DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_companysubscription DISABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_companyheadcountdaily DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_billing_models")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
