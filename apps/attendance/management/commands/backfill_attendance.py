"""
احتساب الحضور لفترةٍ ماضية — لكلّ الحسابات (ق-235).

الاستعمال: python manage.py backfill_attendance --from 2026-08-01 [--to …] [--account 6]

⚠️ **الاحتساب التلقائيّ يبدأ من يوم تفعيله** — فما قبله لم يحتسبه أحد في أيّ حساب.
وهذا يملأ الفجوة **لكلّ الحسابات لا لحسابٍ بعينه**، ويبقى **لنقل بيانات النظام القديم**.
- الحسابات من `app_platform_accounts` (لا Account.objects بلا سياق — ق-234)
- **يتخطّى الشركات التي أوقفت الاحتساب** — فلا تُصفَّر رواتب من يُدخل حضوره يدويًّا
- **لا يتجاوز أمس** · ولا يسبق انضمام الموظف · **والمعدَّل يدويًّا محفوظ** (force=False)
- وفشل موظفٍ لا يوقف الباقين
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.tenancy.context import account_scope
from apps.core.tenancy.platform import all_account_ids


class Command(BaseCommand):
    help = "احتساب الحضور لفترةٍ ماضية لكلّ الحسابات"

    def add_arguments(self, p):
        p.add_argument("--from", dest="start", required=True)
        p.add_argument("--to", dest="end")
        p.add_argument("--account", type=int)

    def handle(self, *args, start, end, account, **kw):
        from apps.attendance.services.processing import process_employment_days
        from apps.employees.models import Employment, EmploymentStatus
        from apps.payroll.models import PayrollSettings

        yesterday = timezone.localdate() - timedelta(days=1)
        s = date.fromisoformat(start)
        e = min(date.fromisoformat(end), yesterday) if end else yesterday
        total_ok = total_fail = 0
        for acc in ([account] if account else all_account_ids()):
            ok = fail = 0
            with account_scope(acc):
                manual = set(PayrollSettings.objects.filter(auto_attendance=False)
                             .values_list("company_id", flat=True))
                emps = (Employment.objects
                        .filter(join_date__lte=e)
                        .filter(Q(status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE])
                                | Q(status=EmploymentStatus.TERMINATED, termination_date__gte=s))
                        .exclude(company_id__in=manual))
                for emp in emps:
                    a = max(s, emp.join_date)
                    b = min(e, emp.termination_date) if emp.termination_date else e
                    if a > b:
                        continue
                    try:
                        with transaction.atomic():
                            process_employment_days(employment=emp, start_date=a, end_date=b)
                        ok += 1
                    except Exception as ex:  # noqa: BLE001
                        fail += 1
                        self.stderr.write(f"  فشل {emp.id}: {ex}")
            self.stdout.write(f"حساب {acc:>3}: {ok} موظفًا · فشل {fail}")
            total_ok += ok; total_fail += fail
        self.stdout.write(f"✔ {s} ← {e} · {total_ok} موظفًا · فشل {total_fail}")
