"""
ق-223: دعوةٌ بدور المالك تُملّك، وبريدٌ مطابقٌ يُربط بلا حساب ثانٍ.

قرار جواد: الأدوار كلها في قائمة الدعوة — ومنها «مالك الحساب»،
**ودورٌ لا يُملّك خيارٌ يوهم ولا يفعل**. والمالكان يبقيان معًا.

وإن كان بريد الموظف بريدَ مستخدمٍ قائم: **لا حسابَ ثانٍ ولا كلمة
مرور** — فالبريد واحدٌ والشخص واحد. يُربط الملف به، والدعوة
تأكيدُ استلامٍ لا تفعيلَ حساب.
"""
from django.db import migrations

FORWARD = """
DROP FUNCTION IF EXISTS app_invite_accept(TEXT, BIGINT, TEXT);

CREATE FUNCTION app_invite_accept(
    p_token_hash TEXT, p_user_id BIGINT, p_locale TEXT DEFAULT NULL)
RETURNS TABLE (ok BOOLEAN, reason TEXT) AS $$
DECLARE
    v_invite  accounts_joininvite%ROWTYPE;
    v_has_user BIGINT;
    v_account BIGINT;
    v_mobile  TEXT;
    v_company BIGINT;
    v_emp     BIGINT;
    v_member  BIGINT;
    v_scope   TEXT;
    v_code    TEXT;
    v_owner   BOOLEAN := FALSE;
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

    SELECT user_id, account_id, COALESCE(mobile_e164, '')
      INTO v_has_user, v_account, v_mobile
      FROM employees_person WHERE id = v_invite.person_id;
    IF v_has_user IS NOT NULL THEN
        RETURN QUERY SELECT FALSE, 'already_has_account'; RETURN;
    END IF;

    UPDATE employees_person
       SET user_id = p_user_id,
           preferred_locale = COALESCE(p_locale, preferred_locale)
     WHERE id = v_invite.person_id;

    SELECT id, company_id INTO v_emp, v_company
      FROM employees_employment
     WHERE person_id = v_invite.person_id AND status = 'active'
     ORDER BY join_date DESC, id DESC
     LIMIT 1;

    -- ودورُ المالك يُملّك فعلًا: فدورٌ لا يفعل خيارٌ يوهم.
    SELECT code, default_scope INTO v_code, v_scope
      FROM accounts_role WHERE id = v_invite.role_id;
    v_owner := (v_code = 'owner');

    INSERT INTO accounts_accountmembership
        (account_id, user_id, active_company_id, is_account_owner,
         is_founding_owner, login_mobile, created_at, owner_since)
    VALUES (v_account, p_user_id, v_company, v_owner, FALSE,
            v_mobile, now(), CASE WHEN v_owner THEN now() END)
    ON CONFLICT (user_id) DO UPDATE
        SET is_account_owner = accounts_accountmembership.is_account_owner
                               OR EXCLUDED.is_account_owner;

    SELECT id INTO v_member FROM accounts_accountmembership
     WHERE user_id = p_user_id;

    IF v_invite.role_id IS NOT NULL AND v_member IS NOT NULL THEN
        INSERT INTO accounts_roleassignment
            (membership_id, role_id, employment_id, company_id, scope)
        VALUES (v_member, v_invite.role_id, v_emp, v_company,
                COALESCE(v_scope, 'own'));
    END IF;

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

REVERSE = "-- لا رجوع."


class Migration(migrations.Migration):

    dependencies = [("accounts", "0061_invite_accept_role")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
