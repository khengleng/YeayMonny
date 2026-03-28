from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

admin.site.site_header = "Fortune Telling Administration"
admin.site.site_title = "Fortune Telling Administration"
admin.site.index_title = "Fortune Telling Administration"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", lambda request: JsonResponse({"ok": True}), name="healthz"),
    path("", include("chat.urls")),
]
