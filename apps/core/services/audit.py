"""
خدمة سجل عمليات المنشأة (ق-44).

القاعدة: التسجيل لا يوقف العملية. فشله يُبتلع لأن فقدان قيد
تدقيق أهون من فشل اعتماد مسير.
"""
import logging
from decimal import Decimal

from apps.core.models_audit import AuditAction, AuditEntry

logger = logging.getLogger("muatmd.audit")

SKIP_FIELDS = {
    "id", "created_at", "updated_at", "account", "account_id",
    "password", "last_login",
}

OBJECT_TYPES = {
    "Employment": "employment",
    "Person": "person",
    "SalaryStructure": "salary_structure",
    "PayrollRun": "payroll_run",
    "Payslip": "payslip",
    "Advance": "advance",
    "Asset": "asset",
    "EmployeeDocument": "document",
    "Request": "request",
    "LeaveBalance": "leave_balance",
    "PayComponent": "pay_component",
    "PayrollSettings": "payroll_settings",
    "Role": "role",
    "RoleAssignment": "role_assignment",
    "Branch": "branch",
    "Department": "department",
    "Shift": "shift",
    "AttendanceDay": "attendance_day",
    "LeaveType": "leave_type",
    "ApprovalChain": "approval_chain",
    "BankTemplate": "bank_template",
}


def object_type_of(instance):
    name = instance.__class__.__name__
    return OBJECT_TYPES.get(name, name.lower())


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (int, float, bool, str)):
        return value
    return str(value)


def snapshot(instance, fields=None):
    """يلتقط قيم السجل قبل التعديل — يُستدعى قبل الحفظ."""
    data = {}
    for f in instance._meta.fields:
        if f.name in SKIP_FIELDS:
            continue
        if fields is not None and f.name not in fields:
            continue
        data[f.name] = _serialize(getattr(instance, f.attname, None))
    return data


def _diff(before, after):
    changes = {}
    for key, old in (before or {}).items():
        new = after.get(key)
        if old != new:
            changes[key] = {"from": old, "to": new}
    for key, new in after.items():
        if key not in (before or {}):
            changes[key] = {"from": None, "to": new}
    return changes


def _actor_bits(actor):
    if actor is None:
        return None, "النظام", None
    if hasattr(actor, "display_name"):
        return actor, actor.display_name, getattr(actor, "user_id", None)
    if hasattr(actor, "username"):
        person = getattr(actor, "person", None)
        name = (person.display_name if person
                else (actor.get_full_name() or actor.username))
        return person, name, actor.id
    return None, str(actor), None


def _write(*, account_id, company_id, object_type, object_id, object_label,
           action, changes, summary, actor, channel, ip):
    person, actor_name, user_id = _actor_bits(actor)

    # المفتاح الأجنبي مؤجَّل الفحص (DEFERRABLE)، فالإدراج بحساب
    # غير موجود يمر ثم يُسقط المعاملة كلها عند الالتزام — وقيد
    # تدقيق فاسد يجب ألا يُفشل اعتماد مسير (ق-44).
    from apps.accounts.models import Account
    if not Account.objects.filter(id=account_id).exists():
        logger.warning("audit_skipped_unknown_account: %s", account_id)
        return None

    try:
        return AuditEntry.objects.create(
            account_id=account_id, company_id=company_id,
            object_type=object_type, object_id=object_id,
            object_label=(object_label or "")[:200],
            action=action, changes=changes or {},
            summary_ar=(summary or "")[:300],
            actor_person=person, actor_name=actor_name[:200],
            actor_user_id=user_id, channel=channel, ip_address=ip)
    except Exception as e:  # noqa: BLE001
        logger.warning("audit_write_failed: %s", e, extra={
            "object_type": object_type, "object_id": object_id})
        return None


def log_change(*, instance, before, actor=None, label="", summary="",
               channel="web", ip=None, fields=None):
    """يسجّل تعديلًا. لا يُسجَّل شيء إن لم يتغيّر شيء."""
    after = snapshot(instance, fields=fields)
    changes = _diff(before, after)
    if not changes:
        return None
    return _write(
        account_id=instance.account_id,
        company_id=getattr(instance, "company_id", None),
        object_type=object_type_of(instance), object_id=instance.pk,
        object_label=label or str(instance),
        action=AuditAction.UPDATE, changes=changes,
        summary=summary or f"تعديل {len(changes)} حقل",
        actor=actor, channel=channel, ip=ip)


def log_action(*, instance, action, actor=None, label="", summary="",
               changes=None, channel="web", ip=None):
    """يسجّل عملية بلا مقارنة — إنشاء، اعتماد، تصدير."""
    return _write(
        account_id=instance.account_id,
        company_id=getattr(instance, "company_id", None),
        object_type=object_type_of(instance), object_id=instance.pk,
        object_label=label or str(instance),
        action=action, changes=changes or {}, summary=summary,
        actor=actor, channel=channel, ip=ip)


def log_create(*, instance, actor=None, label="", summary="",
               channel="web", ip=None):
    return log_action(instance=instance, action=AuditAction.CREATE,
                      actor=actor, label=label,
                      summary=summary or "إنشاء سجل جديد",
                      channel=channel, ip=ip)


def log_delete(*, instance, actor=None, label="", summary="",
               channel="web", ip=None):
    """يسجّل الحذف قبل تنفيذه — الوصف يبقى بعد اختفاء السجل."""
    return _write(
        account_id=instance.account_id,
        company_id=getattr(instance, "company_id", None),
        object_type=object_type_of(instance), object_id=instance.pk,
        object_label=label or str(instance),
        action=AuditAction.DELETE, changes=snapshot(instance),
        summary=summary or "حذف سجل",
        actor=actor, channel=channel, ip=ip)


def history_for(instance, limit=50):
    """سجل تعديلات سجل معيّن — يُعرض أسفل شاشته (ق-44)."""
    return AuditEntry.objects.filter(
        object_type=object_type_of(instance),
        object_id=instance.pk,
    ).select_related("actor_person")[:limit]


def serialize_entry(entry, field_labels=None):
    labels = field_labels or {}
    return {
        "id": entry.id,
        "action": entry.action,
        "action_label": entry.get_action_display(),
        "actor": entry.actor_name,
        "at": entry.created_at,
        "channel": entry.get_channel_display(),
        "summary": entry.summary_ar,
        "changes": [
            {"field": k, "field_label": labels.get(k, k),
             "from": v.get("from"), "to": v.get("to")}
            for k, v in (entry.changes or {}).items()
        ],
    }
