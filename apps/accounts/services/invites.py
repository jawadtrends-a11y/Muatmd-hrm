"""
دعوة الانضمام — المنطق (ق-94).

القواعد:
  · لا دعوة لمن لا معرّف له (بريد · هوية/إقامة/حدود · جوال) —
    فالدعوة تُنشئ حسابًا لا يستطيع صاحبه الدخول إليه.
  · لا دعوة لمن له حساب أصلًا.
  · الرابط يُنسخ دائمًا، والبريد يُرسل إن وُجد — فبيانات كثير من
    الموظفين بلا بريد، ولو علّقنا الدعوة عليه لتعطّلت.
  · إعادة الدعوة تُلغي القديمة وتُنشئ جديدة — فلا رابطان حيّان.
"""
import logging
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models_invite import (
    JoinInvite, InviteStatus, hash_token, make_token)

log = logging.getLogger(__name__)


class InviteError(Exception):
    """خطأ معروف يُعرض للمستخدم كما هو."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def identifiers_of(person):
    """المعرّفات التي يستطيع الدخول بها."""
    return {
        "email": (person.email or "").strip(),
        "id_number": (person.id_number or "").strip(),
        "mobile": (person.mobile_e164 or "").strip(),
    }


def can_invite(person):
    """(هل يجوز، رمز المانع). المانع يُترجَم في طبقة الواجهة."""
    if person.user_id:
        return False, "already_has_account"
    if not any(identifiers_of(person).values()):
        return False, "no_identifier"
    return True, ""


def generate_username():
    """اسم داخليّ لا يراه المستخدم — الدخول بمعرّفاته (ق-94)."""
    from django.contrib.auth.models import User
    for _ in range(10):
        name = f"u-{secrets.token_hex(3)}"
        if not User.objects.filter(username=name).exists():
            return name
    raise InviteError("username_exhausted", "تعذّر توليد اسم مستخدم")


@transaction.atomic
def create_invite(person, *, account_id, company_id,
                  invited_by_person_id=None):
    """ينشئ دعوة ويُرجع (الدعوة، الرمز الخام). الرمز لا يُخزَّن."""
    ok, code = can_invite(person)
    if not ok:
        raise InviteError(code, "لا يمكن دعوة هذا الموظف")

    # إعادة الدعوة تُلغي ما سبق — فلا رابطان حيّان لشخص واحد.
    JoinInvite.objects.filter(
        person_id=person.id, status=InviteStatus.PENDING
    ).update(status=InviteStatus.REVOKED, updated_at=timezone.now())

    raw = make_token()
    invite = JoinInvite.objects.create(
        account_id=account_id,
        company_id=company_id,
        person_id=person.id,
        token_hash=hash_token(raw),
        expires_at=JoinInvite.new_expiry(),
        invited_by_person_id=invited_by_person_id,
    )
    return invite, raw


def invite_url(raw_token):
    base = getattr(settings, "PUBLIC_WEB_URL",
                   "https://hr.muatmd.sa").rstrip("/")
    return f"{base}/join/{raw_token}"


def send_invite_email(invite, person, raw_token, company_name_ar,
                      company_name_en=""):
    """
    يُرسل الدعوة إن كان للموظف بريد. يرجع True إن أُرسلت.

    وبلغتيها معًا: الموظف لم يدخل النظام قطّ فلا لغة مفضّلة له،
    ويختار لغته في صفحة ضبط كلمة المرور.
    """
    from apps.notifications.services.sender import send_email

    email = (person.email or "").strip()
    if not email:
        return False

    url = invite_url(raw_token)
    name = person.display_name
    co_ar = company_name_ar
    co_en = company_name_en or company_name_ar

    subject = f"دعوة للانضمام إلى {co_ar} · Invitation to join"
    text = (
        f"مرحبًا {name}،\n\n"
        f"تمت دعوتك للانضمام إلى نظام الموارد البشرية في {co_ar}.\n"
        f"افتح الرابط لتعيين كلمة مرورك:\n{url}\n\n"
        f"والرابط صالح سبعة أيام.\n\n"
        f"— — —\n\n"
        f"Hello {name},\n\n"
        f"You have been invited to join the HR system at {co_en}.\n"
        f"Open the link to set your password:\n{url}\n\n"
        f"This link is valid for seven days.\n")
    html = f"""
<div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;color:#101C26">
  <p>مرحبًا {name}،</p>
  <p>تمت دعوتك للانضمام إلى نظام الموارد البشرية في <b>{co_ar}</b>.</p>
  <p><a href="{url}" style="background:#0E7C86;color:#fff;padding:11px 22px;
        border-radius:6px;text-decoration:none;display:inline-block">
     تعيين كلمة المرور</a></p>
  <p style="color:#6b7c8c;font-size:13px">والرابط صالح سبعة أيام.</p>
</div>
<hr style="border:none;border-top:1px solid #dde5e9;margin:22px 0">
<div dir="ltr" style="font-family:Arial,sans-serif;color:#101C26">
  <p>Hello {name},</p>
  <p>You have been invited to join the HR system at <b>{co_en}</b>.</p>
  <p><a href="{url}" style="background:#0E7C86;color:#fff;padding:11px 22px;
        border-radius:6px;text-decoration:none;display:inline-block">
     Set your password</a></p>
  <p style="color:#6b7c8c;font-size:13px">This link is valid for seven days.</p>
</div>"""

    sent = send_email(to=email, subject=subject, text=text, html=html,
                      company_id=invite.company_id)
    if sent:
        JoinInvite.objects.filter(id=invite.id).update(
            sent_to_email=email, email_sent_at=timezone.now())
    return sent
