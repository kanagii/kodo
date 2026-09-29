# apps/tracer/admin.py
from django.contrib import admin
from .models import Code, TraceSession, TraceStep

admin.site.register(Code)
admin.site.register(TraceSession)
admin.site.register(TraceStep)