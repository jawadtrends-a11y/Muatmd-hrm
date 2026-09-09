"""
ربط الإسنادات القائمة بتوظيفاتها (ق-115).

لكل إسناد: نجد توظيف صاحب العضوية في شركة الإسناد، فنربطهما.
ومن لا توظيف له (مالك الحساب قبل أن يضيف نفسه) يبقى بلا ربط —
وعضويته تكفيه.
"""
from django.db import migrations


def link_forward(apps, schema_editor):
    RoleAssignment = apps.get_model("accounts", "RoleAssignment")
    Employment = apps.get_model("employees", "Employment")

    linked = orphan = 0
    for ra in RoleAssignment.objects.select_related(
            "membership__user").iterator():
        user = ra.membership.user
        person_id = getattr(getattr(user, "person", None), "id", None)
        if person_id is None or ra.company_id is None:
            orphan += 1
            continue
        emp = Employment.objects.filter(
            person_id=person_id, company_id=ra.company_id).first()
        if emp is None:
            orphan += 1
            continue
        ra.employment_id = emp.id
        ra.save(update_fields=["employment"])
        linked += 1
    print(f"    ربط: {linked} · بلا توظيف: {orphan}")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0046_role_on_employment"),
        ("employees", "0001_employee_models"),
    ]
    operations = [migrations.RunPython(link_forward,
                                       migrations.RunPython.noop)]
