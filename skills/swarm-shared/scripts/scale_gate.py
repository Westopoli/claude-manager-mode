#!/usr/bin/env python3
"""scale_gate.py — /manager-mode Phase 6 gate G10.

G9 measures cyclomatic complexity, which is a readability signal and is
orthogonal to algorithmic complexity: `if item in big_list` inside a loop
scores 3 and passes clean while running in quadratic time. G10 covers that
blind spot with two AST-based halves, same ast.NodeVisitor approach the
other gates use.

  Half A — antipattern scan (every leaf). Structural shapes that turn a
  linear pass quadratic, or worse. Each finding names the outer loop it is
  nested in, because the shape is only a problem *inside* a loop.

  Half B — assertion-presence check (leaves with `scale_assertions: true`
  in their brief). Confirms the leaf's declared test files actually compare
  two input sizes and assert on a ratio. A leaf can otherwise satisfy a
  growth_claim with a test that measures one size and proves nothing about
  growth.

Both halves are advisory by default, matching G8/G9: a shape flagged here
is strong evidence but not proof — a membership test against a two-element
list inside a loop is quadratic on paper and irrelevant in practice. Pass
--strict (hardcore does) to block on findings.

Bands referenced by Half B are defined in
swarm-shared/references/test-design.md; this script only checks that a
ratio comparison exists, not that its threshold is the right one — picking
the band is the test-writer's judgment call, and Phase 3.4's auditor
reviews it.

Exit codes: 0 = pass/SKIP (no impl_files or leaf not found), 1 = findings
with --strict, 2 = usage/config error.
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_invariants as ci  # noqa: E402

# Loop-invariant work that is cheap once and quadratic per-iteration.
# Names are matched on the attribute/function only — a full type inference
# pass is out of proportion to a heuristic gate, and the false-positive
# cost is one advisory line a human reads.
_SORT_NAMES = {"sort", "sorted"}

# Split in two because method-name matching alone is not enough: `get` is
# far more often `dict.get` than an HTTP call, and flagging it produced a
# false positive in every real cascade artifact this gate was checked
# against. Names with no plausible non-IO meaning stand alone; ambiguous
# ones must also sit on a receiver that looks like a client or connection.
_IO_NAMES_ALWAYS = {
    "urlopen", "executemany", "fetchall", "fetchone", "fetchmany",
    "read_text", "write_text", "read_bytes", "write_bytes",
}
_IO_NAMES_ON_CLIENT = {
    "get", "post", "put", "patch", "delete", "head", "request",
    "execute", "query", "fetch", "send",
}
_CLIENT_HINTS = {
    "requests", "session", "client", "http", "httpx", "urllib", "conn",
    "connection", "cursor", "db", "database", "engine", "s3", "bucket",
    "api", "transport", "channel", "socket", "redis", "es",
}


def _flag(brief: ci.Brief, key: str) -> bool:
    """Read a boolean brief field.

    check_invariants' frontmatter parser returns scalars as strings, so
    `scale_assertions: true` arrives as "true", not True — comparing
    against the bool silently disables the check. Matching the tolerant
    string style _test_owned_by_leaf already uses also means a brief
    written with `yes` or `True` behaves the way its author expected.
    """
    return str(brief.frontmatter.get(key, "")).strip().lower() in {"true", "yes", "1"}


def find_brief(briefs_dir: Path, leaf_id: str) -> ci.Brief | None:
    """Duplicated from complexity_gate.py / test_quality_gate.py — no
    precedent for gate scripts importing each other (only check_invariants
    is shared), so this stays a local copy rather than introducing a new
    cross-script import."""
    for path in sorted(briefs_dir.glob("leaf-*.md")) + sorted(briefs_dir.glob("shard-*/leaf-*.md")):
        b = ci.parse_brief(path)
        if b is not None and b.leaf_id == leaf_id:
            return b
    return None


@dataclass
class Finding:
    kind: str  # "nested-loop" | "membership-in-loop" | ... | "missing-scale-assertion"
    target: str  # "<rel_path>::<func_name>" or "<rel_path>"
    reason: str


@dataclass
class Report:
    leaf_id: str
    applicable: bool
    findings: list[Finding] = field(default_factory=list)
    strict: bool = False

    def passed(self) -> bool:
        if not self.applicable or not self.findings:
            return True
        return not self.strict  # advisory-only unless --strict


def _name_of(node: ast.expr) -> str | None:
    """Best-effort identifier for a call target or iterable."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _name_of(node.func)
    if isinstance(node, ast.Subscript):
        return _name_of(node.value)
    return None


