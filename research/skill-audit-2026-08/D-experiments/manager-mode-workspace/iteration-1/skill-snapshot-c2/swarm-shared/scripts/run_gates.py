#!/usr/bin/env python3
"""One gate pass for one leaf. Invoked by /manager-mode Phase 6.5.

Why this exists
---------------
Before this script, Phase 6 was a list of gates written in prose. An overlord
that ran all of them and one that ran none produced the same visible output: a
clean report and a row in post-review-log.md. A survey of 64 brief-carrying
cascades found the predictable result — `BOUNDARIES.md` present 0 times,
`TEST-AUDIT.md` 6 times, the wave snapshot 12 times, and 13 of 15
post-review-log files holding a header and no rows at all.

So this runner does three things prose cannot:

1. **Checks that the upstream artifacts exist.** A gate whose input is missing
   is not a passing gate, it is an absent one. G5 without a snapshot and G7
   without a sweep both used to read as silence.
2. **Runs every scripted gate itself**, rather than naming four commands and
   trusting each to be typed.
3. **Writes GATES.md as a byproduct.** Evidence the overlord has to remember to
   write is evidence that goes missing exactly when it matters most.

What it deliberately does NOT do
--------------------------------
It never mutates the project. No merge, no reset, no umbrella run, no log
row — every git call here is a read-only query. Admission changes state and
belongs to `worktree_ops.py admit`, which refuses to run until this runner has
written a GATES.md with no FAIL row. The one file it writes is its own report.

Exit codes: 0 all gates pass, 1 blocking findings, 2 resolution/config error.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_invariants as ci  # noqa: E402
import worktree_ops as wo  # noqa: E402


SCRIPT_DIR = Path(__file__).resolve().parent

# Gates delegated to their own scripts. `advisory_by_default` mirrors each
# script's own posture: reachability blocks, heuristics advise unless --strict.
DELEGATED = (
    ("G8", "test_quality_gate.py"),
    ("G9", "complexity_gate.py"),
    ("G10", "scale_gate.py"),
)

# Test-runner scratch. The leaf runs its own test command inside its sandbox,
# so a passing test leaves these behind; without the exclusion every Python
# leaf trips G5 on caches its own green test wrote.
DEFAULT_IGNORE = (
    ".git/**", ".swarm/**", "__pycache__/**", "node_modules/**", ".venv/**",
    "*.pyc", ".pytest_cache/**", ".mypy_cache/**", ".ruff_cache/**",
    ".coverage", "htmlcov/**", "*.egg-info/**",
)


@dataclass
class GateResult:
    gate: str
    status: str          # PASS | FAIL | ADVISORY | SKIP
    evidence: str
    timestamp: str = field(default_factory=lambda: _now())

    @property
    def blocking(self) -> bool:
        return self.status == "FAIL"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()


def find_brief(briefs_dir: Path, leaf_id: str) -> ci.Brief | None:
    """Duplicated from the sibling gate scripts, for the reason scale_gate.py
    records: only check_invariants is a shared import, and one runner is not
    reason enough to start a web of cross-script imports."""
    for path in (sorted(briefs_dir.glob("leaf-*.md"))
                 + sorted(briefs_dir.glob("shard-*/leaf-*.md"))):
        b = ci.parse_brief(path)
        if b is not None and b.leaf_id == leaf_id:
            return b
    return None


def _ignored(rel: str, patterns: tuple[str, ...] | list[str]) -> bool:
    """Match a pattern at ANY depth, not only at the repo root.

    `.git/**` has to catch `vendor/thing/.git/config` too. A monorepo with a
    nested checkout otherwise reports several hundred undeclared differences,
    every one of them somebody else's git objects.
    """
    parts = rel.split("/")
    candidates = ["/".join(parts[i:]) for i in range(len(parts))]
    for pat in patterns:
        prefix = pat.rstrip("*").rstrip("/")
        for cand in candidates:
            if fnmatch.fnmatch(cand, pat):
                return True
            if prefix and (cand == prefix or cand.startswith(prefix + "/")):
                return True
    return False


def _walk(root: Path, patterns: tuple[str, ...] | list[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if _ignored(rel, patterns):
            continue
        out[rel] = path
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------- cascade-scoped paths ----------

def cascade_dir(root: Path, slug: str | None) -> Path:
    return (root / ".swarm" / slug) if slug else (root / ".swarm")


def _first_existing(candidates: list[Path]) -> Path | None:
    for c in candidates:
        if c.exists():
            return c
    return None


def resolve_worktree_dir(root: Path, leaf_id: str, slug: str | None,
                         explicit: Path | None) -> Path | None:
    """The leaf's git worktree (Phase 4.1). None once it has been admitted or
    reverted — both remove the worktree, and both happen after this runner."""
    if explicit:
        return explicit if explicit.is_dir() else None
    return _first_existing([cascade_dir(root, slug) / "worktrees" / leaf_id])


def resolve_base(root: Path, slug: str | None, wave: int) -> Path | None:
    """wave-N.base.json, written by worktree_ops.py base (Phase 4.0)."""
    return _first_existing([
        cascade_dir(root, slug) / f"wave-{wave}.base.json",
        root / ".swarm" / f"wave-{wave}.base.json",
    ])


def _git(args: list[str], cwd: Path) -> str | None:
    """Read-only git query; None when git refuses. This runner never mutates."""
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return proc.stdout.rstrip("\n") if proc.returncode == 0 else None


def _porcelain_paths(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path.strip().strip('"').rstrip("/"))
    return out


def resolve_sweep(root: Path, slug: str | None, wave: int) -> Path | None:
    return _first_existing([
        cascade_dir(root, slug) / f"wave-{wave}.SWEEP.md",
        root / ".swarm" / f"wave-{wave}.SWEEP.md",
    ])


def audit_dir(root: Path, slug: str | None, wave: int, shard: str) -> Path:
    """Canonical location, with the two legacy shapes real cascades used.

    Path drift here is not hypothetical: audit dirs have been found at
    `.swarm/audits/wave-N/<slug>/` and at `.swarm/audits/wave-N/default/`.
    Resolving only the canonical shape would report "Phase 3.4 never ran"
    for a shard whose audit is sitting right there under another name.
    """
    canonical = cascade_dir(root, slug) / "audits" / f"wave-{wave}" / (shard or "default")
    legacy = [
        root / ".swarm" / "audits" / f"wave-{wave}" / (slug or ""),
        root / ".swarm" / "audits" / f"wave-{wave}" / (shard or "default"),
    ]
    if canonical.is_dir():
        return canonical
    for candidate in legacy:
        if candidate.is_dir():
            return candidate
    return canonical


def gates_path(root: Path, slug: str | None, wave: int, leaf_id: str) -> Path:
    """Evidence lives one level above the shard dirs: 6.0 checks prior leaves
    without knowing which shard each of them belonged to."""
    return cascade_dir(root, slug) / "audits" / f"wave-{wave}" / f"{leaf_id}.GATES.md"


def ledger_dir(root: Path, slug: str | None, name: str) -> Path | None:
    return _first_existing([
        cascade_dir(root, slug) / name,
        root / ".swarm" / name,
    ])


# ---------- artifact preconditions ----------

def check_artifacts(root: Path, slug: str | None, wave: int, shard: str,
                    briefs_dir: Path, leaf_id: str,
                    require_boundaries: bool) -> list[GateResult]:
    """The upstream artifacts each later gate reads.

    Every one of these is described in SKILL.md as required or blocking, and
    every one was routinely absent in practice — because a missing input made
    its gate silent rather than loud.
    """
    out: list[GateResult] = []

    base = resolve_base(root, slug, wave)
    out.append(GateResult(
        "A1 wave-baseline snapshot",
        "PASS" if base else "FAIL",
        str(base.relative_to(root)) if base
        else f"no wave-{wave}.base.json — Phase 4.0 never ran (worktree_ops.py base), so "
             f"file-match and G5 have no base commit to diff against",
    ))

    sweep = resolve_sweep(root, slug, wave)
    if not sweep:
        out.append(GateResult("A2 assumption-sweep (G7)", "FAIL",
                              f"no wave-{wave}.SWEEP.md — Phase 5.2 never ran"))
    else:
        newest = 0.0
        stale: list[str] = []
        for a in sorted(briefs_dir.glob("leaf-*.ASSUMPTIONS.md")):
            mtime = a.stat().st_mtime
            newest = max(newest, mtime)
            if mtime > sweep.stat().st_mtime:
                stale.append(a.name)
        if stale:
            out.append(GateResult(
                "A2 assumption-sweep (G7)", "FAIL",
                f"{sweep.name} is older than {', '.join(stale)} — re-run Phase 5.2"))
        else:
            out.append(GateResult("A2 assumption-sweep (G7)", "PASS",
                                  f"{sweep.name} newer than every ASSUMPTIONS"))

    adir = audit_dir(root, slug, wave, shard)
    test_audit = adir / "TEST-AUDIT.md"
    out.append(GateResult(
        "A3 pre-impl test audit", "PASS" if test_audit.exists() else "FAIL",
        str(test_audit.relative_to(root)) if test_audit.exists()
        else f"no TEST-AUDIT.md at {adir.relative_to(root)} — Phase 3.4 never "
             f"ran for this shard, so no leaf's test was reviewed",
    ))

    boundaries = adir / "BOUNDARIES.md"
    if boundaries.exists():
        out.append(GateResult("A4 boundary sweep", "PASS",
                              str(boundaries.relative_to(root))))
    else:
        out.append(GateResult(
            "A4 boundary sweep", "FAIL" if require_boundaries else "ADVISORY",
            f"no BOUNDARIES.md at {adir.relative_to(root)} — Phase 2.6's sweep "
            f"has no recorded output"))
    return out


# ---------- per-leaf gates ----------

def _changed_set(root: Path, base_sha: str, leaf_rec: dict[str, Any],
                 worktree: Path | None, ignore: list[str]) -> tuple[set[str] | None, str]:
    """What the leaf produced: its commit's diff against base, or — before
    Phase 5.1 committed — the worktree's uncommitted changes."""
    commit = leaf_rec.get("commit")
    if commit:
        out = _git(["diff", "--name-only", f"{base_sha}..{commit}"], root)
        if out is None:
            return None, f"cannot diff {base_sha[:12]}..{commit[:12]}"
        return set(out.split()), f"commit {commit[:12]}"
    if worktree is not None:
        out = _git(["status", "--porcelain", "--untracked-files=all"], worktree)
        if out is None:
            return None, f"git status failed in {worktree}"
        return {p for p in _porcelain_paths(out) if not _ignored(p, ignore)}, "uncommitted worktree"
    return None, "no commit recorded and no worktree present"


