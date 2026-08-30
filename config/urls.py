from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.api.workspace import workspace
from apps.core.api import access as access_api
from apps.organization import api as org_api
from apps.core.api import billing as billing_api


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
    path("api/billing/plans/", billing_api.plan_catalog, name="plan-catalog"),
    path("api/billing/subscription/", billing_api.my_subscription, name="my-subscription"),
    path("api/billing/estimate/", billing_api.billing_estimate, name="billing-estimate"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
