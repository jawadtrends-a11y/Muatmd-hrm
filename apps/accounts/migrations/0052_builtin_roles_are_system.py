"""
الأدوار المبذورة كلّها أساسية (ق-127).

⚠️ كان `owner` وحده محميًّا — والستّة الباقية تُحذف، فيبقى من
عليها بلا صلاحيات وينكسر ما يشير إليها برمزها (سلاسل الاعتماد،
والتذكير، والودجتات).

**والمحميّ وجودُها لا محتواها**: صلاحياتها تُعدَّل بحرّية.
"""
from django.db import migrations

BUILTIN = ["owner", "hr_manager", "hr_staff", "dept_manager",
           "supervisor", "employee", "ceo"]


def mark(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    n = Role.objects.filter(code__in=BUILTIN).update(is_system=True)
    print(f"    حُميت {n} دورًا")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0051_feature_platform_write")]
    operations = [migrations.RunPython(mark, migrations.RunPython.noop)]
