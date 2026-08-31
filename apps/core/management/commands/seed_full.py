"""
بذرة تجريبية كاملة — خمس شركات بخمسين موظفًا.

الغرض: تجربة كل ميزة بأرقام واقعية قبل أي عميل حقيقي.

    ./seed.sh --full        بناء كامل
    ./seed.sh --full --reset  مسح ثم بناء

⚠️ بيانات وهمية للتطوير — لا تُشغَّل على قاعدة إنتاج.
"""
import random
from datetime import date, timedelta
from decimal import Decimal as D

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

SEED = 20260831
random.seed(SEED)

# ══════════ الشركات ══════════

GROUPS = [
    {
        "slug": "muatmd-group",
        "name": "مجموعة معتمد القابضة",
        "companies": [
            ("C1", "شركة معتمد للمقاولات", "1010111222", "الرياض"),
            ("C2", "شركة معتمد للتجارة", "1010333444", "جدة"),
            ("C3", "شركة معتمد للخدمات اللوجستية", "1010555666", "الدمام"),
        ],
    },
    {
        "slug": "alofuq",
        "name": "شركة الأفق للاستشارات",
        "companies": [("C1", "شركة الأفق للاستشارات", "1010777888", "الرياض")],
    },
    {
        "slug": "alruwwad",
        "name": "مصنع الرواد الصناعي",
        "companies": [("C1", "مصنع الرواد الصناعي", "1010999000", "ينبع")],
    },
]

# ══════════ الأسماء ══════════

MALE_FIRST = [
    "محمد", "أحمد", "عبدالله", "خالد", "سعد", "فهد", "بندر", "ماجد",
    "طلال", "نايف", "سلطان", "عبدالعزيز", "راشد", "يوسف", "إبراهيم",
    "عمر", "زياد", "وليد", "هشام", "مشعل",
]
FEMALE_FIRST = [
    "نورة", "سارة", "منى", "هند", "ريم", "لطيفة", "أمل", "دانة",
    "شهد", "الجوهرة",
]
FAMILY = [
    "القحطاني", "العتيبي", "الشمري", "الحربي", "الغامدي", "الزهراني",
    "الدوسري", "المطيري", "السبيعي", "البقمي", "الشهري", "العنزي",
    "الرشيدي", "الخالدي", "المالكي", "الأحمدي", "الجهني", "البلوي",
]
EXPAT_NAMES = [
    ("راجيش", "كومار", "IN"), ("محمد", "رفيق", "PK"),
    ("أنور", "حسين", "BD"), ("جوزيف", "سانتوس", "PH"),
    ("أحمد", "عبدالرحمن", "EG"), ("خالد", "منصور", "SD"),
    ("سامي", "حداد", "SY"), ("عمر", "الأمين", "YE"),
]

# ══════════ الأقسام والمسميات ══════════

DEPARTMENTS = {
    "مقاولات": ["الإدارة العليا", "الموارد البشرية", "المالية",
                "المشاريع", "السلامة", "المشتريات"],
    "تجارة": ["الإدارة العليا", "الموارد البشرية", "المالية",
              "المبيعات", "المستودعات", "خدمة العملاء"],
    "خدمات": ["الإدارة العليا", "الموارد البشرية", "المالية",
              "العمليات", "النقل", "الصيانة"],
    "استشارات": ["الإدارة العليا", "الموارد البشرية", "المالية",
                 "الاستشارات", "تطوير الأعمال"],
    "صناعة": ["الإدارة العليا", "الموارد البشرية", "المالية",
              "الإنتاج", "الجودة", "الصيانة"],
}

JOB_TITLES = [
    "مدير عام", "مدير إدارة", "مشرف", "أخصائي أول", "أخصائي",
    "محاسب", "فني", "منسق", "موظف إداري", "سائق",
]

# ══════════ الهرم الوظيفي لكل شركة ══════════
# (المسمى، الدور، النطاق، الراتب الأساسي، بدل سكن، بدل نقل)

