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
import types


MAX_STEPS = 500
MAX_SECONDS = 3
MAX_OUTPUT_CHARS = 10000
TRACE_FILENAME = "<kodo_trace>"
MAX_NODES = 50  # cap on nodes recorded per step so snapshots stay small

# Attribute names students commonly use for a node's link and payload.
NEXT_ATTRS = ("next", "nxt", "link")
VALUE_ATTRS = ("value", "val", "data", "key", "item", "element")

_NOT_NODES = (
    type, types.FunctionType, types.BuiltinFunctionType, types.ModuleType,
    str, bytes, int, float, bool, list, tuple, dict, set,
)


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


def _next_attr(obj):
    """Name of the attribute that links to the next node, or None if obj
    isn't node-like (works for the provided Node and student-written ones)."""
    if obj is None or isinstance(obj, _NOT_NODES):
        return None
    for name in NEXT_ATTRS:
        if hasattr(obj, name):
            return name
    return None


def _walk(start, limit=MAX_NODES):
    """Yield nodes from start along the next links; stops at None, at a
    cycle, or at the limit."""
    seen = set()
    node = start
    while node is not None and id(node) not in seen and len(seen) < limit:
        attr = _next_attr(node)
        if attr is None:
            break
        seen.add(id(node))
        yield node
        node = getattr(node, attr, None)


def _node_value(node):
    for name in VALUE_ATTRS:
        if hasattr(node, name):
            raw = getattr(node, name)
            break
    else:
        raw = None
        for key, val in getattr(node, "__dict__", {}).items():
            if key not in NEXT_ATTRS:
                raw = val
                break
    if _next_attr(raw) is not None:
        return repr(raw)
    return _json_safe(raw)


def _list_head(obj):
    """For wrapper classes like `class LinkedList: self.head = ...`:
    returns (head_node_or_None, True) if obj looks like one, else (None, False)."""
    if obj is None or isinstance(obj, _NOT_NODES) or _next_attr(obj) is not None:
        return None, False
    if hasattr(obj, "head"):
        head = getattr(obj, "head")
        if head is None or _next_attr(head) is not None:
            return head, True
    return None, False


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if _next_attr(value) is not None:
            return [_node_value(n) for n in _walk(value)]
        head, is_wrapper = _list_head(value)
        if is_wrapper:
            return [_node_value(n) for n in _walk(head)]
        return repr(value)


def _hidden(value):
    """Classes, functions and modules are clutter in the variables panel."""
    return isinstance(value, (type, types.FunctionType, types.ModuleType))


def _snapshot_variables(locals_dict):
    return {
        key: _json_safe(value)
        for key, value in locals_dict.items()
        if not key.startswith("__") and not _hidden(value)
    }


def _linked_list_snapshot(locals_dict):
    """Returns (label, snapshot) when any local is a node (or a list wrapper
    holding one), else None. The snapshot lists every chain of nodes, which
    variable points at which node, and which variables are None."""
    named = []       # (variable label, node)
    null_ptrs = []
    for key, value in locals_dict.items():
        if key.startswith("__"):
            continue
        if _next_attr(value) is not None:
            named.append((key, value))
            continue
        head, is_wrapper = _list_head(value)
        if is_wrapper:
            if head is None:
                null_ptrs.append(key + ".head")
            else:
                named.append((key + ".head", head))
        elif value is None:
            null_ptrs.append(key)
    if not named:
        return None

    ptrs = {}
    for name, node in named:
        ptrs.setdefault(id(node), []).append(name)

    nodes = {}  # every node reachable from a variable, in discovery order
    for _, node in named:
        for n in _walk(node):
            if len(nodes) >= MAX_NODES:
                break
            nodes.setdefault(id(n), n)

    pointed_to = set()
    for n in nodes.values():
        nxt = getattr(n, _next_attr(n), None)
        if nxt is not None and id(nxt) in nodes:
            pointed_to.add(id(nxt))

    chains = []
    visited = set()

    def build_chain(start):
        items, index = [], {}
        tail, cycle_to = "none", None
        node = start
        while node is not None:
            nid = id(node)
            if nid in index:
                tail, cycle_to = "cycle", index[nid]
                break
            if nid in visited:
                tail = "shared"
                break
            attr = _next_attr(node)
            if attr is None:
                break
            if len(items) >= MAX_NODES:
                tail = "truncated"
                break
            index[nid] = len(items)
            visited.add(nid)
            items.append({"v": _node_value(node), "ptrs": ptrs.get(nid, [])})
            node = getattr(node, attr, None)
        chains.append({"nodes": items, "tail": tail, "cycle_to": cycle_to})

    for nid, n in nodes.items():          # real heads first
        if nid not in pointed_to and nid not in visited:
            build_chain(n)
    for nid, n in nodes.items():          # then anything left (pure cycles)
        if nid not in visited:
            build_chain(n)

    names = [name for name, _ in named]
    label = "head" if "head" in names else names[0]
    return label, {"kind": "linked_list", "chains": chains, "null_ptrs": null_ptrs}


def _guess_structure_snapshot(locals_dict):
    linked = _linked_list_snapshot(locals_dict)
    if linked is not None:
        label, snapshot = linked
        return {label: snapshot}
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
        # needed so students can write their own `class Node:` / `class LinkedList:`
        "__build_class__": __build_class__, "object": object, "super": super,
        "Exception": Exception, "ValueError": ValueError, "IndexError": IndexError,
        "KeyError": KeyError, "TypeError": TypeError,
    }

    # One shared namespace (not separate globals/locals) so functions and
    # classes defined in the snippet can see each other, e.g. a student's own
    # Node used inside their own append() function.
    exec_globals = {"__builtins__": safe_builtins, "__name__": "__kodo__", "Node": Node}

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
        exec(compiled, exec_globals)
    except TraceLimitExceeded as e:
        error_message = str(e)
    except Exception as e:
        error_message = f"{type(e).__name__}: {e}"
    finally:
        sys.settrace(None)

    return steps, error_message