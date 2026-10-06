# apps/tracer/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Code, TraceSession, TraceStep, DATA_STRUCTURE_CHOICES, COMPLEXITY_CHOICES
from .engine import run_traced_code


@login_required
def editor(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip() or "Untitled snippet"
        source_code = request.POST.get("code", "")
        data_structure = request.POST.get("data_structure", "")
        predicted_time = request.POST.get("predicted_time", "")
        predicted_space = request.POST.get("predicted_space", "")

        if not source_code.strip():
            messages.error(request, "Paste some code first.")
            return render(request, "tracer/editor.html", {
                "data_structure_choices": DATA_STRUCTURE_CHOICES,
                "complexity_choices": COMPLEXITY_CHOICES,
            })

        code_obj = Code.objects.create(
            user=request.user,
            title=title,
            source_code=source_code,
            data_structure=data_structure,
        )

        steps, error_message = run_traced_code(source_code)

        session = TraceSession.objects.create(
            code=code_obj,
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
        TraceSession, id=session_id, code__user=request.user
    )
    steps_qs = session.steps.all()

    # Serialized for the frontend player — json_script in the template
    # turns this straight into JSON the visualizer's JS can read, no
    # extra API endpoint needed.
    steps_data = [
        {
            "step_number": s.step_number,
            "line_number": s.line_number,
            "variables": s.variables_snapshot,
            "structure": s.structure_snapshot,
        }
        for s in steps_qs
    ]
    source_lines = session.code.source_code.splitlines()

    return render(request, "tracer/session_detail.html", {
        "session": session,
        "steps": steps_qs,
        "steps_data": steps_data,
        "source_lines": source_lines,
    })


@login_required
def history(request):
    sessions = (
        TraceSession.objects
        .filter(code__user=request.user)
        .select_related("code")
        .order_by("-traced_at")
    )
    return render(request, "tracer/history.html", {"sessions": sessions})