"""
خدمة رفع الملفات (ق-61).

ثلاث سياسات تحدّ من التضخم:
  ١. تصغير الصور تلقائيًا — صورة هوية من جوال حديث تنزل من
     4 ميغا إلى نحو 300 كيلو بلا فقدان قراءة
  ٢. حدّ تخزين لكل حساب يضبطه السوبر أدمن
  ٣. كشف المكرر بالبصمة — نفس الملف لا يُخزَّن مرتين
"""
import hashlib
import io
import logging
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from apps.core.models_files import (
    BLOCKED_EXTENSIONS, KIND_RULES, FileKind, StoredFile,
)

logger = logging.getLogger("muatmd.files")


class UploadError(Exception):
    """خطأ رفع — رسالته تُعرض للمستخدم."""


# ══════════ التحقق ══════════

SIGNATURES = {
    b"%PDF": "pdf",
    b"\xff\xd8\xff": "jpg",
    b"\x89PNG\r\n": "png",
    b"RIFF": "webp",
    b"PK\x03\x04": "office",      # xlsx و docx
}


def _detect(head: bytes) -> str:
    for sig, label in SIGNATURES.items():
        if head.startswith(sig):
            return label
    return ""


def validate(uploaded, kind):
    """
    يتحقق من الامتداد والحجم والتوقيع الثنائي.

    **الفحص بالمحتوى لا بالاسم:** ملف باسم «عقد.pdf» قد يكون
    سكربتًا — والاعتماد على الامتداد وحده ثغرة.
    """
    name = (uploaded.name or "").strip()
    if not name:
        raise UploadError("اسم الملف فارغ")

    ext = Path(name).suffix.lower().lstrip(".")
    if not ext:
        raise UploadError("الملف بلا امتداد")
    if ext in BLOCKED_EXTENSIONS:
        raise UploadError(f"امتداد غير مسموح: .{ext}")

    allowed, max_kb, _max_px = KIND_RULES.get(
        kind, KIND_RULES[FileKind.OTHER])
    if ext not in allowed:
        raise UploadError(
            "الامتدادات المسموحة: " + "، ".join(sorted(allowed)))

    size = getattr(uploaded, "size", 0)
    if size == 0:
        raise UploadError("الملف فارغ")

    # الصور تُصغَّر فنسمح بأربعة أضعاف الحد قبل المعالجة
    is_image = ext in {"jpg", "jpeg", "png", "webp"}
    ceiling_kb = max_kb * 4 if is_image else max_kb
    if size > ceiling_kb * 1024:
        raise UploadError(
            f"الحجم يتجاوز {ceiling_kb / 1024:.1f} ميغابايت")

    head = uploaded.read(8)
    uploaded.seek(0)
    detected = _detect(head)

    if ext == "pdf" and detected != "pdf":
        raise UploadError("الملف ليس PDF صالحًا")
    if detected == "pdf" and ext != "pdf":
        raise UploadError("محتوى الملف PDF والامتداد يخالفه")
    if is_image and detected not in ("jpg", "png", "webp"):
        raise UploadError("الملف ليس صورة صالحة")

    return ext, is_image


# ══════════ التصغير ══════════

def shrink_image(uploaded, kind, ext):
    """
    يصغّر الصورة للحدّ المقرر لنوعها (ق-61).

    يرجع (محتوى، امتداد) — وقد يتحوّل PNG إلى JPEG لأن الأخير
    أصغر بكثير في الصور الفوتوغرافية.
    """
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.warning("pillow_missing — الصورة تُحفظ بحجمها الأصلي")
        return None, ext

    _allowed, max_kb, max_px = KIND_RULES.get(
        kind, KIND_RULES[FileKind.OTHER])
    if not max_px:
        return None, ext

    try:
        uploaded.seek(0)
        img = Image.open(uploaded)
        img = ImageOps.exif_transpose(img)      # تدوير حسب بيانات الجوال

        # الشفافية تُسطَّح على أبيض قبل التحويل لـJPEG
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA")
                     else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        quality = 80
        img.save(buf, format="JPEG", quality=quality, optimize=True)

        # إن بقيت أكبر من الحد، نخفّض الجودة تدريجيًا
        while buf.tell() > max_kb * 1024 and quality > 40:
            quality -= 10
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)

        if buf.tell() > max_kb * 1024:
            raise UploadError(
                f"تعذّر تصغير الصورة تحت {max_kb} كيلوبايت — "
                "جرّب صورة أصغر")

        return buf.getvalue(), "jpg"

    except UploadError:
        raise
    except Exception as e:      # noqa: BLE001
        logger.warning("shrink_failed: %s", e)
        return None, ext


