"""
إنشاء مالك الحساب — مربوطًا بموظفه (ق-٢٥٥).

⚠️⚠️ **المالك موظفٌ أيضًا.** أُنشئ أول مالكٍ يدويًّا فلم يُربط بموظفه — وكانت
`create_person` قد أنشأت للشخص مستخدمًا تلقائيًّا، **فصار للشخص الواحد
مستخدمان**: واحدٌ يدخل به ولا ملفّ له، وواحدٌ له ملفٌّ ولا يدخل به. فلا يرى
المالك ملفَّه ولا قسائمه ولا طلباته، **ولا يعمل له التطبيق**.

⚠️⚠️ **والملكية ليست دورًا.** المالك مَن سجّل ويملك الاشتراك — **صفةُ حساب**
(`is_account_owner`)؛ **والدور ما يفعله في الشركة**: مدير موارد، مدير عام،
موظف. وصاحبُ أول حسابٍ حقيقيّ **مالكٌ وموظفٌ ومدير موارد** — ثلاثةٌ في شخص.
فيُسأل عن دوره ولا يُفرض عليه `owner`.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Account
from apps.accounts.models_access import (AccountMembership, Role,
                                         RoleAssignment, Scope)
from apps.core.tenancy.context import account_scope
from apps.employees.models import Employment


class Command(BaseCommand):
    help = "ينشئ مالك الحساب، يربطه بموظفه، ويسند دوره في الشركة"

    def add_arguments(self, parser):
        parser.add_argument("--account", type=int, required=True)
        parser.add_argument("--employee-no", required=True,
                            help="رقم الموظف الذي يملك الحساب")
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument("--role", default="hr_manager",
                            help="دوره في الشركة: hr_manager · ceo · …")

    @transaction.atomic
    def handle(self, *args, **o):
        U = get_user_model()
        with account_scope(o["account"]):
            acc = Account.objects.get(id=o["account"])
            emp = Employment.objects.filter(
                employee_no=o["employee_no"]).select_related("person").first()
            if emp is None:
                raise CommandError(f"لا موظف برقم {o['employee_no']}")
            role = Role.objects.filter(code=o["role"]).first()
            if role is None:
                raise CommandError(f"لا دور برمز {o['role']}")

            person = emp.person
            previous = person.user_id

            user, _ = U.objects.get_or_create(
                username=o["username"],
                defaults={"email": o["email"], "is_active": True})
            user.set_password(o["password"])
            if o["email"]:
                user.email = o["email"]
            user.is_active = True
            user.save()

            # ⭐ **الربط هو بيت القصيد** — وبه يرى المالك ملفَّه ويعمل التطبيق
            person.user = user
            person.save(update_fields=["user"])

            # ⚠️ والمستخدم التلقائيّ السابق **يُعطَّل لا يُحذف** — فسجلّاته تبقى
            if previous and previous != user.id:
                old = U.objects.filter(id=previous).first()
                if old:
                    old.is_active = False
                    old.save(update_fields=["is_active"])
                    self.stdout.write(f"عُطّل المكرّر: {old.username}")

            m, _ = AccountMembership.objects.get_or_create(
                user=user, account=acc,
                defaults={"is_account_owner": True, "is_founding_owner": True})
            m.is_account_owner = True
            m.active_company_id = emp.company_id
            m.save()

            RoleAssignment.objects.filter(membership=m).delete()
            RoleAssignment.objects.create(
                membership=m, role=role, employment=emp,
                scope=Scope.ACCOUNT.value, company_id=emp.company_id)

            self.stdout.write(self.style.SUCCESS(
                f"✔ المالك {user.username} ← {emp.employee_no} "
                f"({person.display_name}) · دوره: {role.name_ar}"))