def check_file_match(root: Path, base_sha: str, leaf_rec: dict[str, Any],
                     worktree: Path | None, declared: list[str],
                     impl_files: list[str], ignore: list[str]) -> GateResult:
    """6.3. Everything the leaf changed is declared, and every declared impl
    file exists on its branch. Unchanged parent-owned test files are declared
    but legitimately absent from the diff — the leaf may not touch them."""
    changed, where = _changed_set(root, base_sha, leaf_rec, worktree, ignore)
    if changed is None:
        return GateResult("6.3 file-match", "FAIL", where)
    want = set(declared)
    extra = sorted(changed - want)
    ref = leaf_rec.get("commit")
    missing = []
    for rel in impl_files:
        if ref:
            present = _git(["cat-file", "-e", f"{ref}:{rel}"], root) is not None
        else:
            present = worktree is not None and (worktree / rel).exists()
        if not present:
            missing.append(rel)
    if not extra and not missing:
        return GateResult("6.3 file-match", "PASS",
                          f"{len(changed)} changed path(s) ⊆ {len(want)} declared; "
                          f"all {len(impl_files)} impl file(s) present ({where})")
    bits = []
    if missing:
        bits.append(f"missing {missing}")
    if extra:
        bits.append(f"unexpected {extra}")
    return GateResult("6.3 file-match", "FAIL", "; ".join(bits) + f" ({where})")


