"""
بنية التقارير القابلة للتصدير (ق-40).

كل تقرير يُنتج بيانات مُهيكلة، وطبقة التصدير تحوّلها إلى Excel
أو PDF. الفصل يعني أن إضافة صيغة جديدة لا تمس أي تقرير.

كل تقرير يعلن:
  • مفتاحه واسمه ومجموعته
  • معاييره (تواريخ، فلاتر) — لبناء الواجهة تلقائيًا
  • صلاحيته المطلوبة
  • أعمدته وصفوفه
"""
from dataclasses import dataclass, field
from decimal import Decimal


class ReportError(Exception):
    pass


@dataclass
class Column:
    key: str
    label_ar: str
    kind: str = "text"        # text · number · money · date · bool
    width: int = 18
    total: bool = False       # يُجمع في سطر الإجمالي


@dataclass
class Param:
    key: str
    label_ar: str
    kind: str                 # date · month · select · bool · text
    required: bool = False
    default: object = None
    options: list = field(default_factory=list)
    help_ar: str = ""


@dataclass
class ReportResult:
    key: str
    title_ar: str
    subtitle_ar: str = ""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    totals: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def row_count(self):
        return len(self.rows)


class Report:
    """
    قاعدة كل تقرير.

    الفئات الفرعية تعرّف: key · title_ar · group · permission ·
    params · columns() · rows()
    """

    key = ""
    title_ar = ""
    group = "other"          # financial · attendance · leaves · employees
    permission = "reports.view"
    params = []

    def __init__(self, company, **kwargs):
        self.company = company
        self.options = kwargs

    # ── يُنفَّذ في الفئات الفرعية ──
    def columns(self):
        raise NotImplementedError

    def rows(self):
        raise NotImplementedError

    def subtitle(self):
        return ""

    def notes(self):
        return []

    def meta(self):
        return {}

    # ── مشترك ──
    def validate(self):
        """يتحقق من المعايير المطلوبة قبل التنفيذ."""
        missing = [p.label_ar for p in self.params
                   if p.required and self.options.get(p.key) in (None, "")]
        if missing:
            raise ReportError(f"معايير مطلوبة: {'، '.join(missing)}")

    def run(self):
        self.validate()
        cols = self.columns()
        rows = self.rows()

        totals = {}
        for c in cols:
            if not c.total:
                continue
            s = Decimal("0")
            for r in rows:
                v = r.get(c.key)
                if v in (None, ""):
                    continue
                try:
                    s += Decimal(str(v))
                except (TypeError, ArithmeticError):
                    continue
            totals[c.key] = f"{s:.2f}"

        return ReportResult(
            key=self.key, title_ar=self.title_ar,
            subtitle_ar=self.subtitle(), columns=cols, rows=rows,
            totals=totals, meta=self.meta(), notes=self.notes())


# ══════════ السجل ══════════

REGISTRY = {}


def register(cls):
    """يسجّل التقرير ليظهر في صفحة التقارير."""
    if not cls.key:
        raise ReportError(f"تقرير بلا مفتاح: {cls.__name__}")
    if cls.key in REGISTRY:
        raise ReportError(f"مفتاح مكرر: {cls.key}")
    REGISTRY[cls.key] = cls
    return cls


def get_report(key):
    cls = REGISTRY.get(key)
    if cls is None:
        raise ReportError(f"تقرير غير معروف: {key}")
    return cls


GROUPS = {
    "financial": "تقارير مالية",
    "attendance": "تقارير الحضور والانصراف",
    "leaves": "تقارير الإجازات",
    "employees": "تقارير الموظفين",
    "other": "أخرى",
}


def catalog():
    """قائمة التقارير مجمّعة — لصفحة التقارير."""
    out = {}
    for key, cls in sorted(REGISTRY.items()):
        out.setdefault(cls.group, []).append({
            "key": key,
            "title_ar": cls.title_ar,
            "permission": cls.permission,
            "params": [
                {"key": p.key, "label_ar": p.label_ar, "kind": p.kind,
                 "required": p.required, "default": p.default,
                 "options": p.options, "help_ar": p.help_ar}
                for p in cls.params
            ],
        })
    return [
        {"group": g, "group_ar": GROUPS.get(g, g), "reports": items}
        for g, items in out.items()
    ]
