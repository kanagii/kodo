# apps/tracer/engine.py
"""
Kodo's trace engine.

Executes a submitted Python snippet and records, for every executed line,
which line ran and what the local variables looked like at that moment.
This raw step data is what the (future) live-visualization frontend would
animate through.

SECURITY NOTE — read before exposing this anywhere beyond your own machine:
This runs user-submitted code with exec(). The restricted builtins list
below blocks the obvious dangerous calls (no open, no __import__, no os/sys
access), and a step cap + time cap stop runaway infinite loops from hanging
the server. This is a reasonable safeguard for trusted, small-scale use
(you, plus a couple of classmates testing locally) — it is NOT a real
sandbox. A determined user can likely still find ways to escape a
restricted exec() in pure Python. Do not deploy this as a public-facing
endpoint without running traced code in an isolated subprocess or
container instead.
"""

import sys
import time
import json


MAX_STEPS = 500
MAX_SECONDS = 3
TRACE_FILENAME = "<kodo_trace>"


class TraceLimitExceeded(Exception):
    pass


class Node:
    """Starter class made available to every traced snippet, matching
    Kodo's linked-list/tree exercises — no import needed in user code."""

    def __init__(self, value=None, next=None):
        self.value = value
        self.next = next

    def __repr__(self):
        return f"Node({self.value!r})"


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if isinstance(value, Node):
            out = []
            seen = set()
            node = value
            while node is not None and id(node) not in seen:
                seen.add(id(node))
                out.append(node.value)
                node = node.next
            return out
        return repr(value)


def _snapshot_variables(locals_dict):
    return {
        key: _json_safe(value)
        for key, value in locals_dict.items()
        if not key.startswith("__")
    }


def _guess_structure_snapshot(locals_dict):
    for key, value in locals_dict.items():
        if key.startswith("__"):
            continue
        if isinstance(value, (list, tuple)):
            return {key: _json_safe(value)}
    return None


def run_traced_code(source_code):
    """
    Runs source_code and returns (steps, error_message).
    steps: list of {"line_number": int, "variables": {...}, "structure": {...} | None}
    error_message: None on a clean run, else a short description.
    """
    steps = []
    start_time = time.time()

    safe_builtins = {
        "range": range, "len": len, "int": int, "float": float,
        "str": str, "list": list, "dict": dict, "set": set,
        "tuple": tuple, "bool": bool, "min": min, "max": max,
        "sum": sum, "sorted": sorted, "enumerate": enumerate,
        "zip": zip, "abs": abs, "isinstance": isinstance,
        "print": lambda *a, **k: None,
        "True": True, "False": False, "None": None,
    }

    exec_globals = {"__builtins__": safe_builtins, "Node": Node}
    exec_locals = {}

    def trace_calls(frame, event, arg):
        if frame.f_code.co_filename != TRACE_FILENAME:
            return None
        if event == "line":
            if len(steps) >= MAX_STEPS:
                raise TraceLimitExceeded(
                    f"Stopped after {MAX_STEPS} steps — likely an infinite loop."
                )
            if time.time() - start_time > MAX_SECONDS:
                raise TraceLimitExceeded(
                    f"Stopped after {MAX_SECONDS}s — likely an infinite loop."
                )
            steps.append({
                "line_number": frame.f_lineno,
                "variables": _snapshot_variables(frame.f_locals),
                "structure": _guess_structure_snapshot(frame.f_locals),
            })
        return trace_calls

    error_message = None
    try:
        compiled = compile(source_code, TRACE_FILENAME, "exec")
        sys.settrace(trace_calls)
        exec(compiled, exec_globals, exec_locals)
    except TraceLimitExceeded as e:
        error_message = str(e)
    except Exception as e:
        error_message = f"{type(e).__name__}: {e}"
    finally:
        sys.settrace(None)

    return steps, error_message
