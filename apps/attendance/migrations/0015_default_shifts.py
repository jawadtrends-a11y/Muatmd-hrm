"""
ق-235: الفترة الافتراضية للشركات القائمة التي بلا فترة.

⚠️ **والتأسيس لم يكن يُنشئها** — فتسع شركاتٍ بلا فترة: لا غياب ولا تأخير يُحسب
لأحدٍ فيها. **ولا تمسّ شركةً لها افتراضيةٌ أصلًا** (حساب ٦).
"""
from datetime import time

from django.db import migrations


def forward(apps, schema_editor):
    Company = apps.get_model("accounts", "Company")
    Shift = apps.get_model("attendance", "Shift")
    for c in Company.objects.all():
        if Shift.objects.filter(company_id=c.id, is_default=True).exists():
            continue
        code = "DEFAULT" if not Shift.objects.filter(
            company_id=c.id, code="DEFAULT").exists() else "DEFAULT-2"
        Shift.objects.create(
            account_id=c.account_id, company_id=c.id, code=code,
            name_ar="الدوام الرسمي", name_en="Standard shift",
            start_time=time(8, 0), end_time=time(17, 0), break_minutes=60,
            grace_in_minutes=15, working_days=[0, 1, 2, 3, 4],
            is_default=True, is_active=True)


class Migration(migrations.Migration):
    dependencies = [("attendance", "0014_presence_rls")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
