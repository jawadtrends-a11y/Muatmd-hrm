"""
عزل جداول الإجازات والطلبات.

LeaveTier و ApprovalStep يرثان عزلهما من الأب (لا account_id فيهما).
"""
from django.db import migrations

COMPANY_TABLES = [
    "leaves_leavetype",
    "leaves_leavebalance",
    "leaves_leaveentitlement",
    "leaves_request",
    "leaves_approvalchain",
    "leaves_requestapproval",
]

FORWARD = "\n".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_isolation ON {t}
    USING (
        account_id = app_current_account_id()
        AND (
            app_current_company_ids() IS NULL
            OR company_id = ANY(app_current_company_ids())
        )
    )
    WITH CHECK (account_id = app_current_account_id());
"""
    for t in COMPANY_TABLES
) + """
-- شرائح الإجازة ترث عزل نوع الإجازة
ALTER TABLE leaves_leavetier ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaves_leavetier FORCE ROW LEVEL SECURITY;
CREATE POLICY leaves_leavetier_isolation ON leaves_leavetier
    USING (EXISTS (
        SELECT 1 FROM leaves_leavetype lt
        WHERE lt.id = leave_type_id
          AND lt.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM leaves_leavetype lt
        WHERE lt.id = leave_type_id
          AND lt.account_id = app_current_account_id()
    ));

-- درجات الاعتماد ترث عزل السلسلة
ALTER TABLE leaves_approvalstep ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaves_approvalstep FORCE ROW LEVEL SECURITY;
CREATE POLICY leaves_approvalstep_isolation ON leaves_approvalstep
    USING (EXISTS (
        SELECT 1 FROM leaves_approvalchain ac
        WHERE ac.id = chain_id
          AND ac.account_id = app_current_account_id()
    ))
    WITH CHECK (EXISTS (
        SELECT 1 FROM leaves_approvalchain ac
        WHERE ac.id = chain_id
          AND ac.account_id = app_current_account_id()
    ));
"""

REVERSE = "\n".join(
    f"""
DROP POLICY IF EXISTS {t}_isolation ON {t};
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in COMPANY_TABLES + ["leaves_leavetier", "leaves_approvalstep"]
)


class Migration(migrations.Migration):
    dependencies = [
        ("leaves", "0002_entitlements_and_requests"),
        ("accounts", "0002_enable_rls"),
    ]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
