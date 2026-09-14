"""
من له فريق (ق-159).

⚠️ **وسؤال «أله مرؤوسون؟» يسبق البوّابة** — فتمريره بها يجعل
المنطق يدور حول نفسه: البوّابة تسأل عن النطاق، والنطاق يسأل عن
الفريق.
"""


def has_reports(user, company):
    """
    أله مرؤوسون أو إدارةٌ يديرها؟

    ⚠️ **فمجموعة «فريقي» لا تظهر لمن لا فريق له** — وزرٌّ يفتح
    قائمةً فارغة يُربك.
    """
    from apps.employees.models import Employment, EmploymentStatus

    person = getattr(user, "person", None)
    if person is None or company is None:
        return False

    mine = list(Employment.objects.filter(
        person=person, company=company,
        status=EmploymentStatus.ACTIVE).values_list("id", flat=True))
    if not mine:
        return False

    # ⚠️ **ومرؤوسٌ مباشر** — والمباشر قد يكون المشرف لا مدير
    # الإدارة (تصويب جواد).
    if Employment.objects.filter(
            direct_manager_id__in=mine,
            status=EmploymentStatus.ACTIVE).exists():
        return True

    # ⚠️⚠️ **أو مديرُ إدارةٍ فيها موظفون** (قرار جواد): فمن أُسند
    # مديرًا لإدارة **يرى موظفيها** ولو لم يكن مديرهم المباشر —
    # وبلا هذا يُسنَد مديرًا ولا يرى أحدًا.
    from apps.organization.models import Department

    led = list(Department.objects.filter(
        company=company, manager_employment_id__in=mine
    ).values_list("id", flat=True))
    if not led:
        return False

    return Employment.objects.filter(
        department_id__in=led,
        status=EmploymentStatus.ACTIVE).exclude(id__in=mine).exists()




def my_team_queryset(employment):
    """
    فريقُ موظفٍ — **مرؤوسوه وموظفو إدارته**.

    ⚠️⚠️ **ولا يُرشَّح بالنطاق**: فمديرٌ بنطاق شركةٍ يرى الجميع،
    **وشاشة «فريقي» تعني ما تقوله** (تصويب جواد).

    ⚠️ **وهو خارج الفريق**: فلا يُدرج نفسه في قائمة مرؤوسيه.
    """
    from django.db.models import Q

    from apps.employees.models import Employment, EmploymentStatus
    from apps.organization.models import Department

    led = list(Department.objects.filter(
        company_id=employment.company_id,
        manager_employment_id=employment.id).values_list("id",
                                                         flat=True))

    cond = Q(direct_manager_id=employment.id)
    if led:
        cond |= Q(department_id__in=led)

    return (Employment.objects
            .filter(company_id=employment.company_id,
                    status=EmploymentStatus.ACTIVE)
            .filter(cond)
            .exclude(id=employment.id)
            .order_by("employee_no"))


def my_team_queryset(employment):
    """
    فريقُ موظفٍ — **مرؤوسوه وموظفو إدارته**.

    ⚠️⚠️ **ولا يُرشَّح بالنطاق**: فمديرٌ بنطاق شركةٍ يرى الجميع،
    **وشاشة «فريقي» تعني ما تقوله** (تصويب جواد).

    ⚠️ **وهو خارج الفريق**: فلا يُدرج نفسه في قائمة مرؤوسيه.
    """
    from django.db.models import Q

    from apps.employees.models import Employment, EmploymentStatus
    from apps.organization.models import Department

    led = list(Department.objects.filter(
        company_id=employment.company_id,
        manager_employment_id=employment.id).values_list("id",
                                                         flat=True))

    cond = Q(direct_manager_id=employment.id)
    if led:
        cond |= Q(department_id__in=led)

    return (Employment.objects
            .filter(company_id=employment.company_id,
                    status=EmploymentStatus.ACTIVE)
            .filter(cond)
            .exclude(id=employment.id)
            .order_by("employee_no"))


def team_employment_ids(user, company_id):
    """
    أرقام فريق المستخدم — **أو None إن لم يُطلب الترشيح**.

    ⚠️⚠️ **وشاشات «فريقي» تُرشّح بالفريق دائمًا لا بالنطاق**
    (تصويب جواد): فمديرٌ عامّ بنطاق شركةٍ كان يرى الجميع في شاشةٍ
    عنوانها «مرؤوسيك» — **والشاشة تعني ما تقوله**.
    """
    from apps.employees.models import Employment, EmploymentStatus

    person = getattr(user, "person", None)
    if person is None:
        return []

    me = Employment.objects.filter(
        person=person, company_id=company_id,
        status=EmploymentStatus.ACTIVE).first()
    if me is None:
        return []

    return list(my_team_queryset(me).values_list("id", flat=True))