def check_parent_owned(brief: ci.Brief, declared: list[str],
                       parent_owned: list[str]) -> GateResult:
    """Impl paths always. Test paths only when the LEAF owns them.

    Under `test_owned_by: parent` the tests were authored on the parent side
    and legitimately live in parent territory — checking them here would fail
    every leaf in the default configuration.
    """
    checked = list(ci._leaf_paths(brief, "impl"))
    if ci._test_owned_by_leaf(brief):
        checked += ci._leaf_paths(brief, "test")
    hits = [(p, g) for p in checked for g in parent_owned if fnmatch.fnmatch(p, g)]
    if hits:
        detail = ", ".join(f"`{p}` matches `{g}`" for p, g in hits)
        return GateResult("G1 parent-owned", "FAIL", detail)
    exempt = len(declared) - len(checked)
    note = f" ({exempt} parent-authored test path(s) exempt)" if exempt else ""
    return GateResult("G1 parent-owned", "PASS",
                      f"{len(checked)} leaf-owned path(s) vs "
                      f"{len(parent_owned)} parent_owned glob(s){note}")


def check_assumptions(briefs_dir: Path, leaf_id: str) -> GateResult:
    path = briefs_dir / f"{leaf_id}.ASSUMPTIONS.md"
    if path.exists():
        return GateResult("G2 ASSUMPTIONS", "PASS", f"{path.name} present")
    return GateResult("G2 ASSUMPTIONS", "ADVISORY",
                      "no ASSUMPTIONS file — expected when the brief was concrete")


