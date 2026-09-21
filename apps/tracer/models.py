# apps/tracer/models.py
from django.contrib.auth.models import User
from django.db import models

DATA_STRUCTURE_CHOICES = [
    ("", "Not specified"),
    ("array", "Array"),
    ("linked_list", "Linked List"),
    ("stack", "Stack"),
    ("queue", "Queue"),
    ("tree", "Tree"),
    ("graph", "Graph"),
]

COMPLEXITY_CHOICES = [
    ("", "Not sure"),
    ("O(1)", "O(1) — constant"),
    ("O(log n)", "O(log n) — logarithmic"),
    ("O(n)", "O(n) — linear"),
    ("O(n log n)", "O(n log n) — linearithmic"),
    ("O(n^2)", "O(n²) — quadratic"),
    ("O(2^n)", "O(2ⁿ) — exponential"),
]


class Snippet(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="snippets")
    title = models.CharField(max_length=120)
    code = models.TextField()
    data_structure = models.CharField(max_length=20, choices=DATA_STRUCTURE_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class TraceSession(models.Model):
    snippet = models.ForeignKey(Snippet, on_delete=models.CASCADE, related_name="sessions")
    predicted_time_complexity = models.CharField(max_length=20, choices=COMPLEXITY_CHOICES, blank=True)
    predicted_space_complexity = models.CharField(max_length=20, choices=COMPLEXITY_CHOICES, blank=True)
    # Left blank for now — classifying *actual* Big-O from a raw operation
    # count reliably is genuinely hard. operation_count below is the
    # honest, simple estimate your proposal describes instead.
    actual_time_complexity = models.CharField(max_length=20, blank=True)
    actual_space_complexity = models.CharField(max_length=20, blank=True)
    operation_count = models.IntegerField(default=0)
    error_message = models.CharField(max_length=255, blank=True)
    is_saved = models.BooleanField(default=False)
    traced_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trace of {self.snippet.title} @ {self.traced_at:%Y-%m-%d %H:%M}"


class TraceStep(models.Model):
    trace_session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name="steps")
    step_number = models.IntegerField()
    line_number = models.IntegerField()
    variables_snapshot = models.JSONField(default=dict)
    # Best-effort guess at "the" data structure in play at this line —
    # reserved for the live-visualization phase, built later.
    structure_snapshot = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        ordering = ["step_number"]

    def __str__(self):
        return f"Step {self.step_number} (line {self.line_number})"
