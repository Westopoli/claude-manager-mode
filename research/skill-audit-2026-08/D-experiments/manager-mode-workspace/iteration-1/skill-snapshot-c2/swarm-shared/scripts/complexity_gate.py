#!/usr/bin/env python3
"""complexity_gate.py — /manager-mode Phase 6 gate G9, all leaves.

Two AST-based checks (same ast.NodeVisitor approach test_quality_gate.py
uses for reachability):

  1. Cyclomatic complexity per function — count decision points (if, elif,
     for, while, except, and/or short-circuit branches, ternary, +1 base).
     Flag any function over --max-cyclomatic (default 10).

  2. Max nesting depth per function — track block-nesting depth via
     NodeVisitor, incrementing on if/for/while/except/with, decrementing on
     exit. Flag any function whose deepest point exceeds --max-nesting
     (default 3 — a 4th level triggers, matching CodeClimate's
     nested-control-flow limit / Linux kernel style).

Unlike G8, runs on every leaf regardless of impl_files count — a
single-file leaf has just as much per-function complexity to measure, and
the large-single-file preference (playbook.md Sizing §3) makes single-file
leaves the MORE likely place complexity accumulates.

Both finding kinds advisory by default — a high score isn't proof of a
defect the way G8's reachability is. Pass --strict (hardcore does) to block
on findings.

Calibration, measured over experiments/scaling-test/phaseH-ceiling-search/
rungs H1-H3 (72 functions, 1583 LOC of real cascade output): cyclomatic
mean 3.1, p90 5-6, peaking at exactly 10 in two of three rungs and never
exceeding it — so max_cyclomatic=10 sits right on the natural ceiling.
Nesting never reached 3 (mean 1.0, max 2), so max_nesting=3 has never had
the chance to fire; treat it as untested rather than calibrated.

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


def find_brief(briefs_dir: Path, leaf_id: str) -> ci.Brief | None:
    """Duplicated from test_quality_gate.py — no precedent for gate scripts
    importing each other (only check_invariants is shared), so this stays
    a local 5-line copy rather than introducing a new cross-script import."""
    for path in sorted(briefs_dir.glob("leaf-*.md")) + sorted(briefs_dir.glob("shard-*/leaf-*.md")):
        b = ci.parse_brief(path)
        if b is not None and b.leaf_id == leaf_id:
            return b
    return None


@dataclass
class Finding:
    kind: str  # "cyclomatic" | "nesting"
    target: str  # "<rel_path>::<func_name>"
    value: int
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


class _ComplexityVisitor(ast.NodeVisitor):
    """One pass per function: cyclomatic count + max nesting depth."""

    def __init__(self) -> None:
        self.cyclomatic = 1  # base path
        self.max_depth = 0
        self._depth = 0

    def _enter(self) -> None:
        self._depth += 1
        self.max_depth = max(self.max_depth, self._depth)

    def _exit(self) -> None:
        self._depth -= 1

    def visit_If(self, node: ast.If) -> None:
        # Python represents an `elif` as a nested ast.If inside node.orelse
        # ([If(...)] with nothing else). That's a flat elif chain, not real
        # nesting depth — only node.body (the `if true` branch) and a genuine
        # `else` block should count as +1 depth. Walking orelse's elif at the
        # *same* depth (not recursing via generic_visit, which would treat
        # every elif as one more nested level) is what keeps a 12-branch flat
        # dispatch from being misreported as 11 levels deep.
        self.cyclomatic += 1
        self.visit(node.test)
        self._enter()
        for stmt in node.body:
            self.visit(stmt)
        self._exit()
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            self.visit(node.orelse[0])  # elif — same depth
        elif node.orelse:
            self._enter()
            for stmt in node.orelse:
                self.visit(stmt)
            self._exit()

    def visit_For(self, node: ast.For) -> None:
        self.cyclomatic += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_While(self, node: ast.While) -> None:
        self.cyclomatic += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.cyclomatic += 1
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_With(self, node: ast.With) -> None:
        # +1 depth only — a with-block isn't a decision point (no cyclomatic
        # branch), but it does nest the code inside it.
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # each and/or short-circuit adds one more path through the expression
        self.cyclomatic += len(node.values) - 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:  # ternary
        self.cyclomatic += 1
        self.generic_visit(node)


def _walk_functions(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def check_complexity(
    staging_dir: Path,
    impl_paths: list[str],
    max_cyclomatic: int,
    max_nesting: int,
) -> list[Finding]:
    findings: list[Finding] = []
    for rel in impl_paths:
        p = staging_dir / rel
        if not p.exists():
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        for fn in _walk_functions(tree):
            v = _ComplexityVisitor()
            v.visit(fn)
            if v.cyclomatic > max_cyclomatic:
                findings.append(Finding(
                    "cyclomatic", f"{rel}::{fn.name}", v.cyclomatic,
                    f"`{fn.name}` in {rel} has cyclomatic complexity "
                    f"{v.cyclomatic} (max {max_cyclomatic}) — consider "
                    f"splitting into smaller functions or a dispatch table."))
            if v.max_depth > max_nesting:
                findings.append(Finding(
                    "nesting", f"{rel}::{fn.name}", v.max_depth,
                    f"`{fn.name}` in {rel} nests {v.max_depth} levels deep "
                    f"(max {max_nesting}) — consider early returns / guard "
                    f"clauses to flatten."))
    return findings


def run(
    briefs_dir: Path,
    root: Path,
    leaf_id: str,
    staging_dir: Path | None,
    max_cyclomatic: int,
    max_nesting: int,
    strict: bool,
    cascade: str | None = None,
) -> Report:
    brief = find_brief(briefs_dir, leaf_id)
    if brief is None:
        print(f"leaf `{leaf_id}` not found under {briefs_dir}", file=sys.stderr)
        return Report(leaf_id, applicable=False, strict=strict)
    impl_paths = ci._leaf_paths(brief, "impl")
    if not impl_paths:
        return Report(leaf_id, applicable=False, strict=strict)
    sdir = ci.resolve_staging_dir(
        root, leaf_id, shard=ci._shard(brief), slug=cascade,
        explicit=staging_dir,
    )
    if not sdir.exists():
        print(f"staging dir not found: {sdir}", file=sys.stderr)
        return Report(leaf_id, applicable=False, strict=strict)
    findings = check_complexity(sdir, impl_paths, max_cyclomatic, max_nesting)
    return Report(leaf_id, applicable=True, findings=findings, strict=strict)


def render(rpt: Report) -> str:
    if not rpt.applicable:
        return f"{rpt.leaf_id}: SKIP (no impl_files, or leaf not found)"
    if not rpt.findings:
        return f"{rpt.leaf_id}: PASS (complexity + nesting)"
    lines = [
        f"{rpt.leaf_id}: {'FAIL' if rpt.strict else 'ADVISORY'}: {f.kind}: {f.reason}"
        for f in rpt.findings
    ]
    if rpt.strict:
        lines.append(f"--- {len(rpt.findings)} blocking finding(s), G9 blocks admission (--strict) ---")
    else:
        lines.append(f"--- {len(rpt.findings)} advisory finding(s) (non-blocking — pass --strict to block) ---")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="/manager-mode Phase 6 G9: cyclomatic complexity + nesting depth gate")
    p.add_argument("--leaf", required=True)
    p.add_argument("--briefs-dir", type=Path)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--staging-dir", type=Path,
        help="default: <root>/.swarm/<cascade>/pending/[<shard>/]<leaf>, "
             "falling back to the flat <root>/.swarm/pending/<leaf>")
    p.add_argument("--cascade",
        help="cascade slug for `.swarm/<slug>/...` layouts; auto-detected when "
             "exactly one exists")
    p.add_argument("--max-cyclomatic", type=int, default=10)
    p.add_argument("--max-nesting", type=int, default=3)
    p.add_argument(
        "--strict", action="store_true",
        help="block admission on findings (default: advisory-only — a high "
             "score is not proof of a defect; use under manager-mode-hardcore, "
             "where a wrong admit is expensive enough to stop for a heuristic)")
    args = p.parse_args(argv)

    root = ci.git_root(args.root)
    cfg = ci.load_config(root)
    briefs_dir = ci.resolve_briefs_dir(root, cfg, args.briefs_dir, args.cascade)
    if not briefs_dir.exists():
        print(f"briefs_dir not found: {briefs_dir}", file=sys.stderr)
        return 2

    rpt = run(
        briefs_dir, root, args.leaf, args.staging_dir,
        args.max_cyclomatic, args.max_nesting, args.strict,
        ci.discover_cascade_slug(root, args.cascade),
    )
    print(render(rpt))
    return 0 if rpt.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
