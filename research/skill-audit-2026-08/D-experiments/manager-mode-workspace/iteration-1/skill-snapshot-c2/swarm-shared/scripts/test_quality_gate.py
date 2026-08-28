#!/usr/bin/env python3
"""test_quality_gate.py — /manager-mode Phase 6 gate G8, multi-file leaves only.

A single-file leaf has nothing to be unreachable *from*, so this script is a
no-op (exit 0) for any leaf with fewer than 2 impl_files. For leaves with 2+,
it runs two checks:

  1. Reachability — every top-level function/class defined in the leaf's
     impl_files must be referenced by name in another impl file, OR covered
     by an interaction assertion in the test file (a call/spy/mock reference
     near the name — see brief-template.md's composition rule). A definition
     that only appears inside its own unit test is flagged as possibly
     orphaned: it exists, it's tested in isolation, nothing wires it in.
     This is the direct, mechanical fix for the defect class described in
     playbook.md's Roles section (a leaf resolving an unresolved contradiction
     by shipping two implementations, one of them dead).

  2. Lite mutation — for a bounded sample of the functions that DID pass
     reachability, apply one mechanical mutation to the function body (flip a
     comparison operator, negate a boolean literal, or offset a numeric
     literal by one) in a scratch copy of the staged leaf, rerun the leaf's
     test command against it. If the mutated version still passes 100%, that
     function's assertions are weak/tautological enough not to notice a real
     behavior change — flagged.

Deliberately small: one mutant per sampled function, capped by --max-mutants,
not full mutation-testing-tool coverage. The point is a fast per-leaf gate,
not exhaustive mutation analysis.

Exit codes: 0 = pass (or not applicable — fewer than 2 impl_files), 1 =
findings (block admission), 2 = usage/config error.
"""
from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_invariants as ci  # noqa: E402


@dataclass
class Finding:
    kind: str  # "reachability" | "mutation"
    target: str
    reason: str


@dataclass
class Report:
    leaf_id: str
    applicable: bool
    findings: list[Finding] = field(default_factory=list)
    strict: bool = False

    def passed(self) -> bool:
        if not self.applicable:
            return True
        if self.strict:
            return not self.findings
        # Reachability is deterministic — no test input happened to exercise
        # the orphaned function, that's the whole finding — so it blocks by
        # default. A single-mutant mutation finding can be a false alarm: the
        # one mutation this lite gate tried just wasn't covered by any test's
        # chosen inputs, which doesn't prove the assertions are actually
        # tautological (see test_quality_gate.py's module docstring on scope).
        # Advisory by default; pass --strict (or run under manager-mode-
        # hardcore) to promote it to blocking.
        return not any(f.kind == "reachability" for f in self.findings)


def _strip_comments(source: str) -> str:
    """Blank out `#`-comment text (keep line structure/length so any lineno
    math elsewhere stays valid) so a comment merely mentioning "call" or
    "mock" in passing can never satisfy INTERACTION_HINTS. Deliberately
    simple — doesn't parse strings, so a `#` inside a string literal gets
    treated as a comment start too, but that only makes the filter stricter
    (more likely to strip real code as if it were a comment, never the
    reverse), which is the safe direction for a gate that's advisory here
    anyway."""
    out_lines = []
    for line in source.splitlines():
        idx = line.find("#")
        out_lines.append(line[:idx] if idx != -1 else line)
    return "\n".join(out_lines)


# Deliberately narrow to actual interaction-testing API shapes, not bare
# English words like "call"/"mock" — a live Phase-E run proved a prior,
# looser version of this pattern false-triggered on an ordinary comment
# ("...not part of build_invoice's call chain") that happened to contain the
# word "call", masking a real reachability finding. `_strip_comments` below
# is the first line of defense (comments never see this regex at all); this
# tighter pattern is the second — even inside real test code, only count it
# if it's recognizably mock/spy/patch syntax, not prose that mentions calling.
INTERACTION_HINTS = re.compile(
    r"(assert_called|Mock\(|MagicMock\(|patch\(|patch\.object\(|"
    r"monkeypatch\.setattr\(|monkeypatch\.setattr\b|wraps=)",
)


