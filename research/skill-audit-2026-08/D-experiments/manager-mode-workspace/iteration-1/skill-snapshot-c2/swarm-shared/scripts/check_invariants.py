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
    (e) no-contradiction (heuristic — same identifier asserted to two
        different literal values across sibling briefs, same wave/shard)

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
        "max_impl_lines": 1000,
        "max_test_assertions": 20,
        "max_brief_code_lines": 10,
        "max_leaves_per_shard": 6,
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
    invariant: str  # "non-overlap" | "no-design" | "sizing" | "shard-sizing" | "schema"
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
        cfg = {**DEFAULTS, "invariants": {**DEFAULTS["invariants"]}}
        cfg["_user_keys"] = frozenset()
        return cfg
    with cfg_path.open("rb") as fh:
        user_cfg = tomllib.load(fh)
    merged = {**DEFAULTS, **user_cfg}
    inv = {**DEFAULTS["invariants"], **user_cfg.get("invariants", {})}
    merged["invariants"] = inv
    # An explicitly-set key always wins over a derived default. Without this
    # the cascade-slug resolver below cannot tell `briefs_dir` the user chose
    # from `briefs_dir` that merely fell through from DEFAULTS.
    merged["_user_keys"] = frozenset(user_cfg)
    return merged


# ---------- cascade-slug path resolution ----------
#
# /manager-mode scopes each cascade's working files under `.swarm/<slug>/`
# (config.md "Cascade-slug derivation"). Projects predating that layout keep a
# flat `.swarm/briefs/` + `.swarm/pending/`. Both shapes resolve here so
# neither the skill nor an existing repo has to migrate: per-cascade first,
# flat as fallback. Before this existed the docs described one layout and
# these scripts hardcoded another, so a per-cascade run silently found no
# briefs and skipped the leaf instead of failing.

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9-]")


def normalize_slug(name: str) -> str:
    """Lowercase, whitespace/underscore runs to one hyphen, strip the rest."""
    collapsed = re.sub(r"[\s_]+", "-", str(name).strip().lower())
    return _SLUG_STRIP_RE.sub("", collapsed).strip("-")


def cascade_candidates(root: Path) -> list[str]:
    """Every `.swarm/<slug>/briefs/` directory present, by slug."""
    swarm = root / ".swarm"
    if not swarm.is_dir():
        return []
    return sorted({p.parent.name for p in swarm.glob("*/briefs") if p.is_dir()})


def discover_cascade_slug(root: Path, explicit: str | None = None) -> str | None:
    """Explicit --cascade wins. Otherwise auto-resolve only when exactly one
    cascade dir exists; ambiguity returns None so the caller can ask rather
    than guess which cascade the user meant."""
    if explicit:
        # A slug that names a directory on disk wins as-is. Normalization maps
        # `_` to `-`, but real cascades predate that rule and use underscores;
        # rewriting their name silently resolves to a path that isn't there.
        if (root / ".swarm" / explicit).is_dir():
            return explicit
        return normalize_slug(explicit)
    found = cascade_candidates(root)
    return found[0] if len(found) == 1 else None


def resolve_briefs_dir(root: Path, cfg: dict[str, Any],
                       explicit: Path | None = None,
                       cascade: str | None = None) -> Path:
    if explicit:
        return explicit
    if "briefs_dir" in cfg.get("_user_keys", frozenset()):
        return root / cfg["briefs_dir"]
    slug = discover_cascade_slug(root, cascade)
    if slug:
        candidate = root / ".swarm" / slug / "briefs"
        if candidate.is_dir():
            return candidate
    return root / cfg["briefs_dir"]


def staging_candidates(root: Path, leaf_id: str, shard: str = "",
                       slug: str | None = None) -> list[Path]:
    """Staging dirs to try, most specific first. The shard-scoped shapes are
    what SKILL.md's "Shards" section prescribes; they were previously
    resolved by no script at all."""
    swarm = root / ".swarm"
    bases = ([swarm / slug / "pending"] if slug else []) + [swarm / "pending"]
    out: list[Path] = []
    for base in bases:
        if shard:
            out.append(base / shard / leaf_id)
        out.append(base / leaf_id)
    return out


def resolve_staging_dir(root: Path, leaf_id: str, shard: str = "",
                        slug: str | None = None,
                        explicit: Path | None = None) -> Path:
    if explicit:
        return explicit
    candidates = staging_candidates(root, leaf_id, shard, slug)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


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
    # Required, not defaulted. /manager-mode 2.6 gives test authorship to the
    # shard-test-writer, so every brief it emits is `parent`; a silent default
    # meant a brief that simply forgot the line still parsed as something. An
    # omitted field cannot mean the wrong thing if it cannot be omitted.
    "test_owned_by",
)

