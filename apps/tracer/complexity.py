# apps/tracer/complexity.py
"""
Kodo's Big-O estimator.

Reads the *structure* of a submitted snippet (loops, recursion, allocations)
and returns an estimate: (time_label, space_label), e.g. ("O(n^2)", "O(1)").

This is a heuristic, not a proof. It cannot know what `n` is, what type a
variable holds, or how often a function is called, so treat the result as
"what the code's shape suggests". Space means *extra* space the code
allocates, not the input itself. Anything it cannot parse returns ("", "").
"""

import ast

# A "context" is (deg, logs): a statement runs about n**deg * (log n)**logs times.
# A "cost" is (exp, deg, logs); exp=1 means exponential and beats any polynomial.
NONE = (0, 0, 0)
ZERO = (0, 0)

GROW_CALLS = {"append", "add", "appendleft", "push"}
EXTEND_CALLS = {"extend", "update"}
SEARCH_CALLS = {"index", "count", "remove", "insert"}
LINEAR_BUILTINS = {"sum", "min", "max", "any", "all", "list", "set", "tuple", "dict", "reversed"}
COPY_BUILTINS = {"list", "set", "tuple", "dict", "sorted", "reversed"}


# --- small helpers ----------------------------------------------------------

def _ctx_add(ctx, deg=0, logs=0):
    return (ctx[0] + deg, ctx[1] + logs)


def _num(node):
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    )


def _label(cost):
    exp, deg, logs = cost
    if exp:
        return "O(2^n)"
    if deg == 0 and logs == 0:
        return "O(1)"
    parts = []
    if deg == 1:
        parts.append("n")
    elif deg > 1:
        parts.append(f"n^{deg}")
    if logs == 1:
        parts.append("log n")
    elif logs > 1:
        parts.append(f"log^{logs} n")
    return "O(" + " ".join(parts) + ")"


def _scales(node):
    """Does this expression halve, double or otherwise scale a value?"""
    for n in ast.walk(node):
        if not (isinstance(n, ast.BinOp) and isinstance(n.op, (ast.FloorDiv, ast.Div, ast.RShift, ast.LShift, ast.Mult))):
            continue
        if isinstance(n.op, (ast.RShift, ast.LShift)):
            if _num(n.right) and n.right.value >= 1:
                return True
        elif isinstance(n.op, ast.Mult):
            if any(_num(side) and side.value >= 2 for side in (n.left, n.right)):
                return True
        elif _num(n.right) and n.right.value >= 2:
            return True
    return False


def _aug_scales(node):
    if not _num(node.value):
        return False
    if isinstance(node.op, (ast.RShift, ast.LShift)):
        return node.value.value >= 1
    if isinstance(node.op, (ast.FloorDiv, ast.Div, ast.Mult)):
        return node.value.value >= 2
    return False


def _while_is_log(node):
    """True for loops that halve/double their way to the end (binary search,
    `while n > 0: n //= 2`, `while i < n: i *= 2`)."""
    test_names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
    scaled = set()
    for stmt in node.body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name) and _aug_scales(sub):
                scaled.add(sub.target.id)
            elif isinstance(sub, ast.Assign) and _scales(sub.value):
                scaled.update(t.id for t in sub.targets if isinstance(t, ast.Name))
    if scaled & test_names:
        return True
    # binary-search shape: lo/hi are moved using a halved value such as mid
    for stmt in node.body:
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Assign):
                targets = {t.id for t in sub.targets if isinstance(t, ast.Name)}
                used = {n.id for n in ast.walk(sub.value) if isinstance(n, ast.Name)}
                if targets & test_names and used & scaled:
                    return True
    return False


def _for_adds_n(node):
    it = node.iter
    if isinstance(it, (ast.List, ast.Tuple, ast.Set, ast.Constant)):
        return False
    if (
        isinstance(it, ast.Call)
        and isinstance(it.func, ast.Name)
        and it.func.id == "range"
        and it.args
        and all(isinstance(a, ast.Constant) for a in it.args)
    ):
        return False
    return True


def _comp_depth(node):
    """Nesting depth of comprehensions / generator expressions (time)."""
    best = max((_comp_depth(c) for c in ast.iter_child_nodes(node)), default=0)
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return len(node.generators) + best
    return best


def _alloc_depth(node):
    """How many n-sized layers of new memory this expression builds (space)."""
    best = max((_alloc_depth(c) for c in ast.iter_child_nodes(node)), default=0)
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp)):
        return len(node.generators) + best
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        sides = (node.left, node.right)
        if any(isinstance(s, ast.List) for s in sides) and not all(isinstance(s, (ast.List, ast.Constant)) for s in sides):
            return 1 + best
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        return 1 + best
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in COPY_BUILTINS | {"sorted"}
        and node.args
        and not isinstance(node.args[0], ast.Constant)
    ):
        return 1 + best
    return best


