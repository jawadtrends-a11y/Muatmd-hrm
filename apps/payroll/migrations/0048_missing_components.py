"""
ق-٢٤٤: المكوّنات الثلاثة الناقصة للشركات القائمة.

⚠️ المحرّك يولّد `UNPAID_LEAVE` و`DED_CAP` و`ACTIVITY` **ولا مكوّن لها** —
فلا تُربط في قالب القيد، **ويبقى القيد عالقًا حين تظهر**.
"""
from django.db import migrations


def forward(apps, schema_editor):
    Company = apps.get_model("accounts", "Company")
    PayComponent = apps.get_model("payroll", "PayComponent")
    SPECS = [
        ("UNPAID_LEAVE", "خصم إجازة بلا أجر", "Unpaid Leave Deduction",
         "بلا معاوضہ رخصت کٹوتی", "deduction", 120, False),
        ("DED_CAP", "ردّ ما تجاوز سقف الحسم", "Deduction Cap Refund",
         "کٹوتی کی حد کی واپسی", "earning", 45, True),
        ("ACTIVITY", "الأنشطة المراجَعة", "Reviewed Activities",
         "جائزہ شدہ سرگرمیاں", "deduction", 145, False),
    ]
    for c in Company.objects.all():
        for code, ar, en, ur, ctype, order, wps in SPECS:
            PayComponent.objects.get_or_create(
                company_id=c.id, code=code,
                defaults={"account_id": c.account_id, "name_ar": ar,
                          "name_en": en, "name_ur": ur, "component_type": ctype,
                          "is_gosi_subject": False, "is_eosb_subject": False,
                          "is_overtime_base": False, "is_wps_subject": wps,
                          "is_absence_base": False, "is_system": True,
                          "display_order": order})


class Migration(migrations.Migration):
    dependencies = [("payroll", "0047_payslipline_explanation_en")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
