"""
محدِّد المعتمِدين — الواجهة الوحيدة التي تسألها الموديولات.

قرار مؤجَّل بوعي: محرك سلسلة الاعتماد يُبنى في السبرنت 6 مع الطلبات
والإجازات، حيث نرى الاستخدام الفعلي بدل التصميم في الفراغ.

القاعدة الحاكمة حتى ذلك الحين:
    ممنوع على أي موديول أن يفحص صلاحية الاعتماد مباشرة.
    كل اعتماد يمر من هنا. هذا ما يجعل إضافة السلسلة لاحقًا
    تغييرًا في ملف واحد لا إعادة كتابة للموديولات.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Approver:
    membership_id: int
    step_order: int = 1
    is_mandatory: bool = True


def resolve_approvers(*, request_type: str, permission_key: str,
                      account_id: int, company_id: int | None = None,
                      requester_membership_id: int | None = None) -> list[Approver]:
    """
    يرجع المعتمِدين بالترتيب.

    التنفيذ الحالي (مؤقت): درجة واحدة — كل من يملك الصلاحية في نطاقه.
    التنفيذ القادم (السبرنت 6): يقرأ من approval_chains بدرجات
    قابلة للضبط لكل شركة، مع سلسلة افتراضية جاهزة تعدّلها.

    توقيع الدالة لن يتغيّر — لذلك الموديولات لن تتأثر.
    """
    from apps.accounts.models_access import AccountMembership

    qs = AccountMembership.objects.filter(
        account_id=account_id,
        role_assignments__role__permissions__permission_key=permission_key,
    ).distinct()
    if requester_membership_id:
        qs = qs.exclude(id=requester_membership_id)   # لا يعتمد طلبه بنفسه

    return [Approver(membership_id=m.id) for m in qs]


def is_approval_engine_ready() -> bool:
    """يصير True عند بناء المحرك — تستخدمه الاختبارات للتمييز."""
    return False
