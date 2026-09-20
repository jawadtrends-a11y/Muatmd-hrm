"""ق-223: القبول يُسند الدور المحفوظ في الدعوة."""
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

    INSERT INTO accounts_accountmembership
        (account_id, user_id, active_company_id, is_account_owner,
         is_founding_owner, login_mobile, created_at)
    VALUES (v_account, p_user_id, v_company, FALSE, FALSE,
            v_mobile, now())
    ON CONFLICT (user_id) DO NOTHING;

    SELECT id INTO v_member FROM accounts_accountmembership
     WHERE user_id = p_user_id;

    -- ق-223: والعضوية بلا دور صفرُ صلاحيات — فمن دخل لا يرى شيئًا.
    IF v_invite.role_id IS NOT NULL AND v_member IS NOT NULL THEN
        SELECT default_scope INTO v_scope FROM accounts_role
         WHERE id = v_invite.role_id;
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

REVERSE = "-- لا رجوع: نسخة بلا دور تُعيد العطل نفسه."


class Migration(migrations.Migration):

    dependencies = [("accounts", "0060_invite_role")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
