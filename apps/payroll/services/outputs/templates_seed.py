"""
قوالب البنوك الجاهزة.

⚠️ لا يُضاف قالب هنا إلا بمواصفات موثّقة من ملف بنك فعلي.
القالب المبني على تخمين يعني ملفًا مرفوضًا ورواتب متأخرة.

المؤكد حاليًا: البنك الأهلي (NCB) — مستخرج من ملف تصدير فعلي.
"""
from django.db import transaction

from apps.payroll.models import BankColumn, BankColumnSource, BankTemplate

# قالب الأهلي: (الترتيب، العنوان، المصدر، التنسيق، التحويل)
NCB_COLUMNS = [
    (1,  "Bank",                  BankColumnSource.EMPLOYEE_BANK_SWIFT, "", ""),
    (2,  "Account Number",        BankColumnSource.IBAN, "", "upper"),
    (3,  "Total Salary",          BankColumnSource.NET_PAY, "0.00", ""),
    (4,  "Transaction Reference", BankColumnSource.EMPLOYEE_NO, "", ""),
    (5,  "Name",                  BankColumnSource.NAME_EN, "", ""),
    (6,  "National ID/Iqama ID",  BankColumnSource.ID_NUMBER, "", ""),
    (7,  "Employee Address",      BankColumnSource.DEPARTMENT, "", "strip"),
    (8,  "Basic Salary",          BankColumnSource.BASIC, "0.00", ""),
    (9,  "Housing Allowance",     BankColumnSource.HOUSING, "0.00", ""),
    (10, "Other Earnings",        BankColumnSource.OTHER_EARNINGS, "0.00", ""),
    (11, "Deductions",            BankColumnSource.DEDUCTIONS, "0.00", ""),
]

BUILTIN_TEMPLATES = [
    {
        "code": "NCB",
        "name_ar": "قالب البنك الأهلي",
        "bank_name_ar": "البنك الأهلي السعودي",
        "swift_prefix": "NCBK",
        "delimiter": ",",
        "include_header": True,
        "line_ending": "crlf",
        "encoding": "utf-8",
        "filename_pattern": "NCB_For_{date}.csv",
        "note": ("مستخرج من ملف تصدير فعلي. Total Salary = الصافي "
                 "(الأساسي + السكن + أخرى − الخصومات)، و Employee Address "
                 "يحمل اسم القسم لا العنوان."),
        "columns": NCB_COLUMNS,
    },
]


@transaction.atomic
def provision_bank_templates(company):
    """ينسخ القوالب الجاهزة للشركة. آمن للتكرار."""
    created = []
    for spec in BUILTIN_TEMPLATES:
        tpl, is_new = BankTemplate.objects.get_or_create(
            company=company, code=spec["code"],
            defaults={
                "account": company.account,
                "name_ar": spec["name_ar"],
                "bank_name_ar": spec["bank_name_ar"],
                "swift_prefix": spec["swift_prefix"],
                "delimiter": spec["delimiter"],
                "include_header": spec["include_header"],
                "line_ending": spec["line_ending"],
                "encoding": spec["encoding"],
                "filename_pattern": spec["filename_pattern"],
                "note": spec["note"],
                "is_builtin": True,
            })
        if is_new:
            created.append(spec["code"])
            BankColumn.objects.bulk_create([
                BankColumn(template=tpl, position=pos, header=header,
                           source=source, number_format=fmt,
                           text_transform=transform)
                for pos, header, source, fmt, transform in spec["columns"]
            ])
    return created
