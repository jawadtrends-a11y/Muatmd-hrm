"""
بذر بيانات تجريبية كاملة — لتجربة النظام من طرف لطرف.

    python manage.py seed_demo            # ينشئ
    python manage.py seed_demo --reset    # يحذف ويعيد

يغطي حالات حقيقية متعمدة:
  • سعودي مسجّل بإضافي وتأخير
  • وافد غير مسجّل (لا يُخصم منه شيء — ق-15)
  • موظف موقوف (يظهر في المستبعدين)
  • موظف بلا هيكل راتب (يفشل احتسابه بلا إيقاف المسير)
  • شخص واحد في شركتين (ق-4)
  • مسيران: فبراير معتمد ومارس محتسب (للمقارنة)
"""
from datetime import date, datetime
from decimal import Decimal as D

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

SLUG = "demo"

# آيبانات صحيحة رياضيًا (MOD-97)
IBAN_NCB = "SA8510000012345678901234"
IBAN_RJHI = "SA6080000247608010330101"
IBAN_RIBL = "SA4080000024760801033010"

SCOPED_TABLES = [
    "payroll_payslip", "payroll_payrollrun", "payroll_banktemplate",
    "leaves_requestapproval", "leaves_request", "leaves_approvalchain",
    "leaves_leavebalance", "leaves_leaveentitlement", "leaves_leavetype",
    "attendance_attendancemonthlysummary", "attendance_attendanceday",
    "attendance_attendancepunch", "attendance_shiftassignment",
    "attendance_shift", "employees_salarystructure",
    "employees_employment", "employees_person", "organization_holiday",
    "organization_jobtitle", "organization_costcenter",
    "organization_department", "organization_branch",
    "payroll_payrollsettings", "payroll_paycomponent",
    "accounts_companyheadcountdaily", "accounts_companysubscription",
    "accounts_accountmembership",
    "accounts_role", "accounts_company",
]


