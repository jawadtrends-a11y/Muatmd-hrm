from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.api.workspace import workspace
from apps.core.api import access as access_api


def health(request):
    return JsonResponse({"status": "ok", "service": "muatmd-hrm"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/me/workspace/", workspace, name="workspace"),
    path("api/access/permissions/", access_api.permission_catalog, name="perm-catalog"),
    path("api/access/roles/", access_api.role_list, name="role-list"),
    path("api/access/roles/<int:role_id>/", access_api.role_detail, name="role-detail"),
    path("api/access/roles/<int:role_id>/permissions/", access_api.role_permissions_update, name="role-perms"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