HIERARCHY = [
    ("مدير عام",        "owner",        "account", 35000, 8750, 2000),
    ("مدير إدارة",      "dept_manager", "company", 22000, 5500, 1500),
    ("مدير الموارد",    "hr_manager",   "company", 18000, 4500, 1200),
    ("أخصائي موارد",    "hr_staff",     "company",  9000, 2250,  800),
    ("مشرف",            "supervisor",   "team",    12000, 3000,  900),
    ("مشرف",            "supervisor",   "team",    11000, 2750,  900),
    ("محاسب",           "employee",     "own",      8500, 2125,  700),
    ("أخصائي",          "employee",     "own",      7500, 1875,  700),
    ("فني",             "employee",     "own",      5500, 1375,  600),
    ("موظف إداري",      "employee",     "own",      4500, 1125,  500),
]


# ══════════════════ الأدوات ══════════════════


def _saudi_id(i):
    """رقم هوية سعودي يبدأ بـ1."""
    return f"1{random.randint(100000000, 999999999)}"[:10]


def _iqama(i):
    """رقم إقامة يبدأ بـ2."""
    return f"2{random.randint(100000000, 999999999)}"[:10]


def _mobile():
    return f"05{random.randint(10000000, 99999999)}"


def _iban(bank="80"):
    """
    آيبان سعودي صحيح بمعيار ISO 13616.

    رقم المراقبة يُحسب بـmod-97 لا يُخمَّن — النظام يتحقق منه
    (وهو تحقق صحيح: آيبان خاطئ يعني راتبًا لا يصل).
    """
    account = "".join(str(random.randint(0, 9)) for _ in range(18))
    body = f"{bank}{account}"

    # SA = S(28) A(10)، ورقما المراقبة صفران عند الحساب
    rearranged = f"{body}2810" + "00"
    check = 98 - (int(rearranged) % 97)
    return f"SA{check:02d}{body}"