UNANSWERED_RE = re.compile(r"unanswered:\s*true", re.IGNORECASE)


def check_questions(root: Path, slug: str | None, briefs_dir: Path,
                    leaf_id: str) -> GateResult:
    qdir = ledger_dir(root, slug, "questions")
    if qdir is None:
        return GateResult("G3 open-question", "PASS", "no question ledger")
    questions = sorted(qdir.glob(f"{leaf_id}-Q*.md"))
    if not questions:
        return GateResult("G3 open-question", "PASS", "no questions published")
    adir = ledger_dir(root, slug, "answers")
    assumptions = briefs_dir / f"{leaf_id}.ASSUMPTIONS.md"
    logged = assumptions.read_text() if assumptions.exists() else ""
    unresolved = []
    for q in questions:
        qid = q.stem.split("-")[-1]
        answered = adir is not None and (adir / f"{leaf_id}-{qid}.md").exists()
        # A question with neither an answer nor an `unanswered: true` entry is
        # a decision the leaf made silently — the one outcome the ledger exists
        # to make impossible.
        if not answered and not UNANSWERED_RE.search(logged):
            unresolved.append(q.name)
    if unresolved:
        return GateResult("G3 open-question", "FAIL",
                          f"no answer and no `unanswered: true` for {unresolved}")
    return GateResult("G3 open-question", "PASS",
                      f"{len(questions)} question(s), each answered or tagged")


