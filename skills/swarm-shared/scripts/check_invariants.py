#!/usr/bin/env python3
"""claude-manager-mode — deterministic 3-invariant audit on leaf briefs.

Invoked by /manager-mode Phase 3. Reads every *.md brief in briefs_dir, parses the YAML
frontmatter, and validates against the three invariants defined in
~/.claude/skills/swarm-shared/references/playbook.md:

    (a) file-ownership non-overlap
    (b) no design decisions delegated to the leaf
    (c) sizing within configured budgets
    (d) spec-link rule (every brief-declared test file begins with a
        `# spec: <path>::<section>::AC-<N>` header)

Output: one line per brief plus a summary line. Exit code 0 only if all briefs
pass. Designed to be called from a shell snippet inside SKILL.md so the audit
is mechanical, not LLM-judgment.

Config: <git_root>/.claude-swarm.toml. Missing keys inherit defaults below.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # py311+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


# ---------- defaults ----------

DEFAULTS: dict[str, Any] = {
    "spec_dir": "specs/",
    "briefs_dir": ".swarm/briefs/",
    "type_contract_path": "",  # no sensible global default
    "umbrella_test_cmd": "",
    "graphify_cmd": "",
    "parent_owned": [
        "src/**/types.py",
        "tests/conftest.py",
        "tests/umbrella*.py",
        "tests/integration/**",
    ],
    "invariants": {
        "max_impl_lines": 200,
        "max_test_assertions": 20,
        "max_brief_code_lines": 10,
        "ambiguous_verbs": [
            "decide", "choose", "design", "determine",
            "figure out", "resolve", "as appropriate",
            "use your judgment", "pick", "select an approach",
        ],
    },
}


# ---------- data ----------

@dataclass
class Brief:
    path: Path
    frontmatter: dict[str, Any]
    body: str

    @property
    def leaf_id(self) -> str:
        return str(self.frontmatter.get("leaf_id", self.path.stem))


@dataclass
class Failure:
    leaf_id: str
    invariant: str  # "non-overlap" | "no-design" | "sizing" | "schema"
    reason: str


@dataclass
class Report:
    briefs: list[Brief] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


# ---------- io ----------

def git_root(start: Path) -> Path:
    """Walk up from start looking for .claude-swarm.toml; fall back to start."""
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".claude-swarm.toml").exists():
            return parent
    return start


def load_config(root: Path) -> dict[str, Any]:
    cfg_path = root / ".claude-swarm.toml"
    if not cfg_path.exists():
        return DEFAULTS
    with cfg_path.open("rb") as fh:
        user_cfg = tomllib.load(fh)
    merged = {**DEFAULTS, **user_cfg}
    inv = {**DEFAULTS["invariants"], **user_cfg.get("invariants", {})}
    merged["invariants"] = inv
    return merged


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_brief(path: Path) -> Brief | None:
    text = path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    fm_text, body = m.group(1), m.group(2)
    fm = _parse_simple_yaml(fm_text)
    return Brief(path=path, frontmatter=fm, body=body)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Lightweight YAML loader for the brief frontmatter shape we control.

    Handles: `key: value` scalars, `key:` followed by `- item` lists. No
    nesting beyond one level. Intentional — we own the brief template and
    want zero pyyaml dep so this script runs anywhere.
    """
    out: dict[str, Any] = {}
    current_key: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            item = line.split("- ", 1)[1].strip()
            if current_key is None:
                continue
            out.setdefault(current_key, []).append(item)
            continue
        if ":" in line:
            # Indented `key: val` while accumulating a list is a nested-mapping
            # sub-field (e.g. codebase_preconditions' `verify:`). The simple
            # loader does not model nesting; skip it rather than crash.
            if raw[:1].isspace() and isinstance(out.get(current_key), list):
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            if val == "":
                out[key] = []  # list continuation expected
            else:
                out[key] = _coerce(val)
    return out


def _coerce(val: str) -> Any:
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    if val.isdigit():
        return int(val)
    return val


# ---------- invariants ----------

REQUIRED_FIELDS = (
    "leaf_id", "spec_file", "spec_lines",
    "test_file", "impl_file",
    "contract_imports", "do_not_edit",
    "impl_line_budget", "test_assertion_budget",
)


