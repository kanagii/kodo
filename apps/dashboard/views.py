# apps/dashboard/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# TEMP: hardcoded sample data so the screen can be built first.
# Replace with real queries on tracer.Code / TraceSession later,
# keeping the same keys so the template doesn't change.
SAMPLE = {
    "stats": {
        "traces": 24,
        "snippets": 17,
        "saved": 5,
        "accuracy": 67,
    },
    "accuracy": {
        "time": {"correct": 4, "total": 6, "pct": 67},
        "space": {"correct": 5, "total": 6, "pct": 83},
    },
    "by_structure": [
        {"label": "Arrays", "count": 12, "pct": 100},
        {"label": "Linked Lists", "count": 5, "pct": 42},
        {"label": "Stacks", "count": 3, "pct": 25},
        {"label": "Trees", "count": 2, "pct": 17},
    ],
    "recent_traces": [
        {"title": "Linear search", "structure": "Array", "ops": 9, "when": "Nov 10, 16:34", "error": False},
        {"title": "Reverse linked list", "structure": "Linked List", "ops": 31, "when": "Nov 10, 14:02", "error": False},
        {"title": "Stack push/pop", "structure": "Stack", "ops": 0, "when": "Nov 9, 21:15", "error": True},
        {"title": "Bubble sort", "structure": "Array", "ops": 148, "when": "Nov 9, 19:48", "error": False},
        {"title": "BST insert", "structure": "Tree", "ops": 22, "when": "Nov 8, 11:20", "error": False},
    ],
    "saved_sessions": [
        {"title": "Binary search", "structure": "Array", "time": "O(log n)"},
        {"title": "Bubble sort", "structure": "Array", "time": "O(n^2)"},
        {"title": "Reverse linked list", "structure": "Linked List", "time": "O(n)"},
    ],
}


@login_required
def dashboard(request):
    return render(request, "dashboard/dashboard.html", SAMPLE)