def check_proposals(root: Path, slug: str | None, leaf_id: str) -> GateResult:
    pdir = ledger_dir(root, slug, "proposals")
    path = (pdir / f"{leaf_id}.md") if pdir else None
    if path is None or not path.exists():
        return GateResult("G4 contract-proposal", "PASS", "no proposal filed")
    text = path.read_text()
    m = re.search(r"^status:\s*(\S+)", text, re.MULTILINE)
    status = m.group(1).lower() if m else "missing"
    if status == "pending":
        return GateResult("G4 contract-proposal", "FAIL",
                          f"{path.name} is still `status: pending`")
    return GateResult("G4 contract-proposal", "PASS", f"{path.name} is `{status}`")


def check_footprint(root: Path, base_sha: str | None, leaf_rec: dict[str, Any],
                    worktree: Path | None, declared: list[str],
                    ignore: list[str]) -> list[GateResult]:
    """G5. Every path the leaf changed must be declared, and the leaf must not
    have run git itself (its commit sits exactly one step above base; its
    worktree HEAD is base until Phase 5.1 commits).

    Live-tree drift in the user's checkout is reported as ADVISORY, not FAIL:
    admission never writes to that tree any more, so drift there cannot
    corrupt an admission — and blocking on it is what produced the hand-written
    G5 waivers in every real cascade.
    """
    if base_sha is None:
        return [GateResult("G5 footprint", "FAIL", "no wave base to compare against")]
    out: list[GateResult] = []
    declared_set = set(declared)
    offenders: list[str] = []
    ran_git: list[str] = []
    commit = leaf_rec.get("commit")
    if commit:
        parents = (_git(["rev-parse", f"{commit}^@"], root) or "").split()
        if parents != [base_sha]:
            ran_git.append(f"commit {commit[:12]} is not exactly one step above base "
                           f"{base_sha[:12]} (parents {[p[:12] for p in parents]})")
        for rel in (_git(["diff", "--name-only", f"{base_sha}..{commit}"], root) or "").split():
            if rel not in declared_set:
                offenders.append(f"branch:{rel}")
    if worktree is not None:
        head = _git(["rev-parse", "HEAD"], worktree)
        expect = commit or base_sha
        if head != expect:
            ran_git.append(f"worktree HEAD {str(head)[:12]} != {expect[:12]}: the leaf ran git")
        status = _git(["status", "--porcelain", "--untracked-files=all"], worktree) or ""
        for rel in _porcelain_paths(status):
            if _ignored(rel, ignore):
                continue
            if commit or rel not in declared_set:
                offenders.append(f"worktree:{rel}")
    if ran_git:
        out.append(GateResult("G5 footprint", "FAIL", "; ".join(ran_git)))
    elif offenders:
        out.append(GateResult("G5 footprint", "FAIL",
                              f"{len(offenders)} undeclared difference(s): {offenders[:8]}"))
    else:
        where = "commit" if commit else "worktree"
        out.append(GateResult("G5 footprint", "PASS",
                              f"every {where} difference is declared; leaf never ran git"))
    live = [p for p in _porcelain_paths(_git(["status", "--porcelain"], root) or "")
            if not _ignored(p, ignore)]
    if live:
        out.append(GateResult("G5 live-tree drift", "ADVISORY",
                              f"{len(live)} path(s) changed in the user's checkout during the wave "
                              f"(not blocking — admission merges into integration, never here): "
                              f"{['live:' + p for p in live[:8]]}"))
    return out


def check_escalations(brief: ci.Brief, root: Path, slug: str | None,
                      staging: Path, leaf_id: str) -> GateResult:
    triggers = brief.frontmatter.get("escalation_triggers") or []
    if not isinstance(triggers, list) or not triggers:
        return GateResult("G6 escalation-trigger", "SKIP", "no triggers declared")
    edir = ledger_dir(root, slug, "escalations")
    filed = edir is not None and (edir / f"{leaf_id}.md").exists()
    fired: list[str] = []
    for entry in triggers:
        if not isinstance(entry, dict) or not entry.get("detect"):
            continue
        proc = subprocess.run(
            entry["detect"], shell=True, cwd=root, capture_output=True,
            text=True, env={**os.environ, "STAGING_DIR": str(staging)},
        )
        if proc.returncode == 0:
            fired.append(str(entry.get("name", entry["detect"])))
    if fired and not filed:
        return GateResult("G6 escalation-trigger", "FAIL",
                          f"fired {fired} with no escalations/{leaf_id}.md")
    if fired:
        return GateResult("G6 escalation-trigger", "PASS",
                          f"fired {fired}, escalation filed")
    return GateResult("G6 escalation-trigger", "PASS", "no trigger fired")


