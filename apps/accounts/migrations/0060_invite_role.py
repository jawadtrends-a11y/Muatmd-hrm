"""
ق-223: الدور يُختار عند الدعوة — ويُسند عند القبول.

بلاغ جواد: الموظف يقبل الدعوة ويدخل **فلا يرى شيئًا** —
فالعضوية بلا دور **صفرُ صلاحيات**، والشاشات كلّها مغلقة.

والدور لا يُسند وقت الدعوة: فـRoleAssignment يحتاج membership،
**ولا مستخدمَ بعد**. فيُحفظ في الدعوة ويُسند عند القبول.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("accounts", "0059_invite_accept_membership")]

    operations = [
        migrations.AddField(
            model_name="joininvite",
            name="role",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="accounts.role", verbose_name="الدور"),
        ),
    ]