TEST_OWNED_BY_VALUES = ("parent", "leaf")


def check_schema(briefs: list[Brief]) -> list[Failure]:
    fails: list[Failure] = []
    seen_ids: set[str] = set()
    for b in briefs:
        for field_name in REQUIRED_FIELDS:
            if field_name in ("test_file", "impl_file"):
                # Satisfied by the singular field OR a non-empty plural
                # `*_files` list — a brief legitimately using only the
                # plural form (e.g. a genuinely 2-file leaf with no single
                # "primary" file) is not missing anything. Two independent
                # live runs hit this as a false schema failure before this
                # fix — see REPORT.md Phase D.
                plural = b.frontmatter.get(f"{field_name}s")
                if field_name in b.frontmatter or (isinstance(plural, list) and plural):
                    continue
                fails.append(Failure(b.leaf_id, "schema",
                    f"missing `{field_name}` (and no non-empty `{field_name}s` list either)"))
                continue
            if field_name not in b.frontmatter:
                fails.append(Failure(b.leaf_id, "schema",
                    f"missing required field `{field_name}`"))
        owned_by = b.frontmatter.get("test_owned_by")
        if owned_by is not None and str(owned_by).lower() not in TEST_OWNED_BY_VALUES:
            fails.append(Failure(b.leaf_id, "schema",
                f"test_owned_by `{owned_by}` is not one of "
                f"{'/'.join(TEST_OWNED_BY_VALUES)}"))
        if b.leaf_id in seen_ids:
            fails.append(Failure(b.leaf_id, "schema",
                f"duplicate leaf_id `{b.leaf_id}` across briefs"))
        seen_ids.add(b.leaf_id)
    return fails


def _leaf_paths(b: Brief, kind: str) -> list[str]:
    """Return all paths a leaf claims for `kind` ('test' or 'impl').

    Combines singular `<kind>_file` + optional plural `<kind>_files`,
    deduped (order preserved) — a brief that repeats the same path in both
    fields is not claiming it twice, and check_non_overlap must not treat a
    brief as colliding with itself over that. Two independent live runs hit
    this as a false non-overlap failure before the dedup was added — see
    REPORT.md Phase D.
    """
    out: list[str] = []
    singular = b.frontmatter.get(f"{kind}_file")
    if isinstance(singular, str):
        out.append(singular)
    plural = b.frontmatter.get(f"{kind}_files") or []
    if isinstance(plural, list):
        out.extend(p for p in plural if isinstance(p, str))
    return list(dict.fromkeys(out))


def _wave(b: Brief) -> int:
    w = b.frontmatter.get("wave", 1)
    try:
        return int(w)
    except (TypeError, ValueError):
        return 1


def _shard(b: Brief) -> str:
    """Shard id a brief belongs to, for concurrently-running waves.

    Explicit `shard:` frontmatter wins. Otherwise infer from a `shard-<id>/`
    parent directory (briefs discovered under `<briefs_dir>/shard-*/leaf-*.md`).
    Empty string means "no shard" — the single-wave-at-a-time default, where
    only the existing per-wave non-overlap check applies.
    """
    explicit = b.frontmatter.get("shard")
    if isinstance(explicit, str) and explicit:
        return explicit
    # Only the brief's OWN directory, never an arbitrary ancestor. Walking
    # every parent meant a project checked out under any path containing a
    # `shard-*` component inherited a phantom shard on every brief, which
    # pushes staging resolution at `pending/<shard>/leaf-NN/` — a directory
    # that does not exist — ahead of the real one.
    parent = b.path.parent.name
    return parent if parent.startswith("shard-") else ""


def _test_owned_by_leaf(b: Brief) -> bool:
    """True when the leaf itself owns its test files.

    `test_owned_by` is a REQUIRED field (see REQUIRED_FIELDS), so for any
    schema-valid brief this reads a value that is actually present. The
    fallback below is only reached by a brief that already failed schema, and
    it deliberately falls to the stricter side (`leaf` keeps the test paths
    inside the non-overlap and parent-owned checks)."""
    return str(b.frontmatter.get("test_owned_by", "leaf")).lower() == "leaf"


