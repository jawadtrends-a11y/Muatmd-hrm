"""
التخزين الموحّد للملفات (ق-61).

يخدم الصورة الشخصية ووثائق الموظفين ومرفقات الطلبات وشعار
الشركة بنفس البنية — فلا يُبنى حلٌّ خاص لكل حالة.

**العزل في المسار:** {account_id}/{kind}/{uuid}.{ext}
فحتى لو تسرّب رابط، لا يكشف ملفات حساب آخر بالتخمين.

**والحدود متحفّظة عمدًا:** عشرة آلاف موظف بست وثائق يعني ستين
ألف ملف — والفرق بين حدّ 2 ميغا وحدّ 10 يقرر ما إذا كان النظام
يعمل أصلًا.
"""
import hashlib
import uuid
from pathlib import Path as _Path

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AccountScopedModel


class FileKind(models.TextChoices):
    AVATAR = "avatar", _("صورة شخصية")
    LOGO = "logo", _("شعار الشركة")
    DOCUMENT = "document", _("وثيقة موظف")
    CONTRACT = "contract", _("عقد")
    ATTACHMENT = "attachment", _("مرفق طلب")
    OTHER = "other", _("أخرى")


# (الامتدادات المسموحة، الحد بالكيلوبايت، أقصى بُعد بالبكسل)
KIND_RULES = {
    FileKind.AVATAR: ({"jpg", "jpeg", "png", "webp"}, 500, 256),
    FileKind.LOGO: ({"jpg", "jpeg", "png", "webp"}, 300, 512),
    FileKind.DOCUMENT: ({"pdf", "jpg", "jpeg", "png"}, 2048, 1600),
    FileKind.CONTRACT: ({"pdf"}, 3072, None),
    FileKind.ATTACHMENT: ({"pdf", "jpg", "jpeg", "png", "webp"}, 2048, 1600),
    FileKind.OTHER: ({"pdf", "jpg", "jpeg", "png", "xlsx", "docx"}, 2048, 1600),
}

# تُرفض دائمًا مهما كان النوع — تنفيذية أو قابلة للتفسير
BLOCKED_EXTENSIONS = {
    "exe", "bat", "cmd", "com", "scr", "msi", "dll", "so",
    "sh", "bash", "ps1", "vbs", "js", "jar", "app", "deb", "rpm",
    "php", "py", "rb", "pl", "asp", "aspx", "jsp", "cgi",
    "htaccess", "htm", "html", "svg",
}


def _upload_to(instance, filename):
    ext = _Path(filename).suffix.lower().lstrip(".")[:8]
    return f"{instance.account_id}/{instance.kind}/{uuid.uuid4().hex}.{ext}"


class StoredFile(AccountScopedModel):
    """
    ملف محفوظ.

    الحذف منطقي لا فعلي: الملف يبقى والسجل يُعلَّم محذوفًا — فوثيقة
    حُذفت بالخطأ تُستعاد، والمراجعة النظامية تجد أثرها.
    """

    kind = models.CharField(_("النوع"), max_length=20,
                            choices=FileKind.choices, db_index=True)
    file = models.FileField(_("الملف"), upload_to=_upload_to, max_length=400)

    original_name = models.CharField(_("الاسم الأصلي"), max_length=255)
    content_type = models.CharField(_("نوع المحتوى"), max_length=100,
                                    blank=True)
    size_bytes = models.BigIntegerField(_("الحجم"), default=0)
    checksum = models.CharField(_("البصمة"), max_length=64, blank=True,
                                db_index=True)

    company = models.ForeignKey(
        "accounts.Company", on_delete=models.CASCADE, null=True, blank=True,
        related_name="stored_files", verbose_name=_("الشركة"))
    person = models.ForeignKey(
        "employees.Person", on_delete=models.CASCADE, null=True, blank=True,
        related_name="files", verbose_name=_("الشخص"))
    uploaded_by = models.ForeignKey(
        "employees.Person", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="uploaded_files", verbose_name=_("رفعه"))

    is_deleted = models.BooleanField(_("محذوف"), default=False, db_index=True)
    note = models.CharField(_("ملاحظة"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("ملف")
        verbose_name_plural = _("الملفات")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account", "kind", "is_deleted"]),
            models.Index(fields=["person", "kind"]),
            models.Index(fields=["account", "checksum"]),
        ]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.original_name}"

    @property
    def size_label(self):
        kb = self.size_bytes / 1024
        return f"{kb:.0f} KB" if kb < 1024 else f"{kb / 1024:.1f} MB"
