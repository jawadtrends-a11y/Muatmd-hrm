"""
زرع سجل المزايا والباقات الافتراضية (ق-123).

⚠️ كانت تُزرع يدويًّا — فقاعدةٌ جديدة تقوم بلا مزايا ولا باقات،
والمزايا كلّها مغلقة. وبعد أن صارت الحراسة تعمل، صار ذلك يُعطّل
النظام كلّه في أي بيئة جديدة.

والزرع **آمن للتكرار**: لا يدوس ما عدّله المشغّل من اللوحة.
"""
from django.db import migrations


def seed(apps, schema_editor):
    from apps.accounts.services.plans import (
        sync_default_plans, sync_feature_registry)

    feats = sync_feature_registry()
    plans = sync_default_plans()
    print(f"    مزايا: {feats} · باقات: {plans}")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0049_feature_implemented")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
