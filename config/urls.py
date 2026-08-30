from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.api.workspace import workspace


def health(request):
    return JsonResponse({"status": "ok", "service": "muatmd-hrm"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/me/workspace/", workspace, name="workspace"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
