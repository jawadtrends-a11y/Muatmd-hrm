"""
كشف التشابه عند إضافة شخص (ق-5).

القاعدة: رقم الهوية منع صارم، والاسم تحذير لا منع.
«محمد أحمد السالم» قد يكون شخصين حقيقيين في نفس الشركة، ورفض
تسجيل الثاني خطأ وظيفي يصطدم بك عند أول عميل كبير.
"""
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from apps.employees.models import Person

NAME_SIMILARITY_THRESHOLD = 0.90


@dataclass(frozen=True)
class DuplicateCheck:
    blocking: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def can_proceed(self):
        return not self.blocking


def check_person_duplicates(*, account_id, id_type, id_number,
                            name_ar, mobile_e164="", email="",
                            exclude_person_id=None):
    """
    يفحص التشابه قبل الإضافة.

    blocking: يمنع الحفظ (هوية أو جوال مكرر)
    warnings: يُعرض للمستخدم مع خيار المتابعة الواعية (اسم مشابه)
    """
    blocking, warnings = [], []
    qs = Person.objects.filter(account_id=account_id)
    if exclude_person_id:
        qs = qs.exclude(id=exclude_person_id)

    # ── منع صارم: رقم الهوية ──
    existing = qs.filter(id_type=id_type, id_number=id_number).first()
    if existing:
        blocking.append(
            f"يوجد شخص مسجّل بنفس رقم الهوية: {existing.display_name}")

    # ── منع صارم: الجوال (مفتاح واتساب) ──
    if mobile_e164:
        dup_mobile = qs.filter(mobile_e164=mobile_e164).first()
        if dup_mobile:
            blocking.append(
                f"رقم الجوال مسجّل لشخص آخر: {dup_mobile.display_name}. "
                "الجوال مفتاح التعريف في واتساب — رقمان متطابقان يعنيان "
                "وصول الرسائل للشخص الخطأ.")

    # ── منع صارم: البريد ──
    if email:
        dup_email = qs.filter(email__iexact=email).first()
        if dup_email:
            blocking.append(
                f"البريد مسجّل لشخص آخر: {dup_email.display_name}")

    # ── تحذير: تشابه الاسم ──
    for cand in qs.filter(
            family_name_ar__icontains=name_ar.split()[-1]
            if name_ar.split() else "")[:20]:
        ratio = SequenceMatcher(None, name_ar, cand.display_name).ratio()
        if ratio >= NAME_SIMILARITY_THRESHOLD:
            companies = ", ".join(
                e.company.legal_name_ar
                for e in cand.employments.select_related("company")[:3]
            ) or "بلا ارتباط وظيفي"
            warnings.append(
                f"اسم مشابه: {cand.display_name} — هوية {cand.masked_id} "
                f"({companies}). تأكد أنه شخص مختلف.")

    return DuplicateCheck(blocking=blocking, warnings=warnings)
