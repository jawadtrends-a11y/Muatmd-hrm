"""
مهام الحضور الدورية.
"""
from apps.core.tenancy.platform import across_accounts, all_account_ids
import logging

from celery import shared_task

log = logging.getLogger("muatmd.attendance")


@shared_task(name="attendance.pull_biotime_files")
def pull_biotime_files():
    """
    يقرأ ملفات BioTime المرفوعة لكل شركة ويُدخل بصماتها (ق-85).

    كل شركة لها مجلد محبوس باسم bt<company_id>، وترفع فيه BioTime
    ملفاتها. والمهمة تقرأ ثم تنقل لأرشيف — فالملف دليل يُرجع إليه
    (ق-44).
    """
    from pathlib import Path

    from apps.accounts.models import Company
    from apps.attendance.models_sites import PunchDevice
    from apps.attendance.services.biotime import ingest_folder
    from apps.core.tenancy.context import account_scope

    base = Path("/srv/biotime")
    if not base.is_dir():
        return {"skipped": "لا مجلد استقبال"}

    total = {"companies": 0, "accepted": 0, "duplicated": 0, "errors": []}

    for home in sorted(base.glob("bt*")):
        upload = home / "upload"
        if not upload.is_dir() or not any(upload.iterdir()):
            continue

        try:
            company_id = int(home.name[2:])
        except ValueError:
            continue

        # النطاق يُفتح لكل شركة على حدة: المهمة تمرّ على الحسابات
        # كلها، فلا نطاق واحد لها — وقراءة أجهزتها خارج نطاقها
        # تسرّب.
        company = Company.objects.filter(id=company_id).first()
        if company is None:
            continue

        with account_scope(company.account_id):
            # الملفات تُنسب لأول جهاز نشط في الشركة — ورقم الجهاز
            # الحقيقي محفوظ في البيانات الخام لكل بصمة
            device = PunchDevice.objects.filter(
                company_id=company_id,
                is_active=True).order_by("id").first()

        if device is None:
            total["errors"].append({
                "company": company_id,
                "error": "لا جهاز نشط — أنشئ جهازًا قبل استقبال ملفاته",
            })
            continue

        try:
            res = ingest_folder(folder=upload, device=device,
                                archive=home / "archive")
            total["companies"] += 1
            total["accepted"] += res["accepted"]
            total["duplicated"] += res["duplicated"]
            total["errors"].extend(res.get("errors", []))
        except Exception as e:      # noqa: BLE001
            log.exception("biotime_pull_failed",
                          extra={"company": company_id})
            total["errors"].append({"company": company_id,
                                    "error": str(e)})

    if total["accepted"] or total["errors"]:
        log.info("biotime_pull_done", extra=total)
    return total



# ══════════ احتساب الحضور تلقائيًّا (ق-234) ══════════
#
# \u26a0\u26a0 **كان لا يُحتسب إلا بزرٍّ يدويّ** — فلا غياب يُسجَّل ولا تأخير،
# والمسير يصرف الشهر كاملًا. وقاعدة جواد: «الغياب هو الأصل حتى يُقدَّم ما
# يعدّله · وتحديث الحضور فوريّ من البصمات».

from apps.core.tasks import AccountTask  # noqa: E402


@shared_task(base=AccountTask, bind=True, max_retries=2, default_retry_delay=30)
def process_day(self, *, account_id, employment_id, day):
    """يومٌ واحد لموظفٍ واحد — تُطلقه كلّ بصمة، فيظهر حضوره خلال ثوانٍ."""
    from datetime import date as _d
    from apps.attendance.services.processing import process_employment_days
    from apps.employees.models import Employment
    emp = Employment.objects.filter(id=employment_id).first()
    if emp is None:
        return {"skipped": "no_employment"}
    d = _d.fromisoformat(day)
    process_employment_days(employment=emp, start_date=d, end_date=d)
    return {"processed": day}


