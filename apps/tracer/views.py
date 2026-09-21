# apps/tracer/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Snippet, TraceSession, TraceStep, DATA_STRUCTURE_CHOICES, COMPLEXITY_CHOICES
from .engine import run_traced_code


@login_required
def editor(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip() or "Untitled snippet"
        code = request.POST.get("code", "")
        data_structure = request.POST.get("data_structure", "")
        predicted_time = request.POST.get("predicted_time", "")
        predicted_space = request.POST.get("predicted_space", "")

        if not code.strip():
            messages.error(request, "Paste some code first.")
            return render(request, "tracer/editor.html", {
                "data_structure_choices": DATA_STRUCTURE_CHOICES,
                "complexity_choices": COMPLEXITY_CHOICES,
            })

        snippet = Snippet.objects.create(
            user=request.user,
            title=title,
            code=code,
            data_structure=data_structure,
        )

        steps, error_message = run_traced_code(code)

        session = TraceSession.objects.create(
            snippet=snippet,
            predicted_time_complexity=predicted_time,
            predicted_space_complexity=predicted_space,
            operation_count=len(steps),
            error_message=error_message or "",
        )

        TraceStep.objects.bulk_create([
            TraceStep(
                trace_session=session,
                step_number=i + 1,
                line_number=step["line_number"],
                variables_snapshot=step["variables"],
                structure_snapshot=step["structure"],
            )
            for i, step in enumerate(steps)
        ])

        if error_message:
            messages.error(request, f"Trace finished with an error: {error_message}")
        else:
            messages.success(request, f"Traced {len(steps)} steps.")

        return redirect("tracer_session_detail", session_id=session.id)

    return render(request, "tracer/editor.html", {
        "data_structure_choices": DATA_STRUCTURE_CHOICES,
        "complexity_choices": COMPLEXITY_CHOICES,
    })


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(
        TraceSession, id=session_id, snippet__user=request.user
    )
    steps = session.steps.all()
    return render(request, "tracer/session_detail.html", {
        "session": session,
        "steps": steps,
    })


@login_required
def history(request):
    sessions = (
        TraceSession.objects
        .filter(snippet__user=request.user)
        .select_related("snippet")
        .order_by("-traced_at")
    )
    return render(request, "tracer/history.html", {"sessions": sessions})