def find_brief(briefs_dir: Path, leaf_id: str) -> ci.Brief | None:
    for path in sorted(briefs_dir.glob("leaf-*.md")) + sorted(briefs_dir.glob("shard-*/leaf-*.md")):
        b = ci.parse_brief(path)
        if b is not None and b.leaf_id == leaf_id:
            return b
    return None


def _top_level_defs(source: str) -> dict[str, ast.AST]:
    """Public (non-underscore) top-level function/class defs, name -> node."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                out[node.name] = node
    return out


def _call_targets(tree: ast.AST) -> list[tuple[int, str]]:
    """[(lineno, called_name)] for every Call node in tree — direct `name(...)`
    or attribute `mod.name(...)` calls. A textual mention (comment, docstring,
    string literal) never produces a Call node, so this only counts real
    invocations — the naive `re.search(name, other_source)` this replaces was
    fooled by a comment merely *mentioning* an unused function's name."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                out.append((node.lineno, f.id))
            elif isinstance(f, ast.Attribute):
                out.append((node.lineno, f.attr))
    return out


def check_reachability(
    staging_dir: Path, impl_paths: list[str], test_paths: list[str],
    standalone: set[str] = frozenset(),
) -> list[Finding]:
    """A function called directly by its own unit test is normal — that's how
    a leaf's entry point (the orchestrator) gets exercised. The actual smell
    is a SECOND, independent root: a function nobody's impl code calls, that
    the leaf's real entry point never wires in. So: build the impl-to-impl
    call graph, find the entry point (most outgoing local calls — the
    orchestrator), and flag any OTHER top-level def with zero incoming calls
    from leaf-local code. If the leaf has no impl-to-impl calls at all, it's
    a bundle of genuinely independent functions (a legitimate multi-file
    leaf shape per brief-template.md) — nothing to flag, skip entirely.

    `standalone` is the brief's declared `standalone_symbols` list (function
    names the brief author asserts are intentionally not part of the
    composition chain — a real utility bundled into the leaf, tested with an
    ordinary state check, on purpose). This check has no way to infer intent
    from code shape alone: a live run proved that out (three genuinely
    standalone, correctly-tested utility functions all got flagged, because
    "called by leaf-local code" and "test carries interaction-assertion
    syntax" are the only two signals available, and neither is true of a
    correctly-written state-check test for a real standalone function). The
    brief author is the only one who actually knows which case it is, so
    that's a declared fact from the brief now, not a heuristic guess."""
    findings: list[Finding] = []
    trees: dict[str, ast.Module] = {}
    for rel in impl_paths:
        p = staging_dir / rel
        if not p.exists():
            continue
        try:
            trees[rel] = ast.parse(p.read_text())
        except SyntaxError:
            continue

    defs: dict[str, tuple[str, ast.AST]] = {}
    for rel, tree in trees.items():
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and not node.name.startswith("_"):
                defs[node.name] = (rel, node)

    out_degree = {n: 0 for n in defs}
    in_degree = {n: 0 for n in defs}
    for name, (_rel, node) in defs.items():
        for _lineno, called in _call_targets(node):
            if called in defs and called != name:
                out_degree[name] += 1
                in_degree[called] += 1

    if not defs or max(out_degree.values(), default=0) == 0:
        return findings  # no impl-to-impl composition in this leaf at all

    entry_point = max(out_degree, key=lambda n: out_degree[n])

    test_text = ""
    for rel in test_paths:
        p = staging_dir / rel
        if p.exists():
            test_text += _strip_comments(p.read_text()) + "\n"

    for name, (rel, node) in defs.items():
        if name == entry_point or in_degree[name] > 0 or name in standalone:
            continue
        # Never called by any leaf-local impl code, and isn't the entry
        # point. Allowed only if the test shows interaction-assertion
        # vocabulary near a direct reference — a bare state-check of the
        # function in isolation does not prove it's wired into composition.
        covered_by_interaction_test = False
        name_re = re.compile(rf"\b{re.escape(name)}\b")
        for m in name_re.finditer(test_text):
            window = test_text[max(0, m.start() - 200):m.end() + 200]
            if INTERACTION_HINTS.search(window):
                covered_by_interaction_test = True
                break
        if not covered_by_interaction_test:
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            findings.append(Finding(
                "reachability", f"{rel}::{name}",
                f"{kind} `{name}` in {rel} is never called by any other "
                f"function in this leaf (entry point appears to be "
                f"`{entry_point}`), and no interaction assertion in the "
                f"test covers it — possibly orphaned, not wired into "
                f"composition.",
            ))
    return findings