def check_bypass(root: Path, slug: str | None, wave: int, briefs_dir: Path,
                 leaf_id: str) -> GateResult:
    """6.0. A log row records an admission; it is not evidence a gate ran.

    Requiring the GATES.md too is what distinguishes a loop that ran from a log
    filled in afterwards — the failure mode that produced five rows sharing one
    timestamp and no evidence files at all.
    """
    priors = [
        p.stem for p in sorted(briefs_dir.glob("leaf-*.md"))
        if "." not in p.stem and p.stem < leaf_id
    ]
    if not priors:
        return GateResult("6.0 bypass", "PASS", "first leaf of the wave")
    log = _first_existing([
        cascade_dir(root, slug) / "post-review-log.md",
        root / ".swarm" / "post-review-log.md",
    ])
    log_text = log.read_text() if log else ""
    missing: list[str] = []
    for prior in priors:
        has_row = re.search(rf"\|\s*{re.escape(prior)}\s*\|", log_text) is not None
        has_evidence = gates_path(root, slug, wave, prior).exists()
        if not (has_row and has_evidence):
            lack = []
            if not has_row:
                lack.append("log row")
            if not has_evidence:
                lack.append("GATES.md")
            missing.append(f"{prior} (no {' or '.join(lack)})")
    if missing:
        return GateResult("6.0 bypass", "FAIL",
                          f"prior leaves never gated: {missing}")
    return GateResult("6.0 bypass", "PASS",
                      f"{len(priors)} prior leaf/leaves each have a row and evidence")


def run_delegated(root: Path, leaf_id: str, slug: str | None,
                  briefs_dir: Path, staging: Path | None,
                  strict: bool) -> list[GateResult]:
    out: list[GateResult] = []
    for gate, script in DELEGATED:
        path = SCRIPT_DIR / script
        if not path.exists():
            out.append(GateResult(gate, "FAIL", f"{script} not installed"))
            continue
        cmd = [sys.executable, str(path), "--leaf", leaf_id,
               "--root", str(root), "--briefs-dir", str(briefs_dir)]
        if slug:
            cmd += ["--cascade", slug]
        if staging is not None:
            cmd += ["--staging-dir", str(staging)]
        if strict:
            cmd.append("--strict")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        tail = (proc.stdout.strip() or proc.stderr.strip() or "").splitlines()
        evidence = tail[-1] if tail else f"exit {proc.returncode}"
        out.append(GateResult(gate, "PASS" if proc.returncode == 0 else "FAIL",
                              evidence))
    return out


# ---------- report ----------

