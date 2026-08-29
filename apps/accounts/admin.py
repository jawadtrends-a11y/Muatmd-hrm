"""
لوحة إدارة الحسابات — للسوبر أدمن.

تنبيه: هذه اللوحة تعمل بدور hrm_runtime بلا سياق حساب، فلن ترى
شيئًا افتراضيًا. تجاوز مؤقت مقصور على المستخدمين الخارقين حتى
تُبنى لوحة السوبر أدمن المستقلة (السبرنت 4).
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Account, Company
from apps.core.tenancy.context import account_scope


class CompanyInline(admin.TabularInline):
    model = Company
    extra = 0
    fields = ("code", "legal_name_ar", "cr_number", "is_active")
    show_change_link = True


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("display_name_ar", "slug", "status", "company_count",
                    "is_sandbox", "created_at")
    list_filter = ("status", "isolation_mode", "is_sandbox")
    search_fields = ("slug", "display_name_ar", "display_name_en")
    readonly_fields = ("uuid", "created_at", "updated_at")
    inlines = [CompanyInline]

    fieldsets = (
        (_("الهوية"), {"fields": ("slug", "display_name_ar", "display_name_en", "uuid")}),
        (_("الحالة والاشتراك"), {"fields": ("status", "is_sandbox",
                                             "suspended_at", "suspension_reason")}),
        (_("الإعدادات"), {"fields": ("isolation_mode", "default_locale", "timezone",
                                     "employee_no_scope",
                                     "allow_cross_company_employment")}),
        (_("التواريخ"), {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description=_("عدد الشركات"))
    def company_count(self, obj):
        return obj.companies.count()

    def has_add_permission(self, request):
        # الإنشاء يمر بـprovision_account حصرًا — لا من اللوحة
        return False


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("legal_name_ar", "code", "account", "cr_number", "is_active")
    list_filter = ("is_active", "entity_size")
    search_fields = ("legal_name_ar", "legal_name_en", "code", "cr_number")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("account",)

    fieldsets = (
        (_("الأساسيات"), {"fields": ("account", "code",
                                     "legal_name_ar", "legal_name_en")}),
        (_("السجلات النظامية"), {"fields": ("cr_number", "cr_expiry_date",
                                            "unified_national_number", "vat_number")}),
        (_("الجهات الحكومية"), {"fields": ("gosi_establishment_no",
                                           "mol_establishment_no",
                                           "activity_code", "entity_size")}),
        (_("الإعدادات"), {"fields": ("fiscal_year_start_month", "is_active")}),
    )
