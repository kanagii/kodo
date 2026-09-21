from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.landing.urls")),
    path("", include("apps.login.urls")),
    path("", include("apps.register.urls")),
    path("", include("apps.profile.urls")),
    path("", include("apps.settings.urls")),
    path("tracer/", include("apps.tracer.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