def render(leaf_id: str, wave: int, shard: str,
           results: list[GateResult]) -> str:
    lines = [
        f"# {leaf_id} gate evidence — wave {wave}"
        + (f", shard {shard}" if shard else ""),
        "",
        "Written by `run_gates.py`. Every row below is the result of a check",
        "that actually executed; a gate that did not run has no row.",
        "",
        "| gate | result | evidence | timestamp |",
        "|------|--------|----------|-----------|",
    ]
    for r in results:
        evidence = r.evidence.replace("|", "\\|")
        lines.append(f"| {r.gate} | {r.status} | {evidence} | {r.timestamp} |")
    blocking = [r for r in results if r.blocking]
    lines += [
        "",
        f"**Verdict: {'BLOCKED' if blocking else 'clear to admit'}** — "
        f"{len(blocking)} blocking, "
        f"{sum(1 for r in results if r.status == 'ADVISORY')} advisory, "
        f"{sum(1 for r in results if r.status == 'PASS')} pass.",
        "",
        "Admission itself (merge into integration, umbrella pre/post, log row)",
        "is `worktree_ops.py admit` and is deliberately not done here — this",
        "runner never mutates the project.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="/manager-mode Phase 6.5: run every gate for one leaf and "
                    "write its GATES.md evidence file")
    p.add_argument("--leaf", required=True, help="leaf_id, e.g. leaf-03")
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--briefs-dir", type=Path)
    p.add_argument("--cascade", help="cascade slug; auto-detected when exactly one exists")
    p.add_argument("--worktree-dir", type=Path,
                   help="default: <root>/.swarm/<cascade>/worktrees/<leaf>")
    p.add_argument("--wave", type=int, help="default: the brief's own wave")
    p.add_argument("--strict", action="store_true",
                   help="pass --strict to G8/G9/G10 and block on a missing "
                        "BOUNDARIES.md (manager-mode-hardcore)")
    p.add_argument("--out", type=Path, help="default: the shard's audit dir")
    args = p.parse_args(argv)

    root = wo.main_root(args.root.resolve())
    cfg = ci.load_config(root)
    slug = ci.discover_cascade_slug(root, args.cascade)
    briefs_dir = ci.resolve_briefs_dir(root, cfg, args.briefs_dir, args.cascade)
    if not briefs_dir.exists():
        print(f"briefs_dir not found: {briefs_dir}", file=sys.stderr)
        found = ci.cascade_candidates(root)
        if len(found) > 1 and not args.cascade:
            print(f"multiple cascades present ({', '.join(found)}); "
                  f"pass --cascade <slug>", file=sys.stderr)
        return 2

    brief = find_brief(briefs_dir, args.leaf)
    if brief is None:
        print(f"leaf `{args.leaf}` not found under {briefs_dir}", file=sys.stderr)
        return 2

    wave = args.wave if args.wave is not None else ci._wave(brief)
    shard = ci._shard(brief)
    declared = ci._leaf_paths(brief, "test") + ci._leaf_paths(brief, "impl")
    impl_files = ci._leaf_paths(brief, "impl")
    worktree = resolve_worktree_dir(root, args.leaf, slug, args.worktree_dir)
    ignore = wo.effective_ignore(cfg)
    base_path = resolve_base(root, slug, wave)
    base_data = json.loads(base_path.read_text()) if base_path else {}
    base_sha = base_data.get("base_sha")
    leaf_rec = (base_data.get("leaves") or {}).get(args.leaf) or {}
    # The worktree is the tree the delegated gates and G6 inspect: declared
    # files sit at their real paths there, exactly as staging used to hold them.
    tree = worktree if worktree is not None else root

    results: list[GateResult] = []
    results.append(check_bypass(root, slug, wave, briefs_dir, args.leaf))
    results += check_artifacts(root, slug, wave, shard, briefs_dir, args.leaf,
                               require_boundaries=args.strict)
    results.append(check_file_match(root, base_sha or "", leaf_rec, worktree,
                                    declared, impl_files, ignore))
    results.append(check_parent_owned(brief, declared, cfg["parent_owned"]))
    results.append(check_assumptions(briefs_dir, args.leaf))
    results.append(check_questions(root, slug, briefs_dir, args.leaf))
    results.append(check_proposals(root, slug, args.leaf))
    results += check_footprint(root, base_sha, leaf_rec, worktree, declared, ignore)
    results.append(check_escalations(brief, root, slug, tree, args.leaf))
    results += run_delegated(root, args.leaf, slug, briefs_dir, tree, args.strict)

    report = render(args.leaf, wave, shard, results)
    out = args.out or gates_path(root, slug, wave, args.leaf)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)

    print(report)
    print(f"evidence written to {out}")
    return 1 if any(r.blocking for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