def check_schema(briefs: list[Brief]) -> list[Failure]:
    fails: list[Failure] = []
    seen_ids: set[str] = set()
    for b in briefs:
        for field_name in REQUIRED_FIELDS:
            if field_name not in b.frontmatter:
                fails.append(Failure(b.leaf_id, "schema",
                    f"missing required field `{field_name}`"))
        if b.leaf_id in seen_ids:
            fails.append(Failure(b.leaf_id, "schema",
                f"duplicate leaf_id `{b.leaf_id}` across briefs"))
        seen_ids.add(b.leaf_id)
    return fails


def _leaf_paths(b: Brief, kind: str) -> list[str]:
    """Return all paths a leaf claims for `kind` ('test' or 'impl').

    Combines singular `<kind>_file` + optional plural `<kind>_files`.
    """
    out: list[str] = []
    singular = b.frontmatter.get(f"{kind}_file")
    if isinstance(singular, str):
        out.append(singular)
    plural = b.frontmatter.get(f"{kind}_files") or []
    if isinstance(plural, list):
        out.extend(p for p in plural if isinstance(p, str))
    return out


def _wave(b: Brief) -> int:
    w = b.frontmatter.get("wave", 1)
    try:
        return int(w)
    except (TypeError, ValueError):
        return 1


def _test_owned_by_leaf(b: Brief) -> bool:
    """Default: leaf owns its tests. Set test_owned_by: parent in the brief
    when the parent agent authors umbrella + integration tests and the leaf
    only writes impl."""
    return str(b.frontmatter.get("test_owned_by", "leaf")).lower() == "leaf"


def check_non_overlap(briefs: list[Brief], parent_owned: list[str]) -> list[Failure]:
    fails: list[Failure] = []
    # Owner is scoped per wave: leaves in different waves run sequentially,
    # so editing the same file across waves is fine (and common for follow-ups).
    owner: dict[tuple[int, str], str] = {}
    for b in briefs:
        b_wave = _wave(b)
        # impl paths always leaf-owned; test paths only if test_owned_by=leaf
        path_specs: list[tuple[str, str, bool]] = []
        for p in _leaf_paths(b, "impl"):
            path_specs.append(("impl_file", p, True))
        for p in _leaf_paths(b, "test"):
            path_specs.append(("test_file", p, _test_owned_by_leaf(b)))

        for key, path, leaf_owned in path_specs:
            # parent_owned glob check only applies to leaf-claimed-ownership paths
            if leaf_owned:
                wkey = (b_wave, path)
                if wkey in owner:
                    fails.append(Failure(b.leaf_id, "non-overlap",
                        f"{key} `{path}` already owned by {owner[wkey]}"))
                else:
                    owner[wkey] = b.leaf_id
                for glob in parent_owned:
                    if fnmatch.fnmatch(path, glob):
                        fails.append(Failure(b.leaf_id, "non-overlap",
                            f"{key} `{path}` matches parent-owned glob `{glob}`"))

        # do_not_edit must include every same-wave sibling's leaf-owned files
        do_not = set(b.frontmatter.get("do_not_edit") or [])
        b_wave = _wave(b)
        for other in briefs:
            if other.leaf_id == b.leaf_id:
                continue
            if _wave(other) != b_wave:
                continue  # different-wave leaves don't run in parallel
            sibling_paths: list[str] = list(_leaf_paths(other, "impl"))
            if _test_owned_by_leaf(other):
                sibling_paths.extend(_leaf_paths(other, "test"))
            for sibling in sibling_paths:
                if sibling not in do_not:
                    fails.append(Failure(b.leaf_id, "non-overlap",
                        f"do_not_edit is missing sibling-owned `{sibling}` "
                        f"(owned by {other.leaf_id})"))
    return fails


SPEC_LINES_RE = re.compile(r"^\d+-\d+$")


FENCED_CODE_RE = re.compile(r"^[ \t]*```[^\n]*\n(.*?)^[ \t]*```", re.MULTILINE | re.DOTALL)


def _count_fenced_code_lines(body: str) -> int:
    """Sum of non-blank lines inside all fenced code blocks in the brief body.

    Used to detect parent-authored impl bodies pasted into the brief. Stub
    signatures (a few lines of `def foo(...)` headers) stay under the budget;
    full ready-to-paste implementations trip it.
    """
    total = 0
    for m in FENCED_CODE_RE.finditer(body):
        block = m.group(1)
        for line in block.splitlines():
            if line.strip():
                total += 1
    return total


