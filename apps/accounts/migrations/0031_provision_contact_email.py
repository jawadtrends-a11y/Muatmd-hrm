"""
تحديث دالّة التزويد لتذكر contact_email (ق-99).

السبب: الدالّة تُنشئ الشركة بـINSERT صريح الأعمدة، فكل عمود نصّي
جديد لا يُذكر فيها يدخل NULL ويصطدم بقيد NOT NULL — فتسقط كل
عملية إنشاء حساب. والفراغ هنا نصّ فارغ لا NULL، كبقيّة حقول
النصّ في النظام: فلا فراغان مختلفان لمعنى واحد.

⚠️ درس: أي حقل نصّي جديد في Company أو Account يلزمه تحديث هذه
الدالّة معه — وإلا سقط النظام كلّه عند أول إنشاء حساب.
"""
from django.db import migrations

SQL = """
CREATE OR REPLACE FUNCTION app_provision_account(
    p_slug              TEXT,
    p_display_name_ar   TEXT,
    p_company_name_ar   TEXT,
    p_company_code      TEXT DEFAULT 'C1',
    p_is_sandbox        BOOLEAN DEFAULT FALSE
) RETURNS TABLE(account_id BIGINT, company_id BIGINT)
LANGUAGE plpgsql SECURITY DEFINER AS $$
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
        contact_email,
        is_active, created_at, updated_at
    ) VALUES (
        v_account_id, p_company_code, p_company_name_ar, '',
        '', '', '', '', '', '', '', 1,
        '',
        TRUE, now(), now()
    ) RETURNING id INTO v_company_id;
    RETURN QUERY SELECT v_account_id, v_company_id;
END;
$$;
"""


class Migration(migrations.Migration):

    dependencies = [("accounts", "0030_company_contact_email")]

    operations = [migrations.RunSQL(SQL, migrations.RunSQL.noop)]
