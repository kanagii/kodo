from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.landing.urls")),
    path("", include("apps.login.urls")),
    path("", include("apps.register.urls")),
    path("", include("apps.profile.urls")),
    path("", include("apps.settings.urls")),
]