def check_no_design(
    briefs: list[Brief],
    root: Path,
    type_contract_path: str,
    ambiguous_verbs: list[str],
    max_brief_code_lines: int,
) -> list[Failure]:
    fails: list[Failure] = []
    contract_symbols = _load_contract_symbols(root, type_contract_path)
    verb_patterns = [
        re.compile(rf"\b{re.escape(v)}\b", re.IGNORECASE)
        for v in ambiguous_verbs
    ]
    for b in briefs:
        spec_lines = str(b.frontmatter.get("spec_lines", ""))
        if not SPEC_LINES_RE.match(spec_lines):
            fails.append(Failure(b.leaf_id, "no-design",
                f"spec_lines `{spec_lines}` is not a concrete `int-int` range"))
        # contract imports must resolve
        if contract_symbols is not None:
            for sym in b.frontmatter.get("contract_imports") or []:
                bare = sym.rsplit(".", 1)[-1] if isinstance(sym, str) else sym
                if isinstance(bare, str) and bare not in contract_symbols:
                    fails.append(Failure(b.leaf_id, "no-design",
                        f"contract import `{sym}` not in locked contract"))
        # body prose scanned for ambiguous verbs
        for pat in verb_patterns:
            m = pat.search(b.body)
            if m:
                fails.append(Failure(b.leaf_id, "no-design",
                    f"task prose contains ambiguous verb `{m.group(0)}` — "
                    f"that delegates a design decision to the leaf"))
                break  # one finding per brief is enough
        # fenced code budget — brief must not embed ready-to-paste impl bodies.
        # Stub signatures (≤ max) stay; full implementations trip and the leaf
        # loses authorship. Shape-carriers (spec_lines, contract_imports,
        # mirror-pointers in prose) replace embedded bodies.
        code_lines = _count_fenced_code_lines(b.body)
        if code_lines > max_brief_code_lines:
            fails.append(Failure(b.leaf_id, "no-design",
                f"brief embeds {code_lines} lines of fenced code (max "
                f"{max_brief_code_lines}) — collapse to shape (spec_lines "
                f"refs, contract_imports, stub signatures, mirror-pointers). "
                f"Leaf authors the body."))
    return fails


def _load_contract_symbols(root: Path, contract_path: str) -> set[str] | None:
    if not contract_path:
        return None
    p = root / contract_path
    if not p.exists():
        return None
    text = p.read_text()
    # crude symbol extraction: top-level class/def names + UPPER constants.
    # Python and TypeScript/JavaScript patterns coexist in one pass — the
    # keyword anchors don't overlap, so a TS contract and a Python contract
    # both extract correctly without a per-language switch.
    syms: set[str] = set()
    for m in re.finditer(r"^(?:class|def)\s+(\w+)", text, re.MULTILINE):
        syms.add(m.group(1))
    for m in re.finditer(r"^([A-Z][A-Z0-9_]+)\s*=", text, re.MULTILINE):
        syms.add(m.group(1))
    # also pydantic-style Literal kinds, etc.
    for m in re.finditer(r'Literal\[([^\]]+)\]', text):
        for raw in m.group(1).split(","):
            tok = raw.strip().strip("'\"")
            if tok:
                syms.add(tok)
    # TypeScript/JavaScript top-level exports
    for m in re.finditer(
        r"^export\s+(?:default\s+)?(?:async\s+)?"
        r"(?:interface|type|class|enum|function|const|let|var)\s+(\w+)",
        text, re.MULTILINE,
    ):
        syms.add(m.group(1))
    # TS string-literal unions: `type Status = 'a' | 'b' | 'c'`
    for m in re.finditer(
        r"(?:^|\s)type\s+\w+\s*=\s*([^;{}\n]+(?:\n\s*\|[^;{}\n]+)*)",
        text, re.MULTILINE,
    ):
        for tok in re.findall(r"['\"]([\w-]+)['\"]", m.group(1)):
            syms.add(tok)
    return syms


SPEC_LINK_RE = re.compile(r"^(?:#|--)\s*spec:\s*\S+::.+?::AC-\d+", re.MULTILINE)


