"""
سجل التدقيق للتسويات اليدوية.

كل تسوية على رصيد إجازة تُسجَّل: من ولماذا ومتى وكم. سجل لا يُعدَّل
ولا يُحذف — يُسأل عنه في أي نزاع.
"""
import logging

logger = logging.getLogger("muatmd.audit")


def record_adjustment(*, employment, leave_type, amount, reason, person,
                      year):
    """
    يسجّل التسوية.

    التنفيذ الحالي: سجل تطبيق مُهيكل. يُنقل لجدول تدقيق مخصص عند
    بناء لوحة التدقيق (السبرنت 16).
    """
    logger.info(
        "leave_adjustment",
        extra={
            "account_id": employment.account_id,
            "company_id": employment.company_id,
            "employment_id": employment.id,
            "employee_no": employment.employee_no,
            "leave_type": leave_type.code,
            "amount": str(amount),
            "year": year,
            "reason": reason,
            "by_person_id": getattr(person, "id", None),
        },
    )
