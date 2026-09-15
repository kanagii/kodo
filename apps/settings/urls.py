from django.urls import path
from . import views

urlpatterns = [
    path("settings/", views.account_settings, name="settings"),
]
