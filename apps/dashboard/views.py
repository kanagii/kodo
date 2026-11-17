# apps/dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.tracer.models import Code, TraceSession, DATA_STRUCTURE_CHOICES

STRUCTURE_LABELS = dict(DATA_STRUCTURE_CHOICES)


def _structure_label(key):
    return STRUCTURE_LABELS.get(key) or "Not specified"


def _graded(sessions, predicted_field, actual_field):
    """Guesses that can be marked right or wrong: a prediction exists AND
    Kodo has recorded an actual complexity. actual_* is not computed yet,
    so until that feature exists total stays 0 and the page shows a dash."""
    pairs = list(
        sessions.exclude(**{predicted_field: ""})
        .exclude(**{actual_field: ""})
        .values_list(predicted_field, actual_field)
    )
    total = len(pairs)
    correct = sum(1 for predicted, actual in pairs if predicted == actual)
    pct = round(correct * 100 / total) if total else None
    return {"correct": correct, "total": total, "pct": pct}


@login_required
def dashboard(request):
    sessions = TraceSession.objects.filter(code__user=request.user)

    counts = sessions.aggregate(
        traces=Count("id"),
        saved=Count("id", filter=Q(is_saved=True)),
    )
    snippets = Code.objects.filter(user=request.user).count()
    guesses_made = sessions.exclude(predicted_time_complexity="").count()

    time_acc = _graded(sessions, "predicted_time_complexity", "actual_time_complexity")
    space_acc = _graded(sessions, "predicted_space_complexity", "actual_space_complexity")
    total_graded = time_acc["total"] + space_acc["total"]
    total_correct = time_acc["correct"] + space_acc["correct"]
    overall_pct = round(total_correct * 100 / total_graded) if total_graded else None

    # traces per data structure, biggest first; bars are relative to the biggest
    grouped = (
        sessions.values("code__data_structure")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    biggest = max((g["n"] for g in grouped), default=0)
    by_structure = [
        {
            "label": _structure_label(g["code__data_structure"]),
            "count": g["n"],
            "pct": round(g["n"] * 100 / biggest) if biggest else 0,
        }
        for g in grouped
    ]

    recent_traces = [
        {
            "id": s.id,
            "title": s.code.title,
            "structure": _structure_label(s.code.data_structure),
            "ops": s.operation_count,
            "when": s.traced_at,
            "error": bool(s.error_message),
        }
        for s in sessions.select_related("code").order_by("-traced_at")[:5]
    ]

    saved_sessions = [
        {
            "id": s.id,
            "title": s.code.title,
            "structure": _structure_label(s.code.data_structure),
            "time": s.actual_time_complexity or s.predicted_time_complexity or "—",
        }
        for s in sessions.filter(is_saved=True).select_related("code").order_by("-traced_at")[:5]
    ]

    return render(request, "dashboard/dashboard.html", {
        "stats": {
            "traces": counts["traces"],
            "snippets": snippets,
            "saved": counts["saved"],
            "accuracy": overall_pct,
        },
        "accuracy": {"time": time_acc, "space": space_acc},
        "guesses_made": guesses_made,
        "by_structure": by_structure,
        "recent_traces": recent_traces,
        "saved_sessions": saved_sessions,
    })