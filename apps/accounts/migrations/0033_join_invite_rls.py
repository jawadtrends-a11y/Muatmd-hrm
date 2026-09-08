"""
عزل جدول الدعوات، ودالّتان تكسران حلقة العزل عند القبول.

المسألة نفسها التي في ق-94: الموظف يفتح رابط الدعوة **قبل أن
يدخل** — فلا سياق حساب، وRLS يحجب الجدول. فلا سبيل إلا دالّة
SECURITY DEFINER تُرجع أقلّ ما يلزم.

وهما دالّتان لا واحدة:
  ١. المعاينة — ترجع الاسم والشركة وصلاحية الرمز فقط، لا بيانات
     عمل ولا هوية ولا راتب. فمن سرق الرابط لا يحصد شيئًا.
  ٢. القبول — تُنشئ المستخدم وتربطه وتُغلق الدعوة في معاملة
     واحدة. فلا حساب نصف مربوط إن انقطع شيء في المنتصف.
"""
from django.db import migrations

FORWARD = """
ALTER TABLE accounts_joininvite ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounts_joininvite FORCE ROW LEVEL SECURITY;
CREATE POLICY invite_isolation ON accounts_joininvite
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());

-- ١) معاينة الدعوة بالرمز — بلا سياق حساب
CREATE OR REPLACE FUNCTION app_invite_preview(p_token_hash TEXT)
RETURNS TABLE (
    invite_id BIGINT,
    person_name TEXT,
    company_name_ar TEXT,
    company_name_en TEXT,
    account_locale TEXT,
    is_usable BOOLEAN
) AS $$
    SELECT i.id,
           TRIM(CONCAT_WS(' ', p.first_name_ar, p.father_name_ar,
                               p.family_name_ar))::TEXT,
           c.legal_name_ar::TEXT,
           c.legal_name_en::TEXT,
           a.default_locale::TEXT,
           (i.status = 'pending' AND i.expires_at > now())
    FROM accounts_joininvite i
    JOIN employees_person p ON p.id = i.person_id
    JOIN accounts_company c ON c.id = i.company_id
    JOIN accounts_account a ON a.id = i.account_id
    WHERE i.token_hash = p_token_hash;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_invite_preview(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_invite_preview(TEXT) TO hrm_runtime;

-- ٢) قبول الدعوة — ربط المستخدم وإغلاقها ذرّيًّا
CREATE OR REPLACE FUNCTION app_invite_accept(
    p_token_hash TEXT, p_user_id BIGINT, p_locale TEXT DEFAULT NULL
) RETURNS TABLE (ok BOOLEAN, reason TEXT) AS $$
DECLARE
    v_invite  accounts_joininvite%ROWTYPE;
    v_has_user BIGINT;
BEGIN
    SELECT * INTO v_invite FROM accounts_joininvite
        WHERE token_hash = p_token_hash FOR UPDATE;
    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'not_found'; RETURN;
    END IF;
    IF v_invite.status <> 'pending' THEN
        RETURN QUERY SELECT FALSE, 'already_used'; RETURN;
    END IF;
    IF v_invite.expires_at <= now() THEN
        RETURN QUERY SELECT FALSE, 'expired'; RETURN;
    END IF;

    -- من له حساب أصلًا لا تُنشأ له ثانٍ: الدعوة تُغلق بلا ربط.
    SELECT user_id INTO v_has_user FROM employees_person
        WHERE id = v_invite.person_id;
    IF v_has_user IS NOT NULL THEN
        RETURN QUERY SELECT FALSE, 'already_has_account'; RETURN;
    END IF;

    UPDATE employees_person
       SET user_id = p_user_id,
           preferred_locale = COALESCE(p_locale, preferred_locale)
     WHERE id = v_invite.person_id;

    UPDATE accounts_joininvite
       SET status = 'accepted', accepted_at = now(),
           created_user_id = p_user_id, updated_at = now()
     WHERE id = v_invite.id;

    RETURN QUERY SELECT TRUE, 'ok';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

REVOKE ALL ON FUNCTION app_invite_accept(TEXT, BIGINT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_invite_accept(TEXT, BIGINT, TEXT) TO hrm_runtime;
"""

REVERSE = """
DROP POLICY IF EXISTS invite_isolation ON accounts_joininvite;
DROP FUNCTION IF EXISTS app_invite_preview(TEXT);
DROP FUNCTION IF EXISTS app_invite_accept(TEXT, BIGINT, TEXT);
"""


class Migration(migrations.Migration):

    dependencies = [("accounts", "0032_join_invite")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
