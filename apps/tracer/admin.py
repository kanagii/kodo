# apps/tracer/admin.py
from django.contrib import admin
from .models import Snippet, TraceSession, TraceStep

admin.site.register(Snippet)
admin.site.register(TraceSession)
admin.site.register(TraceStep)