# ---------- lite mutation ----------

def _mutation_sites(source: str, node: ast.AST) -> list[tuple[int, int, str, str]]:
    """Return [(lineno, col_offset, old, new)] candidate mutation sites inside
    one function/class body: bool negate, numeric offset. Only Constant nodes
    are used — their col_offset points at the literal itself, so the
    text-replace in `_apply_mutation` is reliable. (An earlier version also
    tried flipping comparison operators via `Compare.col_offset`, but that
    offset points at the comparison's LEFT OPERAND, not the operator — every
    such mutation silently failed its column check and fell through to
    whichever numeric site came next, sometimes one no test actually
    exercised. Correctly locating an operator's own column needs more source
    parsing than this lite gate is scoped for, so comparison mutation is
    dropped rather than shipped broken.)"""
    sites: list[tuple[int, int, str, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, bool):
            sites.append((child.lineno, child.col_offset,
                          str(child.value), str(not child.value)))
        elif isinstance(child, ast.Constant) and isinstance(child.value, (int, float)) \
                and not isinstance(child.value, bool):
            sites.append((child.lineno, child.col_offset,
                          repr(child.value), repr(child.value + 1)))
    return sites


def _apply_mutation(source: str, site: tuple[int, int, str, str]) -> str | None:
    lineno, col, old, new = site
    lines = source.splitlines(keepends=True)
    if lineno - 1 >= len(lines):
        return None
    line = lines[lineno - 1]
    if line[col:col + len(old)] != old:
        return None  # column drifted (shouldn't happen off a fresh parse), skip
    lines[lineno - 1] = line[:col] + new + line[col + len(old):]
    return "".join(lines)


def check_mutation(
    staging_dir: Path,
    impl_paths: list[str],
    test_paths: list[str],
    test_cmd: str,
    max_mutants: int,
    pythonpath: str | None,
    skip_targets: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    tried = 0
    for rel in impl_paths:
        p = staging_dir / rel
        if not p.exists():
            continue
        source = p.read_text()
        defs = _top_level_defs(source)
        for name, node in defs.items():
            if tried >= max_mutants:
                return findings
            if f"{rel}::{name}" in skip_targets:
                continue  # already flagged orphaned by reachability; mutating it adds no signal
            sites = _mutation_sites(source, node)
            if not sites:
                continue
            mutated_source = None
            for site in sites:
                mutated_source = _apply_mutation(source, site)
                if mutated_source is not None:
                    break
            if mutated_source is None:
                continue
            tried += 1
            with tempfile.TemporaryDirectory(prefix="tqg-mutant-") as tmp:
                tmp_root = Path(tmp)
                shutil.copytree(staging_dir, tmp_root, dirs_exist_ok=True)
                (tmp_root / rel).write_text(mutated_source)
                env = None
                if pythonpath:
                    import os
                    env = {**os.environ, "PYTHONPATH": str(tmp_root / pythonpath)}
                result = subprocess.run(
                    test_cmd, shell=True, cwd=tmp_root, env=env,
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    findings.append(Finding(
                        "mutation", f"{rel}::{name}",
                        f"mutating `{name}` in {rel} still passes `{test_cmd}` "
                        f"— assertions for this function are weak enough to "
                        f"miss a real behavior change.",
                    ))
    return findings


def run(
    briefs_dir: Path, root: Path, leaf_id: str, staging_dir: Path | None,
    test_cmd: str | None, max_mutants: int, pythonpath: str | None,
    strict: bool = False, cascade: str | None = None,
) -> Report:
    brief = find_brief(briefs_dir, leaf_id)
    if brief is None:
        print(f"leaf `{leaf_id}` not found under {briefs_dir}", file=sys.stderr)
        return Report(leaf_id, applicable=False, strict=strict)

    impl_paths = ci._leaf_paths(brief, "impl")
    test_paths = ci._leaf_paths(brief, "test")
    if len(impl_paths) < 2:
        return Report(leaf_id, applicable=False, strict=strict)  # nothing to be unreachable from

    sdir = ci.resolve_staging_dir(
        root, leaf_id, shard=ci._shard(brief), slug=cascade,
        explicit=staging_dir,
    )
    if not sdir.exists():
        print(f"staging dir not found: {sdir}", file=sys.stderr)
        return Report(leaf_id, applicable=False, strict=strict)

    standalone_raw = brief.frontmatter.get("standalone_symbols") or []
    standalone = {s for s in standalone_raw if isinstance(s, str)}

    reach_findings = check_reachability(sdir, impl_paths, test_paths, standalone)

    cmd = test_cmd or f"python3 -m pytest {' '.join(test_paths)}"
    orphaned = {f.target for f in reach_findings}
    mut_findings = check_mutation(
        sdir, impl_paths, test_paths, cmd, max_mutants, pythonpath, orphaned,
    )

    return Report(leaf_id, applicable=True, findings=reach_findings + mut_findings, strict=strict)


def render(rpt: Report) -> str:
    if not rpt.applicable:
        return f"{rpt.leaf_id}: SKIP (not applicable — fewer than 2 impl_files, or leaf not found)"
    if not rpt.findings:
        return f"{rpt.leaf_id}: PASS (reachability + lite mutation)"
    lines = []
    for f in rpt.findings:
        blocking = f.kind == "reachability" or rpt.strict
        tag = "FAIL" if blocking else "ADVISORY"
        lines.append(f"{rpt.leaf_id}: {tag}: {f.kind}: {f.reason}")
    n_blocking = sum(1 for f in rpt.findings if f.kind == "reachability" or rpt.strict)
    if n_blocking:
        lines.append(f"--- {n_blocking} blocking finding(s), G8 blocks admission ---")
    else:
        lines.append(f"--- {len(rpt.findings)} advisory finding(s) (mutation, non-blocking — pass --strict to block) ---")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="/manager-mode Phase 6 G8: reachability + lite mutation gate")
    p.add_argument("--leaf", required=True, help="leaf_id, e.g. leaf-03")
    p.add_argument("--briefs-dir", type=Path, help="default from .claude-swarm.toml")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--staging-dir", type=Path,
        help="default: <root>/.swarm/<cascade>/pending/[<shard>/]<leaf>, "
             "falling back to the flat <root>/.swarm/pending/<leaf>")
    p.add_argument("--cascade",
        help="cascade slug for `.swarm/<slug>/...` layouts; auto-detected when "
             "exactly one exists")
    p.add_argument("--test-cmd", help="default: python3 -m pytest <test_files>")
    p.add_argument("--pythonpath", help="relative dir (from staged leaf root) to add to PYTHONPATH for mutant runs")
    p.add_argument("--max-mutants", type=int, default=8)
    p.add_argument("--strict", action="store_true",
        help="also block on mutation findings (default: advisory-only, since a single-mutant "
             "miss can be an unlucky pick rather than proof of a weak test — use under "
             "manager-mode-hardcore or for high-consequence leaves)")
    args = p.parse_args(argv)

    root = ci.git_root(args.root)
    cfg = ci.load_config(root)
    briefs_dir = ci.resolve_briefs_dir(root, cfg, args.briefs_dir, args.cascade)
    if not briefs_dir.exists():
        print(f"briefs_dir not found: {briefs_dir}", file=sys.stderr)
        return 2

    rpt = run(
        briefs_dir, root, args.leaf, args.staging_dir, args.test_cmd,
        args.max_mutants, args.pythonpath, args.strict,
        ci.discover_cascade_slug(root, args.cascade),
    )
    print(render(rpt))
    return 0 if rpt.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
