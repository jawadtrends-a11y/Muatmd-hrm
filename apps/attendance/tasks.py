"""
مهام الحضور الدورية.
"""
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