# ══════════ الحفظ ══════════

def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def account_usage(account_id) -> dict:
    """
    استهلاك التخزين للحساب — لعرضه في اللوحة وفحص الحد.

    ق-61: الحد يضبطه السوبر أدمن، ونقيس الاستخدام الفعلي قبل
    وضع حدود الباقات.
    """
    from django.db.models import Count, Sum

    agg = StoredFile.objects.filter(
        account_id=account_id, is_deleted=False
    ).aggregate(total=Sum("size_bytes"), n=Count("id"))

    used = agg["total"] or 0
    return {
        "bytes": used,
        "mb": round(used / 1024 / 1024, 2),
        "gb": round(used / 1024 / 1024 / 1024, 3),
        "files": agg["n"] or 0,
    }


def _check_quota(account, incoming_bytes):
    """
    يمنع تجاوز حدّ الحساب إن كان مضبوطًا.

    الحد صفر أو None يعني «بلا حد» — وهو الافتراضي حتى نقيس
    الاستخدام الفعلي (ق-61).
    """
    limit_mb = getattr(account, "storage_limit_mb", None)
    if not limit_mb:
        return

    used = account_usage(account.id)["bytes"]
    if used + incoming_bytes > limit_mb * 1024 * 1024:
        raise UploadError(
            f"بلغت حدّ التخزين ({limit_mb} ميغابايت) — "
            "احذف ملفات قديمة أو راجع الدعم لرفع الحد")


@transaction.atomic
def store(*, uploaded, kind, account, company=None, person=None,
          uploaded_by=None, note=""):
    """
    يرفع ملفًا: يتحقق، ويصغّر إن كان صورة، ويكشف المكرر، ويحفظ.

    يرجع (StoredFile, is_duplicate).
    """
    ext, is_image = validate(uploaded, kind)

    # التصغير قبل حساب البصمة — فالمكرر يُقاس على المحفوظ
    data = None
    if is_image:
        data, ext = shrink_image(uploaded, kind, ext)

    if data is None:
        uploaded.seek(0)
        data = uploaded.read()
        uploaded.seek(0)

    size = len(data)
    checksum = _checksum(data)

    # ق-61: نفس الملف لا يُخزَّن مرتين في الحساب نفسه
    existing = StoredFile.objects.filter(
        account=account, checksum=checksum, kind=kind,
        is_deleted=False).first()
    if existing:
        logger.info("duplicate_file", extra={
            "checksum": checksum[:12], "existing_id": existing.id})
        return existing, True

    _check_quota(account, size)

    original = (uploaded.name or "ملف")[:255]
    obj = StoredFile(
        account=account, kind=kind, company=company, person=person,
        uploaded_by=uploaded_by, note=note[:255],
        original_name=original,
        content_type=getattr(uploaded, "content_type", "")[:100],
        size_bytes=size, checksum=checksum)

    obj.file.save(f"{Path(original).stem[:60]}.{ext}",
                  ContentFile(data), save=False)
    obj.save()

    logger.info("file_stored", extra={
        "kind": kind, "size": size, "account_id": account.id})

    return obj, False


def soft_delete(stored_file, by_person=None):
    """
    حذف منطقي — الملف يبقى والسجل يُعلَّم (ق-61).

    فوثيقة حُذفت بالخطأ تُستعاد، والمراجعة النظامية تجد أثرها.
    """
    stored_file.is_deleted = True
    stored_file.save(update_fields=["is_deleted", "updated_at"])
    logger.info("file_deleted", extra={"file_id": stored_file.id})
    return stored_file