class Command(BaseCommand):
    help = "بذرة تجريبية كاملة — خمس شركات بخمسين موظفًا"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="امسح كل البيانات أولًا")

    def handle(self, *args, **opts):
        if opts.get("reset"):
            self._reset()

        self.stdout.write("")
        self.stdout.write("═══ بذرة معتمد HRM الكاملة ═══")
        self.stdout.write("")

        self._seed_platform()

        accounts = []
        for group in GROUPS:
            acc = self._seed_account(group)
            accounts.append(acc)

        self._summary(accounts)

    # ── المسح ──
    def _reset(self):
        from django.db import connection
        self.stdout.write("مسح البيانات…")
        with connection.cursor() as cur:
            cur.execute("""
                DO $$
                DECLARE r RECORD;
                BEGIN
                  FOR r IN (
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tablename NOT LIKE 'django_%'
                      AND tablename NOT LIKE 'auth_%'
                  ) LOOP
                    EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename)
                            || ' RESTART IDENTITY CASCADE';
                  END LOOP;
                END $$;
            """)
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.SUCCESS("  ✓ مُسحت"))

    # ── طبقة المنصة ──
    def _seed_platform(self):
        from apps.accounts.models_platform import get_settings
        from apps.accounts.services.plans import sync_default_plans
        from apps.payroll.services.gosi_seed import sync_gosi_rates

        sync_gosi_rates()
        sync_default_plans()

        ps = get_settings()
        ps.vat_rate = D("15")
        ps.support_email = "support@muatmd.sa"
        ps.support_mobile = "0500000000"
        ps.save()

        self._seed_platform_users()
        self._seed_discounts()
        self.stdout.write("  ✓ طبقة المنصة")

    def _seed_platform_users(self):
        from apps.accounts.models_admin import PlatformRole, PlatformUser
        from apps.accounts.services.platform.auth import create_platform_user

        users = [
            ("admin", "admin@muatmd.sa", "جواد — مالك المنصة",
             PlatformRole.OWNER),
            ("support", "support@muatmd.sa", "فريق الدعم",
             PlatformRole.SUPPORT),
            ("viewer", "viewer@muatmd.sa", "مطّلع",
             PlatformRole.VIEWER),
        ]
        for username, email, name, role in users:
            if PlatformUser.objects.filter(username=username).exists():
                continue
            create_platform_user(username=username, email=email,
                                 full_name=name, password="Admin@2026",
                                 role=role)

    def _seed_discounts(self):
        from apps.accounts.models_billing_v2 import (
            Discount, DiscountKind, DiscountScope,
        )
        rows = [
            ("WELCOME20", "خصم ترحيبي", DiscountScope.COUPON,
             DiscountKind.PERCENT, D("20"), 100),
            ("ANNUAL15", "خصم الاشتراك السنوي", DiscountScope.COUPON,
             DiscountKind.PERCENT, D("15"), None),
            ("LOYAL10", "عميل مميز", DiscountScope.RECURRING,
             DiscountKind.PERCENT, D("10"), None),
        ]
        for code, name, scope, kind, value, max_uses in rows:
            Discount.objects.get_or_create(code=code, defaults={
                "name_ar": name, "scope": scope, "kind": kind,
                "value": value, "max_uses": max_uses,
            })

    # ══════════ الحساب والشركات ══════════

    def _seed_account(self, group):
        from apps.accounts.models import Account, Company
        from apps.accounts.services.provisioning import provision_account
        from apps.core.tenancy.context import account_scope

        first = group["companies"][0]
        res = provision_account(
            slug=group["slug"], display_name_ar=group["name"],
            company_name_ar=first[1], is_sandbox=True)

        with account_scope(res.account_id):
            acc = Account.objects.get(id=res.account_id)
            comp1 = Company.objects.get(id=res.company_id)
            comp1.code = first[0]
            comp1.cr_number = first[2]
            comp1.save()

            companies = [comp1]
            for code, name, cr, city in group["companies"][1:]:
                companies.append(self._add_company(acc, code, name, cr))

            self._seed_subscription(acc, group["slug"])

            for i, comp in enumerate(companies):
                city = group["companies"][i][3]
                self._seed_company(acc, comp, city)

            self.stdout.write(
                f"  ✓ {group['name']} — {len(companies)} شركة")

        return {"account": acc, "slug": group["slug"],
                "companies": companies}

    def _add_company(self, account, code, name, cr):
        """
        شركة إضافية بنفس بذور الشركة الأولى.

        provision_account يبذر الشركة الأولى وحدها — فنكرر
        الخطوات هنا: مكوّنات الأجر والإعدادات والإجازات والبنوك.
        """
        from apps.accounts.models import Company
        from apps.leaves.services.seeds import (
            provision_approval_chains, provision_leave_types,
        )
        from apps.payroll.models import PayrollSettings
        from apps.payroll.services.components import (
            provision_default_components,
        )
        from apps.payroll.services.outputs.templates_seed import (
            provision_bank_templates,
        )

        comp = Company.objects.create(
            account=account, code=code, legal_name_ar=name,
            cr_number=cr)

        provision_default_components(comp)
        PayrollSettings.objects.get_or_create(
            company=comp, defaults={"account_id": account.id})
        provision_leave_types(comp)
        provision_approval_chains(comp)
        provision_bank_templates(comp)

        return comp

    def _seed_subscription(self, account, slug):
        """حالات اشتراك متنوعة — لترى كل شريط تنبيه."""
        from apps.accounts.models import Plan
        from apps.accounts.models_billing_v2 import (
            BillingCycle, SubscriptionState,
        )
        from apps.accounts.services.billing_v2 import (
            activate_manually, start_trial,
        )

        sub = start_trial(account)

        if slug == "muatmd-group":
            plan = Plan.objects.filter(code="enterprise").first()
            activate_manually(
                subscription=sub, plan=plan, cycle=BillingCycle.ANNUAL,
                period_start=date.today() - timedelta(days=60),
                activated_by=None, note="تحويل بنكي TR-2026-001",
                setup_fee=D("5000"))
        elif slug == "alofuq":
            plan = Plan.objects.filter(code="premium").first()
            activate_manually(
                subscription=sub, plan=plan, cycle=BillingCycle.MONTHLY,
                period_start=date.today() - timedelta(days=27),
                activated_by=None, note="اشتراك شهري")
        # alruwwad يبقى على التجربة المجانية

    # ══════════ الشركة الواحدة ══════════

    def _seed_company(self, account, company, city):
        branches = self._seed_branches(account, company, city)
        depts = self._seed_departments(account, company)
        emps = self._seed_employees(account, company, branches, depts)

        days = self._seed_attendance(account, company, emps)
        leaves = self._seed_leaves(account, company, emps)
        runs = self._seed_payroll(company)

        self.stdout.write(
            f"      {company.legal_name_ar}: {len(emps)} موظف · "
            f"{days} يوم حضور · {leaves} إجازة · {runs} مسير")

    def _seed_branches(self, account, company, city):
        from apps.organization.models import Branch
        rows = [
            ("BR1", f"الفرع الرئيسي — {city}"),
            ("BR2", f"فرع {city} الصناعي"),
        ]
        out = []
        for code, name in rows:
            b, _ = Branch.objects.get_or_create(
                account=account, company=company, code=code,
                defaults={"name_ar": name, "city": city})
            out.append(b)
        return out

    def _seed_departments(self, account, company):
        from apps.organization.models import Department

        kind = "مقاولات"
        for k in DEPARTMENTS:
            if k in company.legal_name_ar:
                kind = k
                break

        out = []
        parent = None
        for i, name in enumerate(DEPARTMENTS[kind]):
            d, _ = Department.objects.get_or_create(
                account=account, company=company, code=f"D{i+1}",
                defaults={"name_ar": name, "parent": parent})
            if i == 0:
                parent = d
            out.append(d)
        return out

    # ══════════ الموظفون ══════════

    def _seed_employees(self, account, company, branches, depts):
        from apps.employees.models import EmploymentStatus
        from apps.employees.services.hiring import (
            create_employment, create_person,
        )
        from apps.payroll.models import PayComponent

        comps = {c.code: c for c in PayComponent.objects.filter(
            company=company)}

        used_ids = set()
        employments = []

        for idx, (title, role, scope, basic, housing, transport) in enumerate(
                HIERARCHY):
            is_expat = idx in (8, 9)      # آخر اثنين وافدان

            if is_expat:
                first, family, nat = EXPAT_NAMES[
                    (idx + hash(company.code)) % len(EXPAT_NAMES)]
                id_type, id_number = "iqama", _iqama(idx)
                gender = "male"
            else:
                nat = "SA"
                gender = "female" if idx in (3, 7) else "male"
                pool = FEMALE_FIRST if gender == "female" else MALE_FIRST
                first = pool[(idx * 3 + hash(company.code)) % len(pool)]
                family = FAMILY[(idx * 5 + hash(company.code)) % len(FAMILY)]
                id_type, id_number = "national_id", _saudi_id(idx)

            while id_number in used_ids:
                id_number = (_iqama(idx) if is_expat else _saudi_id(idx))
            used_ids.add(id_number)

            person, _ = create_person(
                account=account, first_name_ar=first, family_name_ar=family,
                gender=gender, nationality_code=nat, id_type=id_type,
                id_number=id_number, mobile=_mobile(),
                preferred_locale="ur" if nat in ("PK", "IN", "BD") else "ar",
                force=True)

            # تواريخ مباشرة متنوعة — بينها من يقارب 5 سنوات
            years_ago = [7, 6, 5, 4, 3, 2, 2, 1, 1, 0][idx]
            days_extra = [10, 40, -20, 100, 200, 15, 300, 60, 150, 45][idx]
            join = date.today() - timedelta(days=years_ago * 365 + days_extra)

            lines = [(comps["BASIC"], D(str(basic)))]
            if "HOUSING" in comps:
                lines.append((comps["HOUSING"], D(str(housing))))
            if "TRANSPORT" in comps:
                lines.append((comps["TRANSPORT"], D(str(transport))))

            status = EmploymentStatus.ACTIVE
            if idx == 9 and company.code == "C2":
                status = EmploymentStatus.SUSPENDED

            emp, _, _ = create_employment(
                person=person, company=company,
                employee_no=f"{company.code[-1]}{idx + 101}",
                join_date=join, iban=_iban("80" if idx % 2 else "10"),
                department=depts[min(idx // 2, len(depts) - 1)],
                branch=branches[idx % len(branches)],
                job_title_text=title,
                salary_lines=lines)

            if status != EmploymentStatus.ACTIVE:
                emp.status = status
                emp.save()

            # التسجيل النظامي — متنوّع عمدًا (ق-15)
            emp.is_gosi_registered = idx < 8
            emp.is_mol_registered = idx < 7
            emp.include_in_wps = idx < 8
            emp.gosi_declared_wage = D(str(basic + housing))
            emp.save()

            employments.append((emp, role, scope, person))

        self._seed_users_and_roles(account, company, employments)
        self._seed_managers(employments)
        self._seed_documents(account, company, employments)
        self._seed_advances_assets(account, company, employments)

        return employments

    def _seed_managers(self, employments):
        """سلسلة إدارية: الموظف → المشرف → مدير الإدارة → المدير العام."""
        gm = employments[0][0]
        dept_mgr = employments[1][0]
        sup1 = employments[4][0]
        sup2 = employments[5][0]

        dept_mgr.direct_manager = gm
        dept_mgr.save()
        for emp, *_ in employments[2:4]:
            emp.direct_manager = gm
            emp.save()
        for i, (emp, *_) in enumerate(employments[6:], start=6):
            emp.direct_manager = sup1 if i % 2 == 0 else sup2
            emp.save()
        sup1.direct_manager = dept_mgr
        sup1.save()
        sup2.direct_manager = dept_mgr
        sup2.save()

    def _seed_users_and_roles(self, account, company, employments):
        """
        مستخدم لكل دور — بكلمة مرور واضحة للتجربة.

        السيناريوهات الخاصة تُبنى في _seed_cross_roles.
        """
        from apps.accounts.models_access import (
            AccountMembership, Role, RoleAssignment,
        )

        slug = account.slug.replace("-", "")
        for emp, role_code, scope, person in employments:
            if role_code == "employee" and emp.employee_no[-1] not in "12":
                continue      # نكتفي بموظفين عاديين لكل شركة

            username = f"{slug}.{company.code.lower()}.{role_code}"
            if role_code == "employee":
                username += emp.employee_no[-1]

            if User.objects.filter(username=username).exists():
                continue

            user = User.objects.create_user(
                username=username, password="Test@2026",
                email=f"{username}@demo.sa",
                first_name=person.first_name_ar)

            person.user = user
            person.save()

            role = Role.objects.filter(account=account,
                                       code=role_code).first()
            if role is None:
                continue

            membership = AccountMembership.objects.create(
                user=user, account=account, active_company=company,
                is_account_owner=(role_code == "owner"))
            RoleAssignment.objects.create(
                membership=membership, role=role, company=company,
                scope=scope)

    # ══════════ الوثائق والسلف والعهد ══════════

    def _seed_documents(self, account, company, employments):
        """وثائق بحالات انتهاء متنوعة — منتهية وحرجة وسليمة."""
        from apps.employees.models_assets import EmployeeDocument

        # (الإزاحة بالأيام، النوع) — السالب يعني منتهية
        cases = [
            (-30, "iqama"), (-5, "passport"), (10, "iqama"),
            (25, "work_permit"), (55, "passport"), (120, "iqama"),
            (200, "contract"), (300, "passport"),
        ]

        for i, (emp, *_ ) in enumerate(employments):
            if i >= len(cases):
                continue
            offset, doc_type = cases[i]
            EmployeeDocument.objects.create(
                account=account, company=company, employment=emp,
                document_type=doc_type,
                document_number=f"DOC{random.randint(100000, 999999)}",
                issue_date=date.today() - timedelta(days=365),
                expiry_date=date.today() + timedelta(days=offset))

    def _seed_advances_assets(self, account, company, employments):
        """سلف نشطة ومسدّدة، وعهد مسلّمة ومرتجعة."""
        from apps.employees.models_assets import (
            Advance, AdvanceStatus, Asset, AssetStatus,
        )
        from apps.payroll.models import PayrollSettings

        st = PayrollSettings.objects.filter(company=company).first()
        if st is None:
            return
        st.advances_enabled = True
        st.advance_max_amount = D("30000")
        st.advance_max_months_of_salary = D("3")
        st.save()

        # سلفتان: نشطة ومسدّدة
        for i, status in ((3, AdvanceStatus.ACTIVE),
                          (6, AdvanceStatus.SETTLED)):
            if i >= len(employments):
                continue
            emp = employments[i][0]
            amount = D("9000") if status == AdvanceStatus.ACTIVE else D("6000")
            Advance.objects.create(
                account=account, company=company, employment=emp,
                advance_no=f"ADV-{company.code}-{i:03d}",
                amount=amount, installments_count=6,
                repaid_amount=D("0") if status == AdvanceStatus.ACTIVE
                              else amount,
                status=status, reason="سلفة شخصية",
                start_year=2026, start_month=4)

        # عهد
        assets = [
            ("حاسب محمول", "electronics", D("4500")),
            ("سيارة شركة", "vehicle", D("85000")),
            ("هاتف جوال", "electronics", D("3200")),
            ("أدوات فنية", "tools", D("1800")),
        ]
        for i, (name, cat, value) in enumerate(assets):
            idx = i * 2 + 1
            if idx >= len(employments):
                continue
            emp = employments[idx][0]
            returned = (i == 3)
            Asset.objects.create(
                account=account, company=company, employment=emp,
                asset_no=f"AST-{company.code}-{i:03d}",
                name_ar=name, category=cat, value=value,
                serial_number=f"SN{random.randint(10000, 99999)}",
                assigned_date=date.today() - timedelta(days=200),
                returned_date=(date.today() - timedelta(days=10)
                               if returned else None),
                status=(AssetStatus.RETURNED if returned
                        else AssetStatus.ASSIGNED))

    # ══════════ الحضور ══════════

    def _seed_attendance(self, account, company, employments, months=3):
        """
        حضور ثلاثة أشهر بحالات متنوعة — لاختبار الاحتساب والمخالفات.

        لكل موظف نمط سلوكي ثابت فتظهر الفروقات بين المنضبط والمتأخر.
        """
        from apps.attendance.models import AttendanceDay, DayStatus
        from django.utils import timezone

        # (نسبة الغياب، نسبة التأخير، دقائق التأخير، نسبة الإضافي)
        PATTERNS = [
            (0.00, 0.02,  8, 0.15),   # المدير العام — منضبط
            (0.01, 0.05, 12, 0.20),
            (0.00, 0.03, 10, 0.10),
            (0.02, 0.10, 18, 0.05),
            (0.01, 0.08, 15, 0.30),   # مشرف — إضافي كثير
            (0.03, 0.15, 22, 0.25),
            (0.05, 0.25, 35, 0.05),   # متأخر باستمرار
            (0.02, 0.12, 20, 0.10),
            (0.08, 0.30, 45, 0.02),   # الأكثر مخالفة
            (0.01, 0.06, 14, 0.15),
        ]

        today = date.today()
        start = (today.replace(day=1)
                 - timedelta(days=30 * (months - 1))).replace(day=1)

        rows = []
        for i, (emp, *_ ) in enumerate(employments):
            if emp.status != "active":
                continue
            absent_p, late_p, late_min, ot_p = PATTERNS[i % len(PATTERNS)]

            day = start
            while day <= today:
                # الجمعة والسبت راحة
                if day.weekday() in (4, 5):
                    rows.append(AttendanceDay(
                        account=account, company=company, employment=emp,
                        work_date=day, status=DayStatus.WEEKEND))
                    day += timedelta(days=1)
                    continue

                r = random.random()

                if r < absent_p:
                    rows.append(AttendanceDay(
                        account=account, company=company, employment=emp,
                        work_date=day, status=DayStatus.ABSENT))
                    day += timedelta(days=1)
                    continue

                # يوم عمل
                late = 0
                if random.random() < late_p:
                    late = random.randint(5, late_min)

                in_h, in_m = 8, late
                work_minutes = 8 * 60
                overtime = 0
                if random.random() < ot_p:
                    overtime = random.choice([30, 60, 90, 120])

                first_in = timezone.make_aware(
                    timezone.datetime(day.year, day.month, day.day,
                                      in_h, in_m))
                last_out = first_in + timedelta(
                    minutes=work_minutes + overtime)

                status = DayStatus.PRESENT
                if work_minutes < 4 * 60:
                    status = DayStatus.PARTIAL

                # الإضافي: نصفه معتمد فقط — لاختبار ق-24
                approved_ot = overtime if random.random() < 0.5 else 0

                rows.append(AttendanceDay(
                    account=account, company=company, employment=emp,
                    work_date=day, status=status,
                    first_in=first_in, last_out=last_out,
                    late_minutes=late,
                    worked_minutes=work_minutes,
                    overtime_minutes=overtime,
                    approved_overtime_minutes=approved_ot))

                day += timedelta(days=1)

        AttendanceDay.objects.bulk_create(rows, batch_size=500,
                                          ignore_conflicts=True)
        return len(rows)

    # ══════════ الإجازات ══════════

    def _seed_leaves(self, account, company, employments):
        """طلبات بكل الحالات — معتمدة ومعلّقة ومرفوضة."""
        from apps.leaves.models import RequestStatus
        from apps.leaves.services.balances import LeaveError
        from apps.leaves.services.leave_requests import create_leave_request

        cases = [
            (2, "ANNUAL", -60, 5, RequestStatus.APPROVED),
            (3, "ANNUAL", -30, 10, RequestStatus.APPROVED),
            (4, "SICK", -15, 3, RequestStatus.APPROVED),
            (5, "ANNUAL", 20, 7, RequestStatus.PENDING),
            (6, "ANNUAL", 45, 14, RequestStatus.PENDING),
            (7, "UNPAID", 10, 30, RequestStatus.PENDING),
            (8, "ANNUAL", -90, 4, RequestStatus.REJECTED),
        ]

        made = 0
        for idx, code, offset, days, status in cases:
            if idx >= len(employments):
                continue
            emp = employments[idx][0]
            if emp.status != "active":
                continue
            try:
                res = create_leave_request(
                    employment=emp, leave_type_code=code,
                    start_date=date.today() + timedelta(days=offset),
                    requested_days=days,
                    note="طلب تجريبي")
                if status != RequestStatus.PENDING:
                    res.request.status = status
                    res.request.save()
                made += 1
            except Exception:
                continue
        return made

    # ══════════ المسيرات ══════════

    def _seed_payroll(self, company, months_back=2):
        """مسيران معتمدان وواحد محتسب — لترى الفروقات والمقارنة."""
        from apps.payroll.models import (
            PayrollRunType, PayrollSettings,
        )
        from apps.payroll.services.engine import (
            approve_run, calculate_run, create_run, submit_run,
        )

        st = PayrollSettings.objects.filter(company=company).first()
        if st:
            st.eosb_wage_basis = "flagged"
            st.save()

        today = date.today()
        made = 0

        for back in range(months_back, -1, -1):
            month = today.month - back
            year = today.year
            while month < 1:
                month += 12
                year -= 1

            try:
                run = create_run(company=company,
                                 run_type=PayrollRunType.REGULAR,
                                 year=year, month=month)
                calculate_run(run)
                run.refresh_from_db()

                if back > 0:      # الشهران السابقان معتمدان
                    submit_run(run)
                    run.refresh_from_db()
                    from apps.employees.models import Employment
                    approver = Employment.objects.filter(
                        company=company).first()
                    if approver:
                        approve_run(run, approver.person)
                made += 1
            except Exception:
                continue

        return made

    # ══════════ الملخص ══════════

    def _summary(self, accounts):
        from apps.accounts.models import Company
        from apps.core.tenancy.context import account_scope
        from apps.employees.models import Employment

        self.stdout.write("")
        self.stdout.write("═══════════════════════════════════")
        self.stdout.write(self.style.SUCCESS("  اكتملت البذرة"))
        self.stdout.write("═══════════════════════════════════")
        self.stdout.write("")

        total_emp = 0
        for entry in accounts:
            acc = entry["account"]
            with account_scope(acc.id):
                n = Employment.objects.filter(account=acc).count()
                total_emp += n
                self.stdout.write(f"  {acc.display_name_ar}")
                self.stdout.write(
                    f"    {len(entry['companies'])} شركة · {n} موظفًا")

        self.stdout.write("")
        self.stdout.write(f"  الإجمالي: {total_emp} موظفًا")
        self.stdout.write("")
        self.stdout.write("  ── الدخول ──")
        self.stdout.write("  كلمة المرور للجميع: Test@2026")
        self.stdout.write("")
        self.stdout.write("  مثال — مجموعة معتمد، شركة المقاولات:")
        self.stdout.write("    muatmdgroup.c1.owner        المدير العام")
        self.stdout.write("    muatmdgroup.c1.hr_manager   مدير الموارد")
        self.stdout.write("    muatmdgroup.c1.hr_staff     أخصائي موارد")
        self.stdout.write("    muatmdgroup.c1.supervisor   مشرف")
        self.stdout.write("    muatmdgroup.c1.employee1    موظف عادي")
        self.stdout.write("")
        self.stdout.write("  لوحة المنصة (admin.muatmd.sa):")
        self.stdout.write("    admin / support / viewer — Admin@2026")
        self.stdout.write("")
