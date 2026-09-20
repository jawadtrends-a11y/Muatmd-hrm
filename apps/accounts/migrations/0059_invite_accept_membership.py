"""ق-223: قبول الدعوة يُنشئ العضوية — وبلاها لا يدخل أحد."""
from django.db import migrations

FORWARD = """
-- الدالّة القائمة لها قيمٌ افتراضية، وCREATE OR REPLACE لا
-- يُزيلها — فتُسقط أولًا. والصلاحيات تُعاد في آخر الهجرة.
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

    SELECT company_id INTO v_company
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

REVERSE = "-- لا رجوع: نسخة بلا عضوية تُعيد العطل نفسه."


class Migration(migrations.Migration):

    dependencies = [("accounts", "0058_zatca_invoice")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
