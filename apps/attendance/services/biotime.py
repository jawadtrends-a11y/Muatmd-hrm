"""
قارئ ملفات BioTime (ق-85).

BioTime يصدّر CSV مفصولًا بـTab إلى مجلد. وهذه الخدمة تقرأه
وتمرّره بنفس منطق ق-84 — فالتعافي ومنع التكرار لا يتكرّران.
"""
import csv
import logging
from datetime import datetime
from pathlib import Path

from django.utils import timezone

log = logging.getLogger("muatmd.attendance")

#: ترتيب أعمدة قالب BioTime المعتمد (ق-85)
COLUMNS = ["emp_code", "punch_time", "punch_state", "work_code",
           "card_number", "area_name", "terminal_alias", "terminal_sn"]


class BioTimeError(ValueError):
    """خطأ في ملف BioTime — رسالة تخبر بما يُفعل."""


def parse_rows(text):
    """
    يحوّل نصّ الملف إلى بصمات.

    ويقبل الملف برأس أعمدة أو بدونه: BioTime يصدّر بلا رأس عادةً،
    وبعض النسخ تضيفه — فلا نرفض ملفًا لسطر زائد.
    """
    rows = []
    reader = csv.reader(text.splitlines(), delimiter="\t")

    for line_no, cells in enumerate(reader, 1):
        if not cells or not any(c.strip() for c in cells):
            continue

        # رأس الأعمدة إن وُجد — يُتخطّى
        if cells[0].strip().lower() in ("emp_code", "employee", "user_id"):
            continue

        data = dict(zip(COLUMNS, [c.strip() for c in cells]))
        emp_no = data.get("emp_code") or ""
        at_raw = data.get("punch_time") or ""

        if not emp_no or not at_raw:
            rows.append({"_error": "سطر ناقص", "_line": line_no,
                         "_raw": cells[:4]})
            continue

        at = _parse_time(at_raw)
        if at is None:
            rows.append({"_error": f"تاريخ غير مقروء: {at_raw}",
                         "_line": line_no})
            continue

        rows.append({
            "employee_no": emp_no,
            "punched_at": at,
            "terminal_sn": data.get("terminal_sn") or "",
            "punch_state": data.get("punch_state") or "",
            "raw": data,
        })

    return rows


def _parse_time(value):
    """
    يقرأ الوقت بصيغه المحتملة.

    فالإعداد يقول yyyy-MM-DD HH:mm:ss، لكن النسخ تختلف — ومن
    يرفض صيغة يخسر يوم بصمات.
    """
    value = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S",
                "%Y%m%d%H%M%S"):
        try:
            naive = datetime.strptime(value, fmt)
            return timezone.make_aware(naive)
        except ValueError:
            continue
    return None


def ingest_text(*, text, device, source_name=""):
    """
    يُدخل بصمات نصّ ملف واحد.

    والمنطق واحد مع ق-84: البصمة بوقتها الأصلي، والمكرّرة تُتجاهل
    (الجهاز + الموظف + الوقت بالثانية).
    """
    from apps.attendance.models import AttendancePunch, PunchSource
    from apps.core.tenancy.context import account_scope
    from apps.employees.models import Employment, EmploymentStatus

    rows = parse_rows(text)
    accepted = duplicated = 0
    unknown, invalid = [], []

    with account_scope(device.account_id):
        emp_by_no = {
            e.employee_no: e
            for e in Employment.objects.filter(
                company_id=device.company_id,
                status=EmploymentStatus.ACTIVE)
        }

        for row in rows:
            if row.get("_error"):
                invalid.append(row)
                continue

            emp = emp_by_no.get(row["employee_no"])
            if emp is None:
                unknown.append(row["employee_no"])
                continue

            _obj, created = AttendancePunch.objects.get_or_create(
                account_id=device.account_id,
                company_id=device.company_id,
                employment=emp,
                punched_at=row["punched_at"],
                device_id=device.device_code,
                defaults={
                    "source": PunchSource.DEVICE,
                    # external_ref فريد لكل شركة — فهو معرّف
                    # البصمة لا الجهاز. ورقم الجهاز في raw_payload.
                    "external_ref": (
                        f"{device.device_code}:{row['employee_no']}:"
                        f"{row['punched_at'].isoformat()}"),
                    "raw_payload": row.get("raw", {}),
                })
            accepted += int(created)
            duplicated += int(not created)

        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])

    log.info("biotime_file_ingested", extra={
        "device": device.device_code, "file": source_name,
        "accepted": accepted, "duplicated": duplicated,
    })

    return {
        "accepted": accepted, "duplicated": duplicated,
        "unknown_employees": sorted(set(unknown))[:20],
        "invalid": invalid[:20],
        "received": len([r for r in rows if not r.get("_error")]),
    }


def ingest_folder(*, folder, device, archive=None):
    """
    يقرأ كل ملفات مجلد ثم ينقلها لأرشيف.

    والملف يُنقل لا يُحذف: من يشكّ في بصمة يعود للملف الأصلي
    (ق-44). ومن يُحذف ملفه يفقد الدليل.
    """
    src = Path(folder)
    if not src.is_dir():
        raise BioTimeError(f"المجلد غير موجود: {folder}")

    arc = Path(archive) if archive else src / "archive"
    arc.mkdir(parents=True, exist_ok=True)

    total = {"files": 0, "accepted": 0, "duplicated": 0, "errors": []}

    for f in sorted(src.glob("*.txt")) + sorted(src.glob("*.csv")):
        try:
            text = f.read_text(encoding="utf-8-sig", errors="replace")
            res = ingest_text(text=text, device=device, source_name=f.name)
            total["files"] += 1
            total["accepted"] += res["accepted"]
            total["duplicated"] += res["duplicated"]

            stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
            f.rename(arc / f"{stamp}-{f.name}")
        except Exception as e:      # noqa: BLE001
            # ملف واحد فاسد لا يوقف الباقي — والخطأ يُسجَّل
            log.exception("biotime_file_failed", extra={"file": f.name})
            total["errors"].append({"file": f.name, "error": str(e)})

    return total