def check_non_overlap(briefs: list[Brief], parent_owned: list[str]) -> list[Failure]:
    fails: list[Failure] = []
    # Owner is scoped per (shard, wave): leaves in different waves of the SAME
    # shard run sequentially, so editing the same file across waves is fine
    # (and common for follow-ups). Shard defaults to "" when unused, so this
    # collapses to the original per-wave-only key for single-shard projects.
    owner: dict[tuple[str, int, str], str] = {}
    # Cross-shard owner is scoped by path only, no wave: shards run
    # CONCURRENTLY (that's the point of sharding — see "Shard-based
    # parallelism" in SKILL.md), so two different shards ever claiming the
    # same path is always a collision, regardless of their wave numbers.
    cross_shard_owner: dict[str, tuple[str, str]] = {}  # path -> (shard, leaf_id)
    for b in briefs:
        b_wave = _wave(b)
        b_shard = _shard(b)
        # impl paths always leaf-owned; test paths only if test_owned_by=leaf
        path_specs: list[tuple[str, str, bool]] = []
        for p in _leaf_paths(b, "impl"):
            path_specs.append(("impl_file", p, True))
        for p in _leaf_paths(b, "test"):
            path_specs.append(("test_file", p, _test_owned_by_leaf(b)))

        for key, path, leaf_owned in path_specs:
            # parent_owned glob check only applies to leaf-claimed-ownership paths
            if leaf_owned:
                wkey = (b_shard, b_wave, path)
                if wkey in owner:
                    fails.append(Failure(b.leaf_id, "non-overlap",
                        f"{key} `{path}` already owned by {owner[wkey]}"))
                else:
                    owner[wkey] = b.leaf_id
                if b_shard:
                    prior = cross_shard_owner.get(path)
                    if prior is not None and prior[0] != b_shard:
                        fails.append(Failure(b.leaf_id, "non-overlap",
                            f"{key} `{path}` claimed by shard `{prior[0]}` "
                            f"(leaf {prior[1]}) — shards run concurrently, "
                            f"no file may be owned by more than one shard"))
                    else:
                        cross_shard_owner.setdefault(path, (b_shard, b.leaf_id))
                for glob in parent_owned:
                    if fnmatch.fnmatch(path, glob):
                        fails.append(Failure(b.leaf_id, "non-overlap",
                            f"{key} `{path}` matches parent-owned glob `{glob}`"))

        # do_not_edit must include every same-wave, same-shard sibling's
        # leaf-owned files. Cross-shard collisions are already fully forbidden
        # above (cross_shard_owner) — shards must never overlap at all, not
        # just declare it — so this sibling check stays scoped to leaves that
        # actually run alongside each other: same shard, same wave.
        do_not = set(b.frontmatter.get("do_not_edit") or [])
        b_wave = _wave(b)
        for other in briefs:
            if other.leaf_id == b.leaf_id:
                continue
            if _shard(other) != b_shard:
                continue  # different shard — no shared parallelism, and
                          # any path overlap was already caught above
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


_TASK_HEADING_RE = re.compile(r"^##\s+Task\s*$", re.MULTILINE)
_NEXT_HEADING_RE = re.compile(r"^##\s+\S", re.MULTILINE)


def _extract_task_section(body: str) -> str:
    """Return the text of the brief's `## Task` section only.

    The ambiguous-verb scan must judge leaf-authored task prose, not the
    brief-template's own boilerplate (`## Acceptance`, `## Escalation
    triggers`, `## Assumption log`, etc.) which legitimately uses words
    like "resolve" or "determine" in instructions to the leaf, not as a
    delegated design decision. Returns the whole body if no `## Task`
    heading is found (fails safe toward scanning too much, not too little).
    """
    m = _TASK_HEADING_RE.search(body)
    if not m:
        return body
    start = m.end()
    next_m = _NEXT_HEADING_RE.search(body, start)
    end = next_m.start() if next_m else len(body)
    return body[start:end]


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
        # Task-section prose scanned for ambiguous verbs (not the whole
        # body — Acceptance/Escalation/Assumption-log boilerplate can
        # legitimately use these words without delegating a design decision)
        task_prose = _extract_task_section(b.body)
        for pat in verb_patterns:
            m = pat.search(task_prose)
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


SPEC_LINK_RE = re.compile(r"^(?:#|--|//)\s*spec:\s*\S+::.+?::AC-\d+", re.MULTILINE)


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


_CONTRADICTION_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*==\s*(-?\d+\.?\d*)")


