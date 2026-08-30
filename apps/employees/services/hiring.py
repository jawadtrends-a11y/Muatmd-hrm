"""
إنشاء الموظف وإدارة هيكل راتبه.

يربط كل ما بُني: كشف التشابه (ق-5)، أعلام التسجيل (ق-15)،
النظام التأميني على الشخص (ق-16)، وهيكل الراتب التاريخي.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction

from apps.employees.models import (
    Employment, EmploymentStatus, Person, SalaryChangeReason, SalaryLine,
    SalaryStructure,
)
from apps.employees.services.duplicates import check_person_duplicates
from apps.employees.services.validators import (
    normalize_mobile, validate_saudi_iban, validate_saudi_id,
)


class HiringError(Exception):
    pass


class DuplicatePersonError(HiringError):
    def __init__(self, blocking):
        self.blocking = blocking
        super().__init__(" | ".join(blocking))


@dataclass
class HireResult:
    person: Person
    employment: Employment
    structure: SalaryStructure | None = None
    warnings: list = field(default_factory=list)


@transaction.atomic
def create_person(*, account, first_name_ar, family_name_ar, gender,
                  nationality_code, id_type, id_number,
                  mobile="", email="", force=False, **extra):
    """
    ينشئ شخصًا. الهوية والجوال والبريد منع صارم، والاسم تحذير (ق-5).

    force=True يتجاوز التحذيرات لا الموانع.
    """
    ok, err = validate_saudi_id(id_number, id_type)
    if not ok:
        raise HiringError(err)

    mobile_e164, mobile_err = normalize_mobile(mobile)
    if mobile_err:
        raise HiringError(mobile_err)

    name = " ".join(filter(None, [
        first_name_ar, extra.get("father_name_ar", ""),
        extra.get("grandfather_name_ar", ""), family_name_ar]))

    check = check_person_duplicates(
        account_id=account.id, id_type=id_type, id_number=id_number,
        name_ar=name, mobile_e164=mobile_e164, email=email)

    if check.blocking:
        raise DuplicatePersonError(check.blocking)
    if check.warnings and not force:
        raise HiringError(
            "تشابه محتمل — راجع التحذيرات ثم أعد المحاولة بـforce:\n"
            + "\n".join(check.warnings))

    person = Person.objects.create(
        account=account, first_name_ar=first_name_ar,
        family_name_ar=family_name_ar, gender=gender,
        nationality_code=nationality_code, id_type=id_type,
        id_number=id_number, mobile_e164=mobile_e164, email=email,
        **{k: v for k, v in extra.items()
           if k in {f.name for f in Person._meta.fields}},
    )
    return person, check.warnings


@transaction.atomic
def create_employment(*, person, company, employee_no, join_date,
                      salary_lines=None, service_start_date=None,
                      probation_days=90, iban="", **extra):
    """
    ينشئ ارتباطًا وظيفيًا مع هيكل راتبه الأول.

    salary_lines: [(component, amount), ...]
    أعلام التسجيل تبدأ False — التوظيف مستقل عن التسجيل (ق-15).
    """
    if person.account_id != company.account_id:
        raise HiringError("الشخص والشركة من حسابين مختلفين")

    if Employment.objects.filter(company=company,
                                 employee_no=employee_no).exists():
        raise HiringError(f"الرقم الوظيفي مستخدم في هذه الشركة: {employee_no}")

    active = Employment.objects.filter(
        company=company, person=person,
        status=EmploymentStatus.ACTIVE).first()
    if active:
        raise HiringError(
            f"للشخص ارتباط نشط بهذه الشركة: {active.employee_no}")

    warnings = []
    if iban:
        ok, err = validate_saudi_iban(iban)
        if not ok:
            raise HiringError(err)

    emp = Employment.objects.create(
        account=company.account, company=company, person=person,
        employee_no=employee_no, join_date=join_date,
        service_start_date=service_start_date or join_date,
        probation_days=probation_days,
        probation_end_date=join_date + timedelta(days=probation_days),
        iban=iban,
        **{k: v for k, v in extra.items()
           if k in {f.name for f in Employment._meta.fields}},
    )

    structure = None
    if salary_lines:
        structure = set_salary_structure(
            employment=emp, lines=salary_lines, effective_from=join_date,
            reason=SalaryChangeReason.HIRING)

    return emp, structure, warnings


@transaction.atomic
def set_salary_structure(*, employment, lines, effective_from,
                         reason=SalaryChangeReason.ADJUSTMENT, note="",
                         approved_by=None):
    """
    ينشئ هيكل راتب جديد. لا تعديل في المكان أبدًا.

    القاعدة الذهبية: كل تغيير سجل جديد بتاريخ سريان — بهذا تُعاد
    احتساب أي مسير قديم بأرقامه الصحيحة.
    """
    if not lines:
        raise HiringError("هيكل الراتب لا يمكن أن يكون فارغًا")

    # إغلاق الهيكل السابق بدل تعديله
    previous = (SalaryStructure.objects
                .filter(employment=employment, effective_to__isnull=True)
                .order_by("-effective_from").first())
    if previous:
        if previous.effective_from >= effective_from:
            raise HiringError(
                f"تاريخ السريان ({effective_from}) يجب أن يلي الهيكل "
                f"السابق ({previous.effective_from})")
        previous.effective_to = effective_from - timedelta(days=1)
        previous.save(update_fields=["effective_to", "updated_at"])

    structure = SalaryStructure.objects.create(
        account=employment.account, company=employment.company,
        employment=employment, effective_from=effective_from,
        reason=reason, note=note)

    SalaryLine.objects.bulk_create([
        SalaryLine(structure=structure, component=comp, amount=Decimal(amount))
        for comp, amount in lines
    ])

    # سجل العمليات (ق-44) — تعديل الراتب أخطر تغيير في النظام
    from apps.core.services.audit import log_action
    log_action(
        instance=structure, action="create", actor=approved_by,
        label=f"{employment.employee_no} — {structure.effective_from}",
        summary=(f"هيكل راتب جديد بإجمالي {structure.gross_monthly} "
                 f"ساري من {structure.effective_from}"),
        changes={
            "lines": {
                "from": (str(previous.gross_monthly) if previous else None),
                "to": str(structure.gross_monthly),
            },
            "reason": {"from": None, "to": reason},
        })
    return structure


def current_salary_structure(employment, as_of: date | None = None):
    """
    هيكل الراتب الساري بتاريخ معيّن — لا بتاريخ اليوم.
    هذا ما يجعل إعادة احتساب مسير قديم تعطي نفس الأرقام.
    """
    day = as_of or date.today()
    return (SalaryStructure.objects
            .filter(employment=employment, effective_from__lte=day)
            .order_by("-effective_from").first())


def gosi_borne_by_company(employment, payroll_settings) -> bool:
    """
    هل تتحمل الشركة حصة هذا الموظف؟ (ق-29)

    الاستثناء على الموظف يسبق إعداد الشركة.
    """
    if employment.gosi_borne_by_company is not None:
        return employment.gosi_borne_by_company
    return payroll_settings.company_bears_employee_gosi
