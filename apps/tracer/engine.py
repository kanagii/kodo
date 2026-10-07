# apps/tracer/engine.py
"""
Kodo's trace engine.

Executes a submitted Python snippet and records, for every executed line,
which line ran, what the local variables looked like right after that line
finished, and anything print() wrote during that line. Capturing happens
"post-execution" (buffer the pending line, flush it on the next line event
or on return/exception) so the very last line in a function — including a
bare `return` — gets its own correctly-timed step instead of being missed.

SECURITY NOTE — read before exposing this anywhere beyond your own machine:
This runs user-submitted code with exec(). The restricted builtins list
below blocks the obvious dangerous calls (no open, no __import__, no os/sys
access), and a step cap + time cap stop runaway infinite loops from hanging
the server. This is a reasonable safeguard for trusted, small-scale use
(you, plus a couple of classmates testing locally) — it is NOT a real
sandbox. Do not deploy this as a public-facing endpoint without running
traced code in an isolated subprocess or container instead.
"""

import sys
import time
import json


MAX_STEPS = 500
MAX_SECONDS = 3
MAX_OUTPUT_CHARS = 10000
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
    steps: list of {"line_number": int, "variables": {...}, "structure": {...} | None, "output": str}
    error_message: None on a clean run, else a short description.
    """
    steps = []
    start_time = time.time()
    pending = {}        # id(frame) -> line number whose post-state we're waiting to capture
    output_buffer = []  # text printed since the last flush, across all frames
    output_total_len = [0]  # mutable counter (list so the closure below can update it)

    def captured_print(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(a) for a in args) + end
        output_total_len[0] += len(text)
        if output_total_len[0] > MAX_OUTPUT_CHARS:
            raise TraceLimitExceeded("Too much output printed — stopped to avoid overload.")
        output_buffer.append(text)

    def flush(frame):
        line = pending.pop(id(frame), None)
        if line is not None:
            output_text = "".join(output_buffer)
            output_buffer.clear()
            steps.append({
                "line_number": line,
                "variables": _snapshot_variables(frame.f_locals),
                "structure": _guess_structure_snapshot(frame.f_locals),
                "output": output_text,
            })

    safe_builtins = {
        "range": range, "len": len, "int": int, "float": float,
        "str": str, "list": list, "dict": dict, "set": set,
        "tuple": tuple, "bool": bool, "min": min, "max": max,
        "sum": sum, "sorted": sorted, "enumerate": enumerate,
        "zip": zip, "abs": abs, "isinstance": isinstance,
        "print": captured_print,
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
            flush(frame)
            pending[id(frame)] = frame.f_lineno

        elif event in ("return", "exception"):
            flush(frame)

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