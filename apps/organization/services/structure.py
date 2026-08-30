"""
خدمة الهيكل التنظيمي.

أول موضع تُفرض فيه حدود الباقة عمليًا: max_branches. الحد صفر
يعني بلا حد (الباقة المؤسسية).
"""
from django.db import transaction

from apps.core.features.gate import Features
from apps.organization.models import Branch, CostCenter, Department, Holiday, JobTitle


class StructureError(Exception):
    pass


class LimitExceeded(StructureError):
    """تجاوز حد الباقة — رسالة ترقية لا رفض صلاحية."""

    def __init__(self, feature_key, limit, current):
        self.feature_key, self.limit, self.current = feature_key, limit, current
        super().__init__(
            f"بلغت الحد الأقصى ({limit}) لباقتكم الحالية. "
            f"الترقية تتيح المزيد."
        )


def _check_limit(company, feature_key, model):
    """0 = بلا حد. غير ذلك يُفحص قبل الإنشاء."""
    limit = Features.limit(company.id, feature_key, default=0)
    if limit == 0:
        return
    current = model.objects.filter(company=company, is_active=True).count()
    if current >= limit:
        raise LimitExceeded(feature_key, limit, current)


@transaction.atomic
def create_branch(*, company, code, name_ar, **extra):
    _check_limit(company, "max_branches", Branch)
    if Branch.objects.filter(company=company, code=code).exists():
        raise StructureError(f"رمز الفرع مستخدم بالفعل: {code}")
    return Branch.objects.create(
        account=company.account, company=company,
        code=code, name_ar=name_ar, **extra,
    )


@transaction.atomic
def create_department(*, company, code, name_ar, parent=None, branch=None, **extra):
    """
    ينشئ قسمًا. المسار والعمق يُحتسبان تلقائيًا في save().
    """
    if Department.objects.filter(company=company, code=code).exists():
        raise StructureError(f"رمز القسم مستخدم بالفعل: {code}")
    if parent and parent.company_id != company.id:
        raise StructureError("القسم الأعلى يتبع شركة أخرى")
    return Department.objects.create(
        account=company.account, company=company,
        code=code, name_ar=name_ar, parent=parent, branch=branch, **extra,
    )


@transaction.atomic
def move_department(*, department, new_parent):
    """
    ينقل قسمًا في الشجرة ويُحدّث مسارات كل الأقسام تحته.

    يمنع الحلقة: لا يُنقل قسم ليصير تحت أحد أبنائه.
    """
    if new_parent is not None:
        if new_parent.company_id != department.company_id:
            raise StructureError("لا يمكن النقل بين شركتين")
        if new_parent.id == department.id:
            raise StructureError("لا يمكن جعل القسم أبًا لنفسه")
        if new_parent.path.startswith(f"{department.path}/") or \
           new_parent.path == department.path:
            raise StructureError("لا يمكن نقل قسم ليصير تحت أحد أبنائه")

    old_path = department.path
    department.parent = new_parent
    department.save()

    # تحديث مسارات الأبناء — استعلام واحد لكل مستوى
    for child in Department.objects.filter(
        company_id=department.company_id, path__startswith=f"{old_path}/"
    ).order_by("depth"):
        child.save()   # save() يعيد احتساب المسار من الأب

    return department


def department_tree(company):
    """شجرة الأقسام مرتّبة — استعلام واحد."""
    nodes = list(Department.objects.filter(company=company, is_active=True)
                 .order_by("path"))
    by_id = {n.id: {"id": n.id, "code": n.code, "name_ar": n.name_ar,
                    "depth": n.depth, "children": []} for n in nodes}
    roots = []
    for n in nodes:
        item = by_id[n.id]
        if n.parent_id and n.parent_id in by_id:
            by_id[n.parent_id]["children"].append(item)
        else:
            roots.append(item)
    return roots


@transaction.atomic
def create_holiday(*, company, name_ar, start_date, end_date,
                   branch=None, is_paid=True, **extra):
    """
    عطلة تديرها الشركة بالكامل — لا تدخّل من المنصة.
    """
    if end_date < start_date:
        raise StructureError("تاريخ النهاية قبل تاريخ البداية")

    overlap = Holiday.objects.filter(
        company=company, branch=branch,
        start_date__lte=end_date, end_date__gte=start_date,
    ).first()
    if overlap:
        raise StructureError(
            f"تتداخل مع عطلة قائمة: {overlap.name_ar} "
            f"({overlap.start_date} — {overlap.end_date})"
        )

    return Holiday.objects.create(
        account=company.account, company=company, branch=branch,
        name_ar=name_ar, start_date=start_date, end_date=end_date,
        is_paid=is_paid, **extra,
    )


def holidays_in_range(company, start, end, branch=None):
    """
    عطل الفترة — تشمل عطل الشركة كاملة وعطل الفرع المحدد.
    يستخدمها محرك الحضور والرواتب لاحقًا.
    """
    from django.db.models import Q
    q = Q(company=company, start_date__lte=end, end_date__gte=start)
    if branch is not None:
        q &= (Q(branch__isnull=True) | Q(branch=branch))
    else:
        q &= Q(branch__isnull=True)
    return Holiday.objects.filter(q).order_by("start_date")
