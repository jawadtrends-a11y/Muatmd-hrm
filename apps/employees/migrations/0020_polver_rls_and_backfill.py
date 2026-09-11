"""
عزل نسخ اللائحة، وربط البنود القائمة بنسخةٍ أولى (ق-130).

⚠️ **بندٌ بلا نسخة يتيمٌ**: لا يُعرف متى سرى ولا بماذا يُقاس
جزاؤه. فتُنشأ نسخةٌ أولى من تاريخ إنشاء الشركة وتُربط بها بنودها.
"""
from django.db import migrations

FORWARD = """
ALTER TABLE employees_policyversion ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees_policyversion FORCE ROW LEVEL SECURITY;
CREATE POLICY polver_isolation ON employees_policyversion
    USING (account_id = app_current_account_id())
    WITH CHECK (account_id = app_current_account_id());
"""

REVERSE = "DROP POLICY IF EXISTS polver_isolation ON employees_policyversion;"


def backfill(apps, schema_editor):
    Company = apps.get_model("accounts", "Company")
    PolicyVersion = apps.get_model("employees", "PolicyVersion")
    ViolationType = apps.get_model("employees", "ViolationType")

    # ⚠️ الجمع في بايثون لا بـdistinct: الاستعلام المرشَّح قد
    # يعيد المعرّف مرّاتٍ، فيُنشأ للشركة نسختان ويصطدم القيد.
    company_ids = sorted({
        c for c in ViolationType.objects
        .filter(policy_version__isnull=True)
        .values_list("company_id", flat=True)
    })

    made = linked = 0
    for comp_id in company_ids:
        comp = Company.objects.filter(id=comp_id).first()
        if comp is None:
            continue
        first = (ViolationType.objects.filter(company_id=comp_id)
                 .order_by("created_at").first())
        v = PolicyVersion.objects.filter(company_id=comp_id,
                                         number=1).first()
        if v is None:
            v = PolicyVersion.objects.create(
                account_id=comp.account_id, company_id=comp_id, number=1,
                effective_from=(first.created_at.date() if first
                                else comp.created_at.date()),
                note="النسخة الأولى — أُنشئت بالترحيل",
                is_active=True)
            made += 1
        linked += ViolationType.objects.filter(
            company_id=comp_id, policy_version__isnull=True
        ).update(policy_version=v)
    print(f"    نسخ: {made} · بنود مربوطة: {linked}")


class Migration(migrations.Migration):
    dependencies = [("employees", "0019_penalty_policy_versions")]
    operations = [
        migrations.RunSQL(FORWARD, REVERSE),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