@shared_task(base=AccountTask, bind=True)
def process_account_day(self, *, account_id, day):
    """
    يومٌ لكلّ موظفي حساب — **فيُنشئ الغياب لمن لم يبصم**.

    ⚠️ **وفشل موظفٍ لا يوقف الباقين** — يُسجَّل ويُكمَل.
    """
    import logging
    from datetime import date as _d
    from apps.attendance.services.processing import process_employment_days
    from apps.employees.models import Employment, EmploymentStatus
    log = logging.getLogger("muatmd.attendance")
    d = _d.fromisoformat(day)
    ok = failed = 0
    from apps.payroll.models import PayrollSettings
    manual = set(PayrollSettings.objects.filter(auto_attendance=False)
                 .values_list("company_id", flat=True))
    for emp in Employment.objects.filter(
            status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE],
            join_date__lte=d).exclude(company_id__in=manual):
        try:
            process_employment_days(employment=emp, start_date=d, end_date=d)
            ok += 1
        except Exception:  # noqa: BLE001
            failed += 1
            log.exception("nightly_day_failed", extra={"employment_id": emp.id, "day": day})
    return {"day": day, "ok": ok, "failed": failed}


@shared_task(bind=True)
def nightly_process(self):
    """
    كلّ ليلة: **أمس** لكلّ حساب — بتوقيت الرياض.

    ⚠️ **أمسُ لا اليوم**: فمن لم يبصم التاسعة صباحًا ليس غائبًا بعد.
    ⚠️ **ويُحسب بـlocaldate()** — فأيًّا كان توقيت Celery يقع بعد منتصف ليل الرياض.
    """
    from datetime import timedelta as _td
    from django.utils import timezone as _tz
    from apps.accounts.models import Account
    day = (_tz.localdate() - _td(days=1)).isoformat()
    ids = all_account_ids()   # ق-234: لا Account.objects بلا سياق
    for acc in ids:
        process_account_day.apply_async(kwargs={"account_id": acc, "day": day})
    return {"day": day, "accounts": len(ids)}



@shared_task(base=AccountTask, bind=True)
def process_account_absences(self, *, account_id):
    """
    ق-235: **«غائب» فور بداية الدوام بلا بصمة** (قرار جواد).

    - ⚠️ **من بدأ دوامه فقط** — فالمحرّك لا يعرف الساعة: شغّله السابعة لمن
      دوامه الثامنة **لسجّله غائبًا قبل أن يبدأ**
    - ⚠️ **ومن لا يومَ له اليوم فقط** — فمن بصم احتُسب ببصمته، ومن سُجّل
      لا يُعاد: **فالفحص خفيفٌ ولو كبر العملاء**
    - وحين يبصم يتحوّل «حاضرًا متأخّرًا» فورًا (process_punch_day)
    """
    import logging
    from django.db import transaction
    from django.utils import timezone as _tz
    from apps.attendance.models import AttendanceDay
    from apps.attendance.services.processing import process_employment_days
    from apps.attendance.services.rules import effective_shift
    from apps.employees.models import Employment, EmploymentStatus
    log = logging.getLogger("muatmd.attendance")
    now = _tz.localtime()
    today = now.date()
    done = set(AttendanceDay.objects.filter(work_date=today)
               .values_list("employment_id", flat=True))
    marked = failed = waiting = no_shift = 0
    from apps.payroll.models import PayrollSettings
    manual = set(PayrollSettings.objects.filter(auto_attendance=False)
                 .values_list("company_id", flat=True))   # شركاتٌ تُدخل حضورها يدويًّا
    for emp in (Employment.objects
                .filter(status__in=[EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE],
                        join_date__lte=today)
                .exclude(id__in=done).exclude(company_id__in=manual)):
        sh = effective_shift(emp, today)
        if sh is None:
            no_shift += 1      # ⚠️ لا يُخلط بـ«لم يبدأ دوامه» — فهو لن يبدأ أبدًا
            continue
        if not sh.start_time or sh.start_time > now.time():
            waiting += 1
            continue
        try:
            with transaction.atomic():
                process_employment_days(employment=emp, start_date=today, end_date=today)
            marked += 1
        except Exception:  # noqa: BLE001
            failed += 1
            log.exception("absence_sweep_failed", extra={"employment_id": emp.id})
    return {"marked": marked, "waiting": waiting, "no_shift": no_shift, "failed": failed}


@shared_task(bind=True)
def absence_sweep(self):
    """كلّ ١٥ دقيقة — لكلّ الحسابات (عبر app_platform_accounts لا Account.objects)."""
    ids = all_account_ids()
    for acc in ids:
        process_account_absences.apply_async(kwargs={"account_id": acc})
    return {"accounts": len(ids)}