# --- recursion --------------------------------------------------------------

def _is_self_call(call, name):
    f = call.func
    if isinstance(f, ast.Name):
        return f.id == name
    return (
        isinstance(f, ast.Attribute)
        and f.attr == name
        and isinstance(f.value, ast.Name)
        and f.value.id in ("self", "cls")
    )


def _self_calls(fn):
    return [n for n in ast.walk(fn) if isinstance(n, ast.Call) and _is_self_call(n, fn.name)]


def _count_expr(node, name):
    return sum(1 for n in ast.walk(node) if isinstance(n, ast.Call) and _is_self_call(n, name))


def _terminates(body):
    return bool(body) and isinstance(body[-1], (ast.Return, ast.Raise))


def _count_block(stmts, name):
    total = 0
    for i, s in enumerate(stmts):
        if isinstance(s, ast.If) and _terminates(s.body):
            # when the if-branch returns, the code after it is the "else" path
            rest = _count_block(s.orelse, name) + _count_block(stmts[i + 1:], name)
            return total + _count_expr(s.test, name) + max(_count_block(s.body, name), rest)
        total += _count_stmt(s, name)
    return total


def _count_stmt(s, name):
    """Recursive calls made per invocation: only one branch of an if runs,
    and a call inside a loop runs repeatedly."""
    if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return 0
    if isinstance(s, ast.If):
        return _count_expr(s.test, name) + max(_count_block(s.body, name), _count_block(s.orelse, name))
    if isinstance(s, (ast.For, ast.While)):
        head = s.iter if isinstance(s, ast.For) else s.test
        return _count_expr(head, name) + (2 if _count_block(s.body, name) else 0) + _count_block(s.orelse, name)
    if isinstance(s, ast.Try):
        handlers = sum(_count_block(h.body, name) for h in s.handlers)
        return _count_block(s.body, name) + handlers + _count_block(s.orelse, name) + _count_block(s.finalbody, name)
    if isinstance(s, ast.With):
        return sum(_count_expr(i.context_expr, name) for i in s.items) + _count_block(s.body, name)
    return _count_expr(s, name)


def _args_of(call):
    return list(call.args) + [k.value for k in call.keywords]


def _call_halves(call):
    for a in _args_of(call):
        if _scales(a):
            return True
        for n in ast.walk(a):
            if isinstance(n, ast.Name) and ("mid" in n.id.lower() or "half" in n.id.lower()):
                return True
    return False


def _has_attribute_arg(call):
    return any(isinstance(n, ast.Attribute) for a in _args_of(call) for n in ast.walk(a))


def _has_arithmetic_arg(call):
    return any(isinstance(n, ast.BinOp) for a in _args_of(call) for n in ast.walk(a))


def _calls_in_collection_loops(fn):
    """Recursive calls made once per item of a collection (graph/tree walks)."""
    found = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.For):
            it = n.iter
            is_range = isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "range"
            if not is_range:
                for sub in ast.walk(n):
                    if isinstance(sub, ast.Call) and _is_self_call(sub, fn.name):
                        found.add(id(sub))
    return found


def _recursion(fn, memoised):
    calls = _self_calls(fn)
    if not calls:
        return None
    count = max(1, _count_block(fn.body, fn.name))
    in_loops = _calls_in_collection_loops(fn)
    structural = all(id(c) in in_loops or _has_attribute_arg(c) for c in calls)
    halving = any(_call_halves(c) for c in calls)
    divide = count >= 2 and not any(_has_arithmetic_arg(c) or _has_attribute_arg(c) for c in calls)

    plain_linear = False
    if structural:
        time, space = (0, 1, 0), (0, 1, 0)
    elif count == 1:
        if halving:
            time, space = (0, 0, 1), (0, 0, 1)
        else:
            time, space, plain_linear = (0, 1, 0), (0, 1, 0), True
    elif halving or divide:
        time, space = (0, 1, 1), (0, 1, 0)
    elif memoised:
        time, space = (0, 1, 0), (0, 1, 0)
    else:
        time, space = (1, 0, 0), (0, 1, 0)
    return time, space, plain_linear


# --- the analyzer -----------------------------------------------------------

