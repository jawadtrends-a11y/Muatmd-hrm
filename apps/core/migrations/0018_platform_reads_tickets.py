"""
قراءة التذاكر من لوحة المنصّة (ق-133).

⚠️ **العزل يحجبها عن المنصّة**: التذاكر معزولة بالحساب، ولوحة
المنصّة تراها كلّها بحكم دورها — ولا سياق حساب لها.

فدالّةٌ `SECURITY DEFINER` تقرأ فوق العزل، **وتُمنح للمنصّة
وحدها**: العميل يقرأ تذاكره بالمسار المعتاد، ولا سبيل له إلى هذه.
"""
from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION app_platform_tickets(
    p_status text DEFAULT '',
    p_only_open boolean DEFAULT false
)
RETURNS TABLE (
    id bigint, ticket_no varchar, subject varchar, kind varchar,
    priority varchar, status varchar, opened_by_name varchar,
    created_at timestamptz, due_at timestamptz,
    first_response_at timestamptz, sla_hours smallint,
    sla_business_hours boolean, plan_code_at_open varchar,
    company_name varchar, account_name varchar,
    account_id bigint, company_id bigint, msgs bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT t.id, t.ticket_no, t.subject, t.kind, t.priority,
           t.status, t.opened_by_name, t.created_at, t.due_at,
           t.first_response_at, t.sla_hours, t.sla_business_hours,
           t.plan_code_at_open,
           c.legal_name_ar, a.display_name_ar,
           t.account_id, t.company_id,
           (SELECT count(*) FROM core_ticketmessage m
             WHERE m.ticket_id = t.id)
      FROM core_supportticket t
      JOIN accounts_company c ON c.id = t.company_id
      JOIN accounts_account a ON a.id = t.account_id
     WHERE (p_status = '' OR t.status = p_status)
       AND (NOT p_only_open OR t.status <> 'resolved')
     ORDER BY
       CASE WHEN t.first_response_at IS NULL THEN 0 ELSE 1 END,
       t.due_at NULLS LAST, t.id DESC
     LIMIT 300;
$$;

CREATE OR REPLACE FUNCTION app_ticket_account(p_ticket_id bigint)
RETURNS bigint
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT account_id FROM core_supportticket WHERE id = p_ticket_id;
$$;
"""

REVERSE = """
DROP FUNCTION IF EXISTS app_platform_tickets(text, boolean);
DROP FUNCTION IF EXISTS app_ticket_account(bigint);
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0017_tickets_rls")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
