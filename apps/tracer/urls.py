# apps/tracer/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.editor, name="tracer_editor"),
    path("history/", views.history, name="tracer_history"),
    path("session/<int:session_id>/", views.session_detail, name="tracer_session_detail"),
]