class _Analyzer:
    def __init__(self):
        self.time = NONE
        self.space = NONE
        self.dicts = set()   # names known to hold a dict (so d[k] = v grows memory)

    def _t(self, ctx):
        self.time = max(self.time, (0, ctx[0], ctx[1]))

    def _s(self, ctx):
        self.space = max(self.space, (0, ctx[0], ctx[1]))

    def block(self, stmts, ctx):
        for s in stmts:
            self.stmt(s, ctx)

    def stmt(self, s, ctx):
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.function(s)
        elif isinstance(s, ast.ClassDef):
            self.block(s.body, ZERO)
        elif isinstance(s, ast.For):
            self.scan(s.iter, ctx)
            inner = _ctx_add(ctx, 1) if _for_adds_n(s) else ctx
            self._t(inner)
            self.block(s.body, inner)
            self.block(s.orelse, ctx)
        elif isinstance(s, ast.While):
            self.scan(s.test, ctx)
            inner = _ctx_add(ctx, 0, 1) if _while_is_log(s) else _ctx_add(ctx, 1)
            self._t(inner)
            self.block(s.body, inner)
            self.block(s.orelse, ctx)
        elif isinstance(s, ast.If):
            self.scan(s.test, ctx)
            self.block(s.body, ctx)
            self.block(s.orelse, ctx)
        elif isinstance(s, ast.Try):
            self.block(s.body, ctx)
            for h in s.handlers:
                self.block(h.body, ctx)
            self.block(s.orelse, ctx)
            self.block(s.finalbody, ctx)
        elif isinstance(s, ast.With):
            self.block(s.body, ctx)
        else:
            self.scan(s, ctx)

    def scan(self, node, ctx):
        # remember dict-like names so later d[k] = v counts as growth
        for n in ast.walk(node):
            if isinstance(n, ast.Assign) and (
                isinstance(n.value, (ast.Dict, ast.DictComp))
                or (isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "dict")
            ):
                self.dicts.update(t.id for t in n.targets if isinstance(t, ast.Name))

        # ---- time ----
        t = _ctx_add(ctx, _comp_depth(node))
        for n in ast.walk(node):
            if not isinstance(n, ast.Call):
                continue
            name = n.func.id if isinstance(n.func, ast.Name) else None
            attr = n.func.attr if isinstance(n.func, ast.Attribute) else None
            if attr == "sort" or name == "sorted":
                t = max(t, _ctx_add(ctx, 1, 1))
            elif name in LINEAR_BUILTINS and len(n.args) == 1 and not isinstance(n.args[0], ast.Constant):
                t = max(t, _ctx_add(ctx, 1))
            elif attr in SEARCH_CALLS:
                t = max(t, _ctx_add(ctx, 1))
            elif attr == "pop" and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 0:
                t = max(t, _ctx_add(ctx, 1))
        self._t(t)

        # ---- space ----
        alloc = _alloc_depth(node)
        if alloc:
            self._s(_ctx_add(ctx, alloc))
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr in GROW_CALLS:
                    self._s(ctx)
                elif n.func.attr in EXTEND_CALLS:
                    self._s(_ctx_add(ctx, 1))
            elif isinstance(n, (ast.Assign, ast.AugAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for tg in targets:
                    if isinstance(tg, ast.Subscript) and isinstance(tg.value, ast.Name) and tg.value.id in self.dicts:
                        self._s(ctx)

    def function(self, fn):
        # dict defaults such as memo={} make this function's d[k] = v grow memory
        a = fn.args
        positional = a.posonlyargs + a.args
        for arg, default in zip(positional[len(positional) - len(a.defaults):], a.defaults):
            if isinstance(default, ast.Dict):
                self.dicts.add(arg.arg)

        sub = _Analyzer()
        sub.dicts = self.dicts
        sub.block(fn.body, ZERO)
        time, space = sub.time, sub.space

        memoised = any(isinstance(n, ast.Name) and n.id in self.dicts for n in ast.walk(fn))
        rec = _recursion(fn, memoised)
        if rec:
            rec_time, rec_space, plain_linear = rec
            if plain_linear and time[0] == 0:
                # linear recursion that also loops: the loop runs once per level
                rec_time = (0, rec_time[1] + time[1], rec_time[2] + time[2])
            time = max(time, rec_time)
            space = max(space, rec_space)

        self.time = max(self.time, time)
        self.space = max(self.space, space)


def estimate_complexity(source_code):
    """Return (time_label, space_label), or ("", "") if the code can't be read."""
    try:
        tree = ast.parse(source_code)
        analyzer = _Analyzer()
        analyzer.block(tree.body, ZERO)
    except (SyntaxError, ValueError, RecursionError):
        return "", ""
    return _label(analyzer.time), _label(analyzer.space)