def _iter_key(node: ast.expr) -> str | None:
    """Identity for a loop's iterable, used to spot self-joins.

    `range(n)` is keyed by its arguments rather than by the name `range`,
    so `for i in range(n): for j in range(n)` reads as quadratic while
    `for i in range(3): for j in range(n)` does not. Without that, every
    pair of range-loops would flag, which is the difference between a
    useful advisory and one people learn to ignore.
    """
    if isinstance(node, ast.Call) and _name_of(node.func) == "range":
        try:
            return "range(" + ", ".join(ast.unparse(a) for a in node.args) + ")"
        except Exception:  # unparse is best-effort; fall through to the name
            return None
    return _name_of(node)


def _is_bounded_iter(node: ast.expr) -> bool:
    """True when the loop runs a fixed number of times regardless of input.

    Covers the two shapes that show up in practice: iterating a literal
    collection of constants (`for f in ("items", "region"):`) and
    `range(<int literal>)`.
    """
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(isinstance(e, ast.Constant) for e in node.elts)
    if isinstance(node, ast.Call) and _name_of(node.func) == "range":
        return all(
            isinstance(a, ast.Constant) and isinstance(a.value, int)
            for a in node.args)
    return False


class _ScaleVisitor(ast.NodeVisitor):
    """Walks one function, tracking enclosing-loop depth.

    Every check here is conditioned on being inside at least one loop —
    sorting once is fine, sorting per iteration is not. Tracking the
    enclosing iterables as well lets the nested-loop check distinguish
    `for a in xs: for b in ys:` (an intentional cross-product) from
    `for a in xs: for b in xs:` (a self-join, the classic accidental
    quadratic).
    """

    def __init__(
        self,
        str_names: frozenset[str] = frozenset(),
        hashed_names: frozenset[str] = frozenset(),
    ) -> None:
        self.findings: list[tuple[str, str]] = []  # (kind, reason)
        # (iterable key, is_bounded) per enclosing loop, outermost first
        self._loops: list[tuple[str | None, bool]] = []
        self._str_names = str_names  # locals initialised to a str literal
        self._hashed_names = hashed_names  # locals bound to a set/dict

    @property
    def _in_loop(self) -> bool:
        """True only when some enclosing loop actually scales with input.

        Work repeated a fixed number of times is not a scaling problem, so
        a loop over a literal tuple of four field names — or `range(3)` —
        does not make its body suspicious. Requiring at least one unbounded
        enclosing loop removed the last false positives this gate produced
        against real cascade artifacts.
        """
        return any(not bounded for _, bounded in self._loops)

    def _visit_loop(
        self,
        header: ast.expr,
        body: list[ast.stmt],
        orelse: list[ast.stmt],
        key: str | None,
        bounded: bool,
    ) -> None:
        # The header is visited at the OUTER depth on purpose: `for p in
        # sorted(a) + sorted(b):` evaluates those sorts once, before the
        # loop runs, so charging them to the loop body reported every such
        # iteration as a per-iteration re-sort. A `while` condition does
        # re-evaluate each pass, but treating it the same way keeps the
        # rule one sentence long and only loses findings on a shape that
        # is rare in leaf impl code.
        self.visit(header)
        if not bounded and key is not None and any(
                k == key and not b for k, b in self._loops):
            self.findings.append((
                "nested-loop",
                f"loop over `{key}` is nested inside another loop over the "
                f"same collection — quadratic in len({key})"))
        self._loops.append((key, bounded))
        for stmt in list(body) + list(orelse):
            self.visit(stmt)
        self._loops.pop()

    def visit_For(self, node: ast.For) -> None:
        self._visit_loop(node.iter, node.body, node.orelse,
                         _iter_key(node.iter), _is_bounded_iter(node.iter))

    def visit_While(self, node: ast.While) -> None:
        self._visit_loop(node.test, node.body, node.orelse, None, False)

    def visit_Compare(self, node: ast.Compare) -> None:
        # `x in some_list` inside a loop — O(n) lookup per iteration.
        # A set/dict/frozenset literal is O(1), so only flag list/tuple
        # literals and bare names (which we cannot type-infer, hence
        # advisory).
        if self._in_loop:
            for op, cmp in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.In, ast.NotIn)):
                    continue
                if isinstance(cmp, (ast.Set, ast.SetComp, ast.Dict, ast.DictComp)):
                    continue  # hash lookup, already O(1)
                name = _name_of(cmp)
                if name in self._hashed_names:
                    continue  # local bound to a set/dict/frozenset upstream
                word = "not in" if isinstance(op, ast.NotIn) else "in"
                self.findings.append((
                    "membership-in-loop",
                    f"`{word} {name or '<expr>'}` inside a loop — linear "
                    f"scan per iteration; use a set or dict if "
                    f"`{name or 'it'}` is a list or tuple"))
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # `s += chunk` in a loop is quadratic for immutable sequences: each
        # concatenation copies the accumulated prefix. Gated on the target
        # having been initialised to a string literal in this function,
        # because the identical AST shape is also the most common numeric
        # accumulator (`total += price`) and flagging that would drown the
        # real finding.
        if self._in_loop and isinstance(node.op, ast.Add):
            target = _name_of(node.target)
            if target in self._str_names:
                self.findings.append((
                    "concat-in-loop",
                    f"`{target} += ...` inside a loop copies the accumulated "
                    f"prefix each pass — collect into a list and join once"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._in_loop:
            name = _name_of(node.func)
            recv = node.func.value if isinstance(node.func, ast.Attribute) else None
            recv_name = (_name_of(recv) or "").lower() if recv is not None else ""
            if name in _SORT_NAMES:
                self.findings.append((
                    "sort-in-loop",
                    f"`{name}()` called inside a loop — re-sorts on every "
                    f"iteration; sort once before the loop"))
            elif name in _IO_NAMES_ALWAYS or (
                    name in _IO_NAMES_ON_CLIENT and recv_name in _CLIENT_HINTS):
                self.findings.append((
                    "io-in-loop",
                    f"`{name}()` inside a loop — one round trip per item "
                    f"(the N+1 pattern); batch the call outside the loop"))
        self.generic_visit(node)


def _typed_locals_module(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """Same as _typed_locals, but only module-level (non-nested) assignments."""
    top = ast.Module(body=[s for s in tree.body if isinstance(s, ast.Assign)],
                     type_ignores=[])
    return _typed_locals(top)


def _walk_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


_HASHED_CTORS = {"set", "dict", "frozenset", "Counter", "defaultdict", "OrderedDict"}


def _is_hashed_expr(v: ast.expr) -> bool:
    """True when `v` evaluates to something with O(1) membership."""
    if isinstance(v, (ast.Set, ast.SetComp, ast.Dict, ast.DictComp)):
        return True
    if isinstance(v, ast.Call):
        if _name_of(v.func) in _HASHED_CTORS:
            return True
        # `order.get("approvals", set())` / `.setdefault(k, {})` — the
        # default argument is what types the result when the key is absent,
        # and this idiom is common enough in real briefs that ignoring it
        # produced false membership findings on live artifacts.
        if _name_of(v.func) in {"get", "setdefault"} and len(v.args) == 2:
            return _is_hashed_expr(v.args[1])
    return False


def _typed_locals(
    scope: ast.AST,
) -> tuple[frozenset[str], frozenset[str]]:
    """(names bound to a str literal, names bound to a set/dict).

    Both exist for the same reason: by the time a name is used inside the
    loop it is just an ast.Name, so the literal that would have identified
    its type is several statements away. Without this pass, `out = ""`
    followed by `out += x` is indistinguishable from a numeric accumulator,
    and `seen = {...}` followed by `x in seen` looks like a linear scan —
    the latter false-fired on every real artifact this gate was tested on.

    Deliberately shallow: single-assignment, literal or known constructor,
    anywhere in the function. Reassignment to a different type is not
    tracked, which biases toward silence rather than a wrong finding.
    """
    strs: set[str] = set()
    hashed: set[str] = set()
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign):
            continue
        v = node.value
        is_str = isinstance(v, ast.JoinedStr) or (
            isinstance(v, ast.Constant) and isinstance(v.value, str))
        is_hashed = _is_hashed_expr(v)
        if not (is_str or is_hashed):
            continue
        for t in node.targets:
            n = _name_of(t)
            if not n:
                continue
            (strs if is_str else hashed).add(n)
    return frozenset(strs), frozenset(hashed)


def check_antipatterns(staging_dir: Path, impl_paths: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for rel in impl_paths:
        p = staging_dir / rel
        if not p.exists():
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        # Module-level bindings count: a CATALOG dict defined at import time
        # is the most natural place for the O(1) lookup table a function
        # then uses, and scoping the scan to the function body alone made
        # every such lookup look linear.
        mod_strs, mod_hashed = _typed_locals_module(tree)
        for fn in _walk_functions(tree):
            fn_strs, fn_hashed = _typed_locals(fn)
            v = _ScaleVisitor(mod_strs | fn_strs, mod_hashed | fn_hashed)
            for stmt in fn.body:
                v.visit(stmt)
            for kind, reason in v.findings:
                findings.append(Finding(kind, f"{rel}::{fn.name}", reason))
    return findings


class _RatioVisitor(ast.NodeVisitor):
    """Detects a growth assertion: a comparison whose left side is a
    division. That is the shape test-design.md prescribes
    (`ops(2N) / ops(N) < 3.0`), and it is what distinguishes a growth
    assertion from a single-size measurement."""

    def __init__(self) -> None:
        self.found = False

    def visit_Compare(self, node: ast.Compare) -> None:
        left = node.left
        if isinstance(left, ast.BinOp) and isinstance(left.op, ast.Div):
            self.found = True
        self.generic_visit(node)


def check_scale_assertions(staging_dir: Path, test_paths: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for rel in test_paths:
        p = staging_dir / rel
        if not p.exists():
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        v = _RatioVisitor()
        v.visit(tree)
        if not v.found:
            findings.append(Finding(
                "missing-scale-assertion", rel,
                "brief sets `scale_assertions: true` but this test asserts "
                "no ratio between two input sizes — a single-size "
                "measurement cannot detect a growth-rate regression; see "
                "swarm-shared/references/test-design.md"))
    return findings


def run(
    briefs_dir: Path,
    root: Path,
    leaf_id: str,
    staging_dir: Path | None,
    strict: bool,
) -> Report:
    brief = find_brief(briefs_dir, leaf_id)
    if brief is None:
        print(f"leaf `{leaf_id}` not found under {briefs_dir}", file=sys.stderr)
        return Report(leaf_id, applicable=False, strict=strict)
    impl_paths = ci._leaf_paths(brief, "impl")
    if not impl_paths:
        return Report(leaf_id, applicable=False, strict=strict)
    sdir = staging_dir or (root / ".swarm" / "pending" / leaf_id)
    if not sdir.exists():
        print(f"staging dir not found: {sdir}", file=sys.stderr)
        return Report(leaf_id, applicable=False, strict=strict)

    findings = check_antipatterns(sdir, impl_paths)
    if _flag(brief, "scale_assertions"):
        findings += check_scale_assertions(sdir, ci._leaf_paths(brief, "test"))
    return Report(leaf_id, applicable=True, findings=findings, strict=strict)


def render(rpt: Report) -> str:
    if not rpt.applicable:
        return f"{rpt.leaf_id}: SKIP (no impl_files, or leaf not found)"
    if not rpt.findings:
        return f"{rpt.leaf_id}: PASS (scale antipatterns + growth assertions)"
    lines = [
        f"{rpt.leaf_id}: {'FAIL' if rpt.strict else 'ADVISORY'}: {f.kind}: {f.target}: {f.reason}"
        for f in rpt.findings
    ]
    if rpt.strict:
        lines.append(f"--- {len(rpt.findings)} blocking finding(s), G10 blocks admission (--strict) ---")
    else:
        lines.append(f"--- {len(rpt.findings)} advisory finding(s) (non-blocking — pass --strict to block) ---")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="/manager-mode Phase 6 G10: algorithmic-scale gate")
    p.add_argument("--leaf", required=True)
    p.add_argument("--briefs-dir", type=Path)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--staging-dir", type=Path)
    p.add_argument(
        "--strict", action="store_true",
        help="block admission on findings (default: advisory-only — a "
             "flagged shape is strong evidence, not proof; use under "
             "manager-mode-hardcore, where a wrong admit is expensive "
             "enough to stop for a heuristic)")
    args = p.parse_args(argv)

    root = ci.git_root(args.root)
    cfg = ci.load_config(root)
    briefs_dir = args.briefs_dir or (root / cfg["briefs_dir"])
    if not briefs_dir.exists():
        print(f"briefs_dir not found: {briefs_dir}", file=sys.stderr)
        return 2

    rpt = run(briefs_dir, root, args.leaf, args.staging_dir, args.strict)
    print(render(rpt))
    return 0 if rpt.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
