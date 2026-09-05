from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.api.workspace import workspace
from apps.core.api import access as access_api
from apps.organization import api as org_api
from apps.core.api import billing as billing_api
from apps.payroll import api as payroll_api
from apps.employees import api as employees_api
from apps.attendance import api as attendance_api
from apps.payroll import api_outputs as outputs_api
from apps.employees import api_assets as assets_api
from apps.core import api_reports as reports_api
from apps.core import api_audit as audit_api
from apps.accounts import api_billing as acct_billing
from apps.accounts import api_platform_auth as platform_auth_api
from apps.accounts import api_admin as platform_admin_api
from apps.accounts import api_auth as client_auth
from apps.leaves import api as leaves_api
from apps.notifications import api as notifications_api


def health(request):
    return JsonResponse({"status": "ok", "service": "muatmd-hrm"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/me/workspace/", workspace, name="workspace"),
    path("api/org/branches/", org_api.branches, name="branches"),
    path("api/org/departments/", org_api.departments, name="departments"),
    path("api/org/departments/tree/", org_api.department_tree_view, name="dept-tree"),
    path("api/org/departments/<int:dept_id>/move/", org_api.department_move, name="dept-move"),
    path("api/org/holidays/", org_api.holidays, name="holidays"),
    path("api/org/job-titles/", org_api.job_titles, name="job-titles"),
    path("api/access/permissions/", access_api.permission_catalog, name="perm-catalog"),
    path("api/access/roles/", access_api.role_list, name="role-list"),
    path("api/access/roles/<int:role_id>/", access_api.role_detail, name="role-detail"),
    path("api/access/roles/<int:role_id>/permissions/", access_api.role_permissions_update, name="role-perms"),
    # صلاحيات موظف بعينه (ق-67 وق-78)
    path("api/access/members/", access_api.member_list, name="member-list"),
    path("api/access/members/<int:employment_id>/permissions/", access_api.member_permissions, name="member-perms"),
    # تخصيص أنواع الطلبات لمعتمِد (ق-74)
    path("api/access/members/<int:employment_id>/approver-scopes/", access_api.member_approver_scopes, name="member-approver-scopes"),
    # نقل ملكية الحساب (ق-76)
    path("api/access/members/<int:employment_id>/ownership/", access_api.transfer_ownership, name="member-ownership"),
    path("api/access/members/<int:employment_id>/login/", access_api.remove_login, name="member-login-remove"),
    path("api/billing/plans/", billing_api.plan_catalog, name="plan-catalog"),
    path("api/billing/subscription/", billing_api.my_subscription, name="my-subscription"),
    path("api/billing/estimate/", billing_api.billing_estimate, name="billing-estimate"),
    path("api/payroll/components/", payroll_api.components, name="pay-components"),
    path("api/payroll/components/<int:component_id>/flags/", payroll_api.component_flags, name="pay-component-flags"),
    path("api/payroll/settings/", payroll_api.payroll_settings, name="payroll-settings"),
    path("api/payroll/eosb/calculate/", payroll_api.eosb_calculator, name="eosb-calc"),
    path("api/payroll/termination-reasons/", payroll_api.termination_reasons, name="termination-reasons"),
    path("api/employees/", employees_api.employees, name="employees"),
    path("api/employees/<int:employment_id>/", employees_api.employee_detail, name="employee-detail"),
    path("api/employees/<int:employment_id>/salary/", employees_api.salary_structures, name="salary-structures"),
    path("api/employees/<int:employment_id>/registration/", employees_api.registration_flags, name="registration-flags"),
    # التغيير الوظيفي (ق-82)
    path("api/employees/<int:employment_id>/job-changes/", employees_api.job_changes, name="job-changes"),
    path("api/job-changes/<int:change_id>/decide/", employees_api.decide_job_change, name="job-change-decide"),
    path("api/me/job-changes/", employees_api.my_job_changes, name="my-job-changes"),
    path("api/attendance/shifts/", attendance_api.shifts, name="shifts"),
    path("api/attendance/punch/", attendance_api.punch, name="punch"),
    path("api/attendance/<int:employment_id>/punches/", attendance_api.punches, name="punches"),
    path("api/attendance/<int:employment_id>/days/", attendance_api.attendance_days, name="attendance-days"),
    path("api/attendance/<int:employment_id>/summary/", attendance_api.monthly_summary, name="attendance-summary"),
    path("api/attendance/days/<int:day_id>/overtime/", attendance_api.approve_day_overtime, name="approve-overtime"),
    path("api/attendance/days/<int:day_id>/adjust/", attendance_api.adjust_day, name="adjust-day"),
    path("api/payroll/runs/<int:run_id>/overview/", outputs_api.run_overview, name="run-overview"),
    path("api/payroll/runs/<int:run_id>/tab/<str:tab>/", outputs_api.run_tab, name="run-tab"),
    path("api/payroll/bank-templates/", outputs_api.bank_templates, name="bank-templates"),
    path("api/payroll/runs/<int:run_id>/bank/<int:template_id>/preview/", outputs_api.bank_file_preview, name="bank-preview"),
    path("api/payroll/runs/<int:run_id>/bank/<int:template_id>/download/", outputs_api.bank_file_download, name="bank-download"),
    path("api/payroll/runs/<int:run_id>/wps/preview/", outputs_api.wps_preview, name="wps-preview"),
    path("api/payroll/runs/<int:run_id>/wps/download/", outputs_api.wps_download, name="wps-download"),
    path("api/payslips/<int:payslip_id>/", outputs_api.payslip_detail, name="payslip-detail"),
    path("api/me/payslips/", outputs_api.my_payslips, name="my-payslips"),
    path("api/advances/", assets_api.advances, name="advances"),
    path("api/advances/<int:advance_id>/approve/", assets_api.advance_approve, name="advance-approve"),
    path("api/advances/<int:advance_id>/schedule/", assets_api.advance_schedule, name="advance-schedule"),
    path("api/employees/<int:employment_id>/advance-eligibility/", assets_api.advance_eligibility, name="advance-eligibility"),
    path("api/assets/", assets_api.assets, name="assets"),
    path("api/assets/<int:asset_id>/return/", assets_api.asset_return, name="asset-return"),
    path("api/documents/", assets_api.documents, name="documents"),
    path("api/documents/expiring/", assets_api.expiring_documents_view, name="expiring-documents"),
    path("api/employees/<int:employment_id>/clearance/", assets_api.employee_settlement_preview, name="clearance"),
    path("api/employees/<int:employment_id>/settlement/preview/", assets_api.settlement_preview, name="settlement-preview"),
    path("api/employees/<int:employment_id>/settlement/create/", assets_api.settlement_create, name="settlement-create"),
    path("api/settlement/reasons/", assets_api.termination_reasons_list, name="settlement-reasons"),
    path("api/reports/", reports_api.reports_catalog, name="reports-catalog"),
    path("api/reports/<str:key>/", reports_api.run_report, name="run-report"),
    path("api/audit/", audit_api.audit_feed, name="audit-feed"),
    path("api/audit/<str:object_type>/<int:object_id>/", audit_api.object_history, name="audit-history"),
    # اشتراك الحساب والفوترة (ق-47، ق-49) — يختلف عن
    # api/billing/* أعلاه التي تخص اشتراك الشركة بباقة
    path("api/account/subscription/", acct_billing.subscription_status, name="acct-subscription"),
    path("api/account/plans/", acct_billing.available_plans, name="acct-plans"),
    path("api/account/invoices/", acct_billing.invoices, name="acct-invoices"),
    path("api/account/invoices/<int:invoice_id>/", acct_billing.invoice_detail, name="acct-invoice-detail"),
    path("api/account/checkout/", acct_billing.start_checkout, name="acct-checkout"),
    path("api/account/invoices/<int:invoice_id>/pay/", acct_billing.pay_invoice, name="acct-pay"),
    path("api/account/auto-renew/", acct_billing.toggle_auto_renew, name="acct-auto-renew"),
    path("api/account/cards/", acct_billing.saved_cards, name="acct-cards"),
    path("billing/callback", acct_billing.payment_callback, name="payment-callback"),
    # ══ لوحة المنصة (ق-51) — معزولة عن مسارات العملاء ══
    path("platform/auth/login/", platform_auth_api.platform_login, name="platform-login"),
    path("platform/auth/logout/", platform_auth_api.platform_logout, name="platform-logout"),
    path("platform/auth/me/", platform_auth_api.platform_me, name="platform-me"),
    path("platform/auth/totp/", platform_auth_api.platform_totp_setup, name="platform-totp"),
    path("platform/accounts/", platform_admin_api.accounts_list, name="platform-accounts"),
    path("platform/accounts/<int:account_id>/", platform_admin_api.account_detail, name="platform-account"),
    path("platform/accounts/<int:account_id>/impersonate/", platform_auth_api.impersonate_start, name="impersonate-start"),
    path("platform/impersonate/end/", platform_auth_api.impersonate_end, name="impersonate-end"),
    path("platform/impersonate/status/", platform_auth_api.impersonation_status, name="impersonate-status"),
    path("platform/accounts/<int:account_id>/activate/", platform_admin_api.admin_activate, name="platform-activate"),
    path("platform/accounts/<int:account_id>/extend/", platform_admin_api.admin_extend, name="platform-extend"),
    path("platform/invoices/<int:invoice_id>/mark-paid/", platform_admin_api.admin_mark_invoice_paid, name="platform-mark-paid"),
    path("platform/discounts/", platform_admin_api.admin_discounts, name="platform-discounts"),
    path("platform/discounts/<int:discount_id>/", platform_admin_api.admin_discount_detail, name="platform-discount"),
    path("platform/settings/", platform_admin_api.platform_settings, name="platform-settings"),
    path("platform/dashboard/", platform_admin_api.admin_dashboard, name="platform-dashboard"),
    # مصادقة العملاء بالرموز (ق-53) — منفصلة عن platform/auth
    path("api/auth/login/", client_auth.login_view, name="auth-login"),
    path("api/auth/logout/", client_auth.logout_view, name="auth-logout"),
    path("api/auth/sessions/", client_auth.sessions_view, name="auth-sessions"),
    # الإجازات والطلبات
    path("api/leaves/types/", leaves_api.leave_types, name="leave-types"),
    # إدارة أنواع الإجازات (ق-83)
    path("api/leaves/types/new/", leaves_api.leave_type_create, name="leave-type-create"),
    path("api/leaves/types/<int:type_id>/", leaves_api.leave_type_detail, name="leave-type-detail"),
    path("api/leaves/balances/", leaves_api.leave_balances, name="leave-balances"),
    path("api/leaves/requests/", leaves_api.leave_requests, name="leave-requests"),
    path("api/leaves/requests/<int:request_id>/", leaves_api.request_detail, name="request-detail"),
    path("api/leaves/requests/<int:request_id>/decide/", leaves_api.decide_request, name="request-decide"),
    path("api/me/requests/", leaves_api.my_requests, name="my-requests"),
    path("api/me/approvals/", leaves_api.my_approvals, name="my-approvals"),
    path("api/me/leaves/", leaves_api.my_leave_summary, name="my-leaves"),
    # إدارة المسيرات
    # التسويات الرجعية (ق-69)
    path("api/payroll/retro/", payroll_api.retro_pending, name="retro-pending"),
    path("api/payroll/retro/<int:adjustment_id>/decide/", payroll_api.retro_decide, name="retro-decide"),
    path("api/payroll/runs/", payroll_api.payroll_runs, name="payroll-runs"),
    path("api/payroll/runs/<int:run_id>/calculate/", payroll_api.run_calculate, name="run-calculate"),
    path("api/payroll/runs/<int:run_id>/submit/", payroll_api.run_submit, name="run-submit"),
    path("api/payroll/runs/<int:run_id>/approve/", payroll_api.run_approve, name="run-approve"),
    # الحضور الجماعي
    path("api/attendance/daily/", attendance_api.daily_board, name="attendance-daily"),
    path("api/attendance/monthly/", attendance_api.monthly_board, name="attendance-monthly"),
    path("api/payroll/bank-lookup/", payroll_api.bank_lookup, name="bank-lookup"),
    path("api/me/request-types/", leaves_api.request_types, name="request-types"),
    path("api/requests/", leaves_api.submit_request, name="submit-request"),
    path("api/me/profile/", employees_api.my_profile, name="my-profile"),
    path("api/me/attendance/", attendance_api.my_attendance, name="my-attendance"),
    path("api/me/leaves-detail/", leaves_api.my_leaves_detail, name="my-leaves-detail"),
    path("api/me/letters/", leaves_api.my_letters, name="my-letters"),
    path("api/requests/preview/", leaves_api.preview_request, name="preview-request"),
    path("api/me/account/", employees_api.my_account, name="my-account"),
    path("api/me/password/", employees_api.change_my_password, name="my-password"),
    path("api/me/avatar/", employees_api.my_avatar, name="my-avatar"),
    path("api/files/", employees_api.upload_attachment, name="upload-attachment"),
    path("api/files/<int:file_id>/", employees_api.serve_file, name="serve-file"),
    path("api/sites/", attendance_api.work_sites, name="work-sites"),
    path("api/sites/<int:site_id>/", attendance_api.work_site_detail, name="site-detail"),
    path("api/sites/<int:site_id>/employees/", attendance_api.site_assignments, name="site-employees"),
    path("api/me/punch/", attendance_api.my_punch, name="my-punch"),
    path("api/employees/<int:employment_id>/profile/", employees_api.employee_profile, name="employee-profile"),
    path("api/employees/<int:employment_id>/update/", employees_api.update_employee_profile, name="employee-update"),
    path("api/employees/<int:employment_id>/dependents/", employees_api.employee_dependents, name="employee-dependents"),
    path("api/employees/<int:employment_id>/contacts/", employees_api.employee_contacts, name="employee-contacts"),
    path("api/me/editable-fields/", leaves_api.my_editable_fields, name="my-editable-fields"),
    # الإنابة أثناء الغياب (ق-75)
    path("api/me/deputies/", leaves_api.eligible_deputies_view, name="eligible-deputies"),
    path("api/me/delegations/", leaves_api.my_delegations, name="my-delegations"),
    # الإشعارات — جرس المستخدم
    path("api/me/notifications/", notifications_api.my_notifications, name="my-notifications"),
    path("api/me/notifications/read/", notifications_api.mark_read, name="notifications-read"),
    path("api/delegations/<int:delegation_id>/decide/", leaves_api.decide_delegation_view, name="delegation-decide"),
    # إلغاء الطلب — لمقدّمه قبل أول قرار (ق-81)
    path("api/requests/<int:request_id>/cancel/", leaves_api.cancel_request_view, name="request-cancel"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]


