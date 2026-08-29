"""
دالة إنشاء الحساب — المسار الوحيد المسموح لتجاوز WITH CHECK.

SECURITY DEFINER تجعلها تعمل بصلاحية منشئها (المالك) لا المستدعي،
فتستطيع الإدراج بلا سياق. نطاقها محصور في إنشاء حساب وشركته الأولى
فقط — لا تقرأ ولا تعدّل شيئًا آخر.
"""
from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION app_provision_account(
    p_slug              TEXT,
    p_display_name_ar   TEXT,
    p_company_name_ar   TEXT,
    p_company_code      TEXT DEFAULT 'C1',
    p_is_sandbox        BOOLEAN DEFAULT FALSE
) RETURNS TABLE (account_id BIGINT, company_id BIGINT) AS $$
DECLARE
    v_account_id BIGINT;
    v_company_id BIGINT;
BEGIN
    IF p_slug !~ '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$' THEN
        RAISE EXCEPTION 'معرّف غير صالح: %', p_slug;
    END IF;

    INSERT INTO accounts_account (
        uuid, slug, display_name_ar, display_name_en,
        isolation_mode, status, default_locale, timezone,
        employee_no_scope, allow_cross_company_employment,
        is_sandbox, suspension_reason, created_at, updated_at
    ) VALUES (
        gen_random_uuid(), p_slug, p_display_name_ar, '',
        'shared', 'trial', 'ar', 'Asia/Riyadh',
        'company', TRUE, p_is_sandbox, '', now(), now()
    ) RETURNING id INTO v_account_id;

    INSERT INTO accounts_company (
        account_id, code, legal_name_ar, legal_name_en,
        cr_number, unified_national_number, vat_number,
        gosi_establishment_no, mol_establishment_no,
        activity_code, entity_size, fiscal_year_start_month,
        is_active, created_at, updated_at
    ) VALUES (
        v_account_id, p_company_code, p_company_name_ar, '',
        '', '', '', '', '', '', '', 1, TRUE, now(), now()
    ) RETURNING id INTO v_company_id;

    RETURN QUERY SELECT v_account_id, v_company_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- تُمنح لدور التشغيل حصرًا. لا تُمنح لـPUBLIC.
REVOKE ALL ON FUNCTION app_provision_account(TEXT,TEXT,TEXT,TEXT,BOOLEAN) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_provision_account(TEXT,TEXT,TEXT,TEXT,BOOLEAN) TO hrm_runtime;
"""

REVERSE = """
DROP FUNCTION IF EXISTS app_provision_account(TEXT,TEXT,TEXT,TEXT,BOOLEAN);
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_enable_rls")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