def check_no_contradiction(briefs: list[Brief], root: Path) -> list[Failure]:
    """Best-effort heuristic: flag the same identifier asserted to two different
    literal values across sibling (same wave/shard) briefs' test files — a rule
    stated two ways with no stated ground truth, left for a leaf to guess at.
    Not an exhaustive contradiction prover; catches the C3-class defect (see
    playbook.md) cheaply before any leaf spawns.
    """
    groups: dict[tuple[int, str], list[Brief]] = {}
    for b in briefs:
        groups.setdefault((_wave(b), _shard(b)), []).append(b)
    fails: list[Failure] = []
    for group in groups.values():
        seen: dict[str, tuple[str, str, str]] = {}  # identifier -> (value, leaf_id, path)
        for b in group:
            for path in _leaf_paths(b, "test"):
                p = root / path
                if not p.exists():
                    continue
                for line in p.read_text().splitlines():
                    if "assert" not in line:
                        continue
                    for ident, val in _CONTRADICTION_RE.findall(line):
                        prior = seen.get(ident)
                        if prior is None:
                            seen[ident] = (val, b.leaf_id, path)
                        elif prior[0] != val and prior[1] != b.leaf_id:
                            fails.append(Failure(b.leaf_id, "no-contradiction",
                                f"`{ident} == {val}` in {path} contradicts "
                                f"`{ident} == {prior[0]}` asserted by {prior[1]} "
                                f"in {prior[2]} — same wave/shard, unresolved "
                                f"before any leaf spawns"))
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


def check_shard_sizing(briefs: list[Brief],
                       invariants: dict[str, Any]) -> list[Failure]:
    """One shard is one shard-test-writer, and that agent holds the whole
    shard's brief set plus every impl file its tests target before it emits a
    line of test code. The wave's own 16-leaf cap is sized for a different
    load (staging isolation + the overlord's brief writing) and is far too
    loose here — see SKILL.md "Shards". A wave past the cap must be split
    into `ceil(leaves / max_leaves_per_shard)` shards; a wave at or under it
    needs no shard at all.
    """
    cap = int(invariants["max_leaves_per_shard"])
    groups: dict[tuple[int, str], list[Brief]] = {}
    for b in briefs:
        groups.setdefault((_wave(b), _shard(b)), []).append(b)

    fails: list[Failure] = []
    for (wave, shard), members in sorted(groups.items()):
        if len(members) <= cap:
            continue
        label = f"wave-{wave}/{shard or 'default'}"
        ids = ", ".join(sorted(b.leaf_id for b in members))
        needed = -(-len(members) // cap)  # ceil
        fails.append(Failure(label, "shard-sizing",
            f"{len(members)} leaves in one shard ({ids}) exceeds "
            f"max_leaves_per_shard={cap} — one shard is one shard-test-writer, "
            f"and that context cannot hold {len(members)} leaves' briefs, "
            f"target impl and test output at once. Split into {needed} shards "
            f"(set `shard:` per brief, or move them under "
            f"`<briefs_dir>/shard-<id>/`), keeping leaves whose ACs cite each "
            f"other's symbols or units in the SAME shard"))
    return fails


# ---------- driver ----------

def audit(briefs_dir: Path, cfg: dict[str, Any], root: Path) -> Report:
    rpt = Report()
    # Flat `leaf-*.md` (the single-wave default) plus `shard-*/leaf-*.md`
    # (see "Shards" in SKILL.md). A project with no shards has zero
    # matches for the second glob, so this is a no-op for every existing
    # single-wave setup.
    #
    # `path.stem` on a real brief ("leaf-03.md") has no dot ("leaf-03"). The
    # brief template's own convention for sidecar files — leaf-03.ASSUMPTIONS.md,
    # leaf-03.ESCALATION.md, leaf-03.RESULT.md — all match the `leaf-*.md`
    # glob too, since `*` is greedy across dots, and get misparsed as
    # malformed briefs (no frontmatter) otherwise. Filter them out by the
    # dot they always carry that a real leaf id never does.
    paths = sorted(
        p for p in briefs_dir.glob("leaf-*.md") if "." not in p.stem
    ) + sorted(
        p for p in briefs_dir.glob("shard-*/leaf-*.md") if "." not in p.stem
    )
    for path in paths:
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
    rpt.failures.extend(check_shard_sizing(rpt.briefs, cfg["invariants"]))
    rpt.failures.extend(check_spec_link(rpt.briefs, root))
    rpt.failures.extend(check_no_contradiction(rpt.briefs, root))
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
    p.add_argument("--cascade",
        help="cascade slug for `.swarm/<slug>/...` layouts; auto-detected when "
             "exactly one exists")
    args = p.parse_args(argv)

    root = git_root(args.root)
    cfg = load_config(root)
    briefs_dir = resolve_briefs_dir(root, cfg, args.briefs_dir, args.cascade)
    if not briefs_dir.exists():
        print(f"briefs_dir not found: {briefs_dir}", file=sys.stderr)
        found = cascade_candidates(root)
        if len(found) > 1 and not args.cascade:
            print(f"multiple cascades present ({', '.join(found)}); "
                  f"pass --cascade <slug>", file=sys.stderr)
        return 2
    rpt = audit(briefs_dir, cfg, root)
    print(render(rpt))
    return 0 if rpt.passed else 1


if __name__ == "__main__":
    sys.exit(main())