class Command(BaseCommand):
    help = "بذر بيانات تجريبية كاملة لتجربة النظام"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="حذف الحساب التجريبي وإعادة بنائه")

    def handle(self, *args, **options):
        from apps.accounts.models import Account

        existing = Account.objects.filter(slug=SLUG).first()
        if existing and not options["reset"]:
            self.stdout.write(self.style.WARNING(
                f"الحساب '{SLUG}' موجود (id={existing.id}). "
                "استخدم --reset لإعادة البناء."))
            return
        if existing:
            self.stdout.write("حذف الحساب التجريبي القائم…")
            self._purge(existing.id)

        self._build()

    def _purge(self, account_id):
        """حذف بترتيب التبعيات — الأبناء أولًا."""
        with connection.cursor() as cur:
            cur.execute("SET session_replication_role = replica")
            cur.execute("DELETE FROM payroll_payslipline WHERE payslip_id IN "
                        "(SELECT id FROM payroll_payslip WHERE account_id=%s)",
                        [account_id])
            cur.execute("DELETE FROM payroll_bankcolumn WHERE template_id IN "
                        "(SELECT id FROM payroll_banktemplate "
                        "WHERE account_id=%s)", [account_id])
            cur.execute("DELETE FROM leaves_approvalstep WHERE chain_id IN "
                        "(SELECT id FROM leaves_approvalchain "
                        "WHERE account_id=%s)", [account_id])
            cur.execute("DELETE FROM leaves_leavetier WHERE leave_type_id IN "
                        "(SELECT id FROM leaves_leavetype WHERE account_id=%s)",
                        [account_id])
            cur.execute("DELETE FROM employees_salaryline WHERE structure_id IN "
                        "(SELECT id FROM employees_salarystructure "
                        "WHERE account_id=%s)", [account_id])
            cur.execute("DELETE FROM accounts_rolepermission WHERE role_id IN "
                        "(SELECT id FROM accounts_role WHERE account_id=%s)",
                        [account_id])
            cur.execute("DELETE FROM accounts_roleassignment "
                        "WHERE membership_id IN (SELECT id FROM "
                        "accounts_accountmembership WHERE account_id=%s)",
                        [account_id])
            for table in SCOPED_TABLES:
                cur.execute(f"DELETE FROM {table} WHERE account_id=%s",
                            [account_id])
            cur.execute("DELETE FROM accounts_account WHERE id=%s",
                        [account_id])
            cur.execute("SET session_replication_role = DEFAULT")

    # ══════════ البناء ══════════

    @transaction.atomic
    def _build(self):
        from apps.accounts.models import Account, Company
        from apps.accounts.services.provisioning import provision_account
        from apps.core.tenancy.context import account_scope
        from apps.payroll.services.gosi_seed import sync_gosi_rates

        sync_gosi_rates()
        self.stdout.write("نسب التأمينات ✓")

        prov = provision_account(
            slug=SLUG, display_name_ar="مجموعة معتمد التجريبية",
            company_name_ar="شركة معتمد للمقاولات", is_sandbox=True)

        with account_scope(prov.account_id):
            acc = Account.objects.get(id=prov.account_id)
            c1 = Company.objects.get(id=prov.company_id)
            c2 = self._second_company(acc)
            self.stdout.write(f"شركتان ✓")

            org = self._org(c1)
            people = self._people(acc, c1, c2, org)
            self._attendance(acc, c1, people)
            self._leaves(people)
            self._runs(c1)

        self.stdout.write(self.style.SUCCESS(
            f"\nاكتمل. الحساب: {SLUG} (id={prov.account_id})"))

    def _second_company(self, acc):
        from apps.accounts.models import Company
        from apps.leaves.services.seeds import (
            provision_approval_chains, provision_leave_types,
        )
        from apps.payroll.models import PayrollSettings
        from apps.payroll.services.components import provision_default_components
        from apps.payroll.services.outputs.templates_seed import (
            provision_bank_templates,
        )

        c2 = Company.objects.create(account=acc, code="C2",
                                    legal_name_ar="شركة معتمد للتجارة")
        provision_default_components(c2)
        PayrollSettings.objects.get_or_create(company=c2,
                                              defaults={"account": acc})
        provision_leave_types(c2)
        provision_approval_chains(c2)
        provision_bank_templates(c2)
        return c2

    def _org(self, comp):
        from apps.organization.models import JobTitle
        from apps.organization.services.structure import (
            create_branch, create_department, create_holiday,
        )

        branch = create_branch(company=comp, code="RUH",
                               name_ar="فرع الرياض", city="الرياض",
                               mol_establishment_no="1234567")
        admin = create_department(company=comp, code="ADM",
                                  name_ar="الإدارة العامة")
        admin.name_en = "Administration"
        admin.save()
        eng = create_department(company=comp, code="ENG",
                                name_ar="الهندسة", parent=admin)
        eng.name_en = "Engineering"
        eng.save()

        title = JobTitle.objects.create(
            account=comp.account, company=comp, name_ar="مهندس مدني",
            name_en="Civil Engineer", mol_occupation_code="2142")

        create_holiday(company=comp, name_ar="عيد الفطر",
                       start_date=date(2026, 3, 19),
                       end_date=date(2026, 3, 22))
        return {"branch": branch, "admin": admin, "eng": eng, "title": title}

    def _people(self, acc, c1, c2, org):
        from apps.attendance.models import Shift, ShiftAssignment
        from apps.employees.models import EmploymentStatus
        from apps.employees.services.hiring import (
            create_employment, create_person,
        )
        from apps.payroll.models import PayComponent

        comps = {c.code: c for c in PayComponent.objects.filter(company=c1)}
        comps2 = {c.code: c for c in PayComponent.objects.filter(company=c2)}

        shift = Shift.objects.create(
            account=acc, company=c1, code="DAY", name_ar="الدوام الصباحي",
            start_time="08:00", end_time="16:00", break_minutes=60,
            grace_in_minutes=15, working_days=[0, 1, 2, 3, 4])

        out = {}

        # 1) المدير — سعودي مسجّل
        p, _ = create_person(
            account=acc, first_name_ar="خالد", father_name_ar="سعد",
            family_name_ar="الحربي", full_name_en="KHALID SAAD ALHARBI",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1011122233", mobile="0501112223",
            email="khalid@demo.sa", gosi_scheme_code="traditional",
            birth_date=date(1985, 5, 10), force=True)
        mgr, _, _ = create_employment(
            person=p, company=c1, employee_no="101",
            join_date=date(2019, 1, 1), branch=org["branch"],
            department=org["admin"], job_title=org["title"],
            iban=IBAN_NCB, bank_code="NCBK",
            salary_lines=[(comps["BASIC"], D("15000")),
                          (comps["HOUSING"], D("3750")),
                          (comps["TRANSPORT"], D("1500"))])
        mgr.is_gosi_registered = True
        mgr.is_mol_registered = True
        mgr.include_in_wps = True
        mgr.save()
        ShiftAssignment.objects.create(account=acc, company=c1,
                                       employment=mgr, shift=shift,
                                       effective_from=date(2019, 1, 1))
        out["manager"] = mgr

        # 2) موظف سعودي — إضافي وتأخير
        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            full_name_en="SAAD ALQAHTANI", gender="male",
            nationality_code="SA", id_type="national_id",
            id_number="1099887766", mobile="0509887766",
            gosi_scheme_code="new_scheme", birth_date=date(1998, 3, 15),
            force=True)
        saudi, _, _ = create_employment(
            person=p, company=c1, employee_no="201",
            join_date=date(2021, 6, 1), branch=org["branch"],
            department=org["eng"], job_title=org["title"],
            direct_manager=mgr, iban=IBAN_RIBL, bank_code="RIBL",
            salary_lines=[(comps["BASIC"], D("9000")),
                          (comps["HOUSING"], D("2250")),
                          (comps["TRANSPORT"], D("900"))])
        saudi.is_gosi_registered = True
        saudi.is_mol_registered = True
        saudi.include_in_wps = True
        saudi.save()
        ShiftAssignment.objects.create(account=acc, company=c1,
                                       employment=saudi, shift=shift,
                                       effective_from=date(2021, 6, 1))
        out["saudi"] = saudi

        # 3) وافد — غير مسجّل (ق-15)
        p, _ = create_person(
            account=acc, first_name_ar="راشد", family_name_ar="خان",
            full_name_en="RASHID KHAN", gender="male",
            nationality_code="PK", id_type="iqama",
            id_number="2154967927", mobile="0504445556",
            preferred_locale="ur", birth_date=date(1990, 8, 20), force=True)
        expat, _, _ = create_employment(
            person=p, company=c1, employee_no="301",
            join_date=date(2022, 3, 1), branch=org["branch"],
            department=org["eng"], direct_manager=mgr,
            iban=IBAN_RJHI, bank_code="RJHI",
            salary_lines=[(comps["BASIC"], D("4000")),
                          (comps["HOUSING"], D("1000")),
                          (comps["TRANSPORT"], D("500"))])
        expat.include_in_wps = True
        expat.save()
        ShiftAssignment.objects.create(account=acc, company=c1,
                                       employment=expat, shift=shift,
                                       effective_from=date(2022, 3, 1))
        out["expat"] = expat

        # 4) موقوف — يظهر في المستبعدين
        p, _ = create_person(
            account=acc, first_name_ar="فهد", family_name_ar="العتيبي",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1055443322", mobile="0505443322", force=True)
        susp, _, _ = create_employment(
            person=p, company=c1, employee_no="401",
            join_date=date(2023, 1, 1), direct_manager=mgr,
            salary_lines=[(comps["BASIC"], D("5000"))])
        susp.status = EmploymentStatus.SUSPENDED
        susp.save()
        out["suspended"] = susp

        # 5) بلا هيكل راتب — يفشل احتسابه
        p, _ = create_person(
            account=acc, first_name_ar="عمر", family_name_ar="الزهراني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1077766655", mobile="0507776665", force=True)
        create_employment(person=p, company=c1, employee_no="501",
                          join_date=date(2025, 1, 1), direct_manager=mgr)

        # 6) المدير في الشركة الثانية (ق-4)
        create_employment(
            person=out["manager"].person, company=c2, employee_no="C2-01",
            join_date=date(2024, 1, 1), employment_type="secondary",
            work_ratio=D("0.5"), iban=IBAN_NCB, bank_code="NCBK",
            salary_lines=[(comps2["BASIC"], D("6000"))])

        self.stdout.write("ستة ارتباطات وظيفية ✓")
        return out

    def _attendance(self, acc, comp, people):
        from apps.attendance.models import AttendanceDay
        from apps.attendance.services.processing import (
            approve_overtime, build_monthly_summary, process_employment_days,
            record_punch,
        )

        tz = timezone.get_current_timezone()

        def stamp(d, h, m=0):
            return timezone.make_aware(datetime(2026, 3, d, h, m), tz)

        # المدير: حضور منتظم
        for day in (2, 3, 4, 5, 9, 10, 11, 12):
            record_punch(employment=people["manager"], punched_at=stamp(day, 8),
                         source="device", external_ref=f"m{day}i")
            record_punch(employment=people["manager"],
                         punched_at=stamp(day, 16), source="device",
                         external_ref=f"m{day}o")

        # السعودي: يوم بإضافي (3 مارس حتى 19) ويوم بتأخير (4 مارس 8:40)
        schedule = {2: (8, 0, 16), 3: (8, 0, 19), 4: (8, 40, 16),
                    5: (8, 0, 16), 9: (8, 0, 16), 10: (8, 0, 16)}
        for day, (hi, mi, ho) in schedule.items():
            record_punch(employment=people["saudi"],
                         punched_at=stamp(day, hi, mi), source="device",
                         external_ref=f"s{day}i")
            record_punch(employment=people["saudi"], punched_at=stamp(day, ho),
                         source="device", external_ref=f"s{day}o")

        # الوافد: بصمة واحدة يوميًا — حضور جزئي
        for day in (2, 3, 4, 5):
            record_punch(employment=people["expat"], punched_at=stamp(day, 8),
                         source="device", external_ref=f"e{day}i")

        for key in ("manager", "saudi", "expat"):
            process_employment_days(employment=people[key],
                                    start_date=date(2026, 3, 1),
                                    end_date=date(2026, 3, 31))

        ot = AttendanceDay.objects.filter(
            employment=people["saudi"], work_date=date(2026, 3, 3)).first()
        if ot and ot.overtime_minutes:
            approve_overtime(attendance_day=ot,
                             minutes=min(180, ot.overtime_minutes),
                             approved_by_person=people["manager"].person)

        for key in ("manager", "saudi", "expat"):
            build_monthly_summary(employment=people[key], year=2026, month=3)

        self.stdout.write("بصمات وسجلات حضور ومُلخصات مارس ✓")

    def _leaves(self, people):
        from apps.leaves.models import ApprovalDecision, LeaveType
        from apps.leaves.services.approvals import decide
        from apps.leaves.services.balances import accrue
        from apps.leaves.services.leave_requests import (
            apply_approved_leave, create_leave_request,
        )

        annual = LeaveType.objects.get(
            company=people["saudi"].company, code="ANNUAL")
        for key in ("manager", "saudi", "expat"):
            accrue(people[key], annual, as_of=date(2026, 12, 31))

        # إجازة معتمدة ومطبَّقة
        res = create_leave_request(
            employment=people["saudi"], leave_type_code="ANNUAL",
            start_date=date(2026, 4, 5), requested_days=5,
            note="إجازة سنوية")
        req = decide(request_obj=res.request,
                     approver_employment=people["manager"],
                     decision=ApprovalDecision.APPROVED, comment="موافق")
        apply_approved_leave(req)

        # طلب معلّق بانتظار الاعتماد
        create_leave_request(
            employment=people["expat"], leave_type_code="ANNUAL",
            start_date=date(2026, 5, 10), requested_days=3,
            note="بانتظار الاعتماد")

        self.stdout.write("إجازة معتمدة وأخرى معلّقة ✓")

    def _runs(self, comp):
        from apps.employees.models import Employment
        from apps.payroll.models import PayrollRunType
        from apps.payroll.services.engine import (
            approve_run, calculate_run, create_run, submit_run,
        )

        approver = Employment.objects.filter(
            company=comp, employee_no="101").first()

        # فبراير — معتمد (أساس المقارنة وتصدير البنك)
        feb = create_run(company=comp, run_type=PayrollRunType.REGULAR,
                         year=2026, month=2)
        calculate_run(feb)
        feb.refresh_from_db()
        submit_run(feb)
        feb.refresh_from_db()
        approve_run(feb, approver.person)
        feb.refresh_from_db()
        feb.payment_date = date(2026, 2, 25)
        feb.save()

        # مارس — محتسب بانتظار المراجعة
        mar = create_run(company=comp, run_type=PayrollRunType.REGULAR,
                         year=2026, month=3)
        res = calculate_run(mar)
        mar.refresh_from_db()

        self.stdout.write(
            f"مسيران: فبراير معتمد · مارس محتسب "
            f"({res.calculated} قسيمة، {res.failed} فشل، "
            f"{mar.variance_count} فروقات) ✓")