def check_spec_link(briefs: list[Brief], root: Path) -> list[Failure]:
    """Every brief-declared test file must start with a `# spec: ...::AC-N` header.

    The header anchors the test back to the spec line it encodes. Phase 2 of the
    /manager-mode cascade requires the overlord to write tests with this header; this
    check enforces it before any leaf spawns.
    """
    fails: list[Failure] = []
    for b in briefs:
        for path in _leaf_paths(b, "test"):
            p = root / path
            if not p.exists():
                # Phase 2 should have written it. Missing test file at audit-time
                # is itself a failure — leaves cannot run against a non-existent test.
                fails.append(Failure(b.leaf_id, "spec-link",
                    f"declared test file `{path}` not found on disk — "
                    f"overlord must write per-leaf tests before audit"))
                continue
            head = p.read_text().splitlines()[:5]  # only scan first 5 lines
            head_text = "\n".join(head)
            if not SPEC_LINK_RE.search(head_text):
                fails.append(Failure(b.leaf_id, "spec-link",
                    f"test file `{path}` missing Spec Link Rule header "
                    f"`# spec: <path>::<section>::AC-<N>` in first 5 lines"))
    return fails


def check_sizing(briefs: list[Brief], invariants: dict[str, Any]) -> list[Failure]:
    fails: list[Failure] = []
    max_lines = int(invariants["max_impl_lines"])
    max_assert = int(invariants["max_test_assertions"])
    for b in briefs:
        ibudget = b.frontmatter.get("impl_line_budget")
        tbudget = b.frontmatter.get("test_assertion_budget")
        if isinstance(ibudget, int) and ibudget > max_lines:
            fails.append(Failure(b.leaf_id, "sizing",
                f"impl_line_budget={ibudget} exceeds project max {max_lines} — "
                f"slice into two leaves"))
        if isinstance(tbudget, int) and tbudget > max_assert:
            fails.append(Failure(b.leaf_id, "sizing",
                f"test_assertion_budget={tbudget} exceeds project max {max_assert}"))
    return fails


# ---------- driver ----------

def audit(briefs_dir: Path, cfg: dict[str, Any], root: Path) -> Report:
    rpt = Report()
    for path in sorted(briefs_dir.glob("leaf-*.md")):
        b = parse_brief(path)
        if b is None:
            rpt.failures.append(Failure(path.stem, "schema",
                "no YAML frontmatter — brief is malformed"))
            continue
        rpt.briefs.append(b)
    rpt.failures.extend(check_schema(rpt.briefs))
    rpt.failures.extend(check_non_overlap(rpt.briefs, cfg["parent_owned"]))
    rpt.failures.extend(check_no_design(
        rpt.briefs, root, cfg["type_contract_path"],
        cfg["invariants"]["ambiguous_verbs"],
        int(cfg["invariants"]["max_brief_code_lines"]),
    ))
    rpt.failures.extend(check_sizing(rpt.briefs, cfg["invariants"]))
    rpt.failures.extend(check_spec_link(rpt.briefs, root))
    return rpt


def render(rpt: Report) -> str:
    lines: list[str] = []
    failures_by_leaf: dict[str, list[Failure]] = {}
    for f in rpt.failures:
        failures_by_leaf.setdefault(f.leaf_id, []).append(f)
    for b in rpt.briefs:
        leaf_fails = failures_by_leaf.get(b.leaf_id, [])
        if not leaf_fails:
            lines.append(f"{b.leaf_id}: PASS")
        else:
            for f in leaf_fails:
                lines.append(f"{b.leaf_id}: FAIL: {f.invariant}: {f.reason}")
    # surface schema failures with no parsed brief
    leaf_ids_with_briefs = {b.leaf_id for b in rpt.briefs}
    for f in rpt.failures:
        if f.leaf_id not in leaf_ids_with_briefs:
            lines.append(f"{f.leaf_id}: FAIL: {f.invariant}: {f.reason}")
    total = len(rpt.briefs)
    n_pass = sum(1 for b in rpt.briefs if b.leaf_id not in failures_by_leaf)
    lines.append(f"--- {n_pass}/{total} briefs PASS, {len(rpt.failures)} findings ---")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="claude-manager-mode 3-invariant audit")
    p.add_argument("--briefs-dir", type=Path,
        help="path to briefs dir; default from .claude-swarm.toml")
    p.add_argument("--root", type=Path, default=Path.cwd(),
        help="project root (defaults to cwd; walks up looking for .claude-swarm.toml)")
    args = p.parse_args(argv)

    root = git_root(args.root)
    cfg = load_config(root)
    briefs_dir = args.briefs_dir or (root / cfg["briefs_dir"])
    if not briefs_dir.exists():
        print(f"briefs_dir not found: {briefs_dir}", file=sys.stderr)
        return 2
    rpt = audit(briefs_dir, cfg, root)
    print(render(rpt))
    return 0 if rpt.passed else 1


if __name__ == "__main__":
    sys.exit(main())
