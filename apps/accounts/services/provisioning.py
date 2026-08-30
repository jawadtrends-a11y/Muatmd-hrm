"""
إنشاء الحسابات — المسار الوحيد المسموح.

ممنوع Account.objects.create() في كود التطبيق: سياسة WITH CHECK
سترفضه، وهذا مقصود. راجع الوثيقة المعمارية (2).
"""
import re
from dataclasses import dataclass

from django.db import connection, transaction

from apps.accounts.models import Account, Company
from apps.core.tenancy.context import account_scope

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")


class ProvisioningError(Exception):
    pass


@dataclass(frozen=True)
class ProvisionedAccount:
    account_id: int
    company_id: int


@transaction.atomic
def provision_account(
    *,
    slug: str,
    display_name_ar: str,
    company_name_ar: str,
    company_code: str = "C1",
    is_sandbox: bool = False,
) -> ProvisionedAccount:
    """ينشئ حسابًا جديدًا وشركته الأولى. يرجع معرّفيهما."""
    slug = (slug or "").strip().lower()
    if not SLUG_RE.match(slug):
        raise ProvisioningError(
            "المعرّف يجب أن يتكوّن من حروف إنجليزية صغيرة وأرقام وشرطات (3–63 خانة)"
        )
    if not display_name_ar.strip() or not company_name_ar.strip():
        raise ProvisioningError("اسم المجموعة واسم الشركة مطلوبان")

    with connection.cursor() as cur:
        cur.execute(
            "SELECT account_id, company_id FROM app_provision_account(%s,%s,%s,%s,%s)",
            [slug, display_name_ar.strip(), company_name_ar.strip(),
             company_code.strip(), is_sandbox],
        )
        account_id, company_id = cur.fetchone()

    # نسخ الأدوار الافتراضية — كل حساب يملك نسخته ويعدّلها بحرية
    from apps.accounts.services.roles import provision_roles_for_account
    with account_scope(account_id):
        provision_roles_for_account(account_id)

    return ProvisionedAccount(account_id=account_id, company_id=company_id)


def get_account_summary(account_id: int) -> dict:
    """يقرأ ملخص الحساب داخل سياقه — للتحقق بعد الإنشاء."""
    with account_scope(account_id):
        acc = Account.objects.get(id=account_id)
        return {
            "id": acc.id,
            "slug": acc.slug,
            "name": acc.display_name_ar,
            "status": acc.status,
            "companies": list(
                Company.objects.filter(account_id=account_id)
                .values_list("legal_name_ar", flat=True)
            ),
        }
