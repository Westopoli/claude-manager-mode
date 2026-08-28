#!/usr/bin/env python3
"""Git-worktree isolation for /manager-mode. The only place git runs.

Why this exists
---------------
Leaves used to build in a full copy of the project (`.swarm/<slug>/sandbox/`)
with a SHA-256 baseline for the footprint check and a copy-in/backup/restore
admission. Real cascades tripped the footprint gate on live-tree drift the
overlord had no way to prevent, and hand-wrote waiver scripts to get past it.
A git worktree gives the same isolation property — the leaf's test imports
impl at its real path inside a tree no sibling can touch — and lets git do the
bookkeeping: `status` says what a leaf changed, `diff --name-only` says what
its commit carries, a `--no-ff` merge is the admission, `reset --hard` is the
revert.

Roles
-----
* **Leaves never run git.** Their working directory is a checkout this script
  manages; the prompt says so.
* **The user's branch is written exactly twice**, both after confirmation:
  the base commit at Phase 4.0 (`base --commit-artifacts --yes`) and the final
  fast-forward (`finish --yes`). Everything else happens on
  `swarm/<slug>/leaf-NN` and `swarm/<slug>/integration`.
* **run_gates.py stays read-only.** `admit` refuses unless that runner has
  written `leaf-NN.GATES.md` with no FAIL row.

Subcommands (see SKILL.md Phases 0.0, 4.0, 4.1, 5.1, 6.6–6.9, 7)
-----------
  preflight --slug S                 refuse on non-git / dirty / detached / leftovers
  base      --slug S --wave N        record base sha, create integration branch+worktree
  add       --slug S --wave N        one worktree per brief in the wave (or --leaf ...)
  commit    --slug S --leaf L        stage+commit the leaf's declared files; refuse otherwise
  admit     --slug S --leaf L        merge into integration, umbrella pre/post, log row
  revert    --slug S --leaf L        undo a merge left in place by a same-count admit
  sync      --slug S --yes           ff the user's branch to integration (end of wave)
  finish    --slug S [--yes]         show pending commits; with --yes ff + cleanup
  status    --slug S                 list residual worktrees/branches (Phase 7 report)
  cleanup   --slug S [--purge --yes] remove leftovers; --purge also removes reverted/*

Exit codes: 0 ok, 1 refused/blocked, 2 config/resolution error, 3 needs --yes.
Every git call is appended to `.swarm/<slug>/git-ops.log`.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_invariants as ci  # noqa: E402

DEFAULT_IGNORE = (
    ".git/**", ".swarm/**", "__pycache__/**", "node_modules/**", ".venv/**",
    "*.pyc", ".pytest_cache/**", ".mypy_cache/**", ".ruff_cache/**",
    ".coverage", "htmlcov/**", "*.egg-info/**",
)
DEFAULT_LINK = ("node_modules", ".venv", "venv", "vendor", "target")
LOG_HEADER = (
    "# Post-Review Log — append-only, do not edit manually\n"
    "# Editing this file invalidates bypass-detection.\n\n"
    "| wave | shard | leaf_id | files | delta | timestamp | status | leaf_commit | merge_commit |\n"
    "|------|-------|---------|-------|-------|-----------|--------|-------------|--------------|\n"
)


class Refuse(Exception):
    """A deliberate stop with a message for the overlord; exit 1."""


class NeedsYes(Exception):
    """A step that writes the user's branch or destroys state; exit 3 without --yes."""


# ---------- paths ----------

@dataclass
class Ctx:
    root: Path            # MAIN checkout root (never a worktree)
    slug: str
    cfg: dict[str, Any]

    @property
    def cdir(self) -> Path:
        return self.root / ".swarm" / self.slug

    @property
    def int_dir(self) -> Path:
        return self.cdir / "worktrees" / "integration"

    def wt_dir(self, leaf: str) -> Path:
        return self.cdir / "worktrees" / leaf

    @property
    def int_branch(self) -> str:
        return f"swarm/{self.slug}/integration"

    def leaf_branch(self, leaf: str) -> str:
        return f"swarm/{self.slug}/{leaf}"

    def reverted_branch(self, leaf: str) -> str:
        return f"swarm/{self.slug}/reverted/{leaf}"

    def base_path(self, wave: int) -> Path:
        return self.cdir / f"wave-{wave}.base.json"

    @property
    def ops_log(self) -> Path:
        return self.cdir / "git-ops.log"

    @property
    def review_log(self) -> Path:
        return self.root / ".swarm" / "post-review-log.md"

    @property
    def briefs_dir(self) -> Path:
        return ci.resolve_briefs_dir(self.root, self.cfg, None, self.slug)


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def main_root(start: Path) -> Path:
    """The main checkout root even when invoked from inside a linked worktree.

    `--git-common-dir` prints a relative `.git` from the main checkout and an
    absolute path from a worktree (DRYRUN.md finding 6) — resolve before use.
    """
    try:
        out = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=start,
                             capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ci.git_root(start)
    common = (start / out).resolve() if not os.path.isabs(out) else Path(out).resolve()
    return common.parent


# ---------- git wrapper ----------

class Git:
    def __init__(self, log_path: Path | None):
        self.log_path = log_path

    def run(self, args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a") as fh:
                fh.write(f"{now()} | {cwd} | git {shlex.join(args)} | exit {proc.returncode}\n")
                if proc.returncode != 0 and proc.stderr.strip():
                    fh.write("    " + proc.stderr.strip().replace("\n", "\n    ") + "\n")
        if check and proc.returncode != 0:
            raise Refuse(f"git {shlex.join(args)} failed (exit {proc.returncode}): "
                         f"{proc.stderr.strip() or proc.stdout.strip()}")
        return proc

    def out(self, args: list[str], cwd: Path) -> str:
        # rstrip only: `status --porcelain` lines start with a significant space (" M path")
        return self.run(args, cwd).stdout.rstrip("\n")


# ---------- config helpers ----------

def cfg_list(cfg: dict[str, Any], new: str, old: str, default: tuple[str, ...]) -> list[str]:
    """Read a renamed config key, accepting the old name with a warning."""
    if new in cfg:
        return list(cfg[new])
    if old in cfg:
        print(f"note: `{old}` is deprecated; rename it to `{new}` in .claude-swarm.toml",
              file=sys.stderr)
        return list(cfg[old])
    return list(default)


def effective_ignore(cfg: dict[str, Any]) -> list[str]:
    """footprint_ignore ∪ worktree_link ∪ worktree_copy (DRYRUN.md finding 3:
    a symlink named `.venv` is NOT matched by the `.venv/` ignore pattern)."""
    ignore = cfg_list(cfg, "footprint_ignore", "snapshot_ignore", DEFAULT_IGNORE)
    ignore += cfg_list(cfg, "worktree_link", "sandbox_link", DEFAULT_LINK)
    ignore += list(cfg.get("worktree_copy") or [])
    return ignore


def _ignored(rel: str, patterns: list[str]) -> bool:
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


def porcelain_paths(text: str) -> list[str]:
    """Paths from `git status --porcelain` (handles renames `a -> b`)."""
    out = []
    for line in text.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path.strip().strip('"').rstrip("/"))
    return out


def plant_deps(ctx: Ctx, git: Git, wt: Path) -> list[str]:
    """Symlink worktree_link entries and copy worktree_copy entries into `wt`.
    Also write link names to the worktree's own exclude file so `git status`
    stays clean (belt) — effective_ignore filters them anyway (braces)."""
    planted: list[str] = []
    for name in cfg_list(ctx.cfg, "worktree_link", "sandbox_link", DEFAULT_LINK):
        src = ctx.root / name
        dst = wt / name
        if src.exists() and not dst.exists() and not dst.is_symlink():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(src, dst)
            planted.append(name)
    for rel in ctx.cfg.get("worktree_copy") or []:
        src = ctx.root / rel
        dst = wt / rel
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            planted.append(rel)
    if planted:
        exclude = Path(git.out(["rev-parse", "--git-path", "info/exclude"], wt))
        if not exclude.is_absolute():
            exclude = wt / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude.read_text() if exclude.exists() else ""
        with exclude.open("a") as fh:
            for name in planted:
                if name not in existing.splitlines():
                    fh.write(f"/{name}\n")
    return planted


# ---------- briefs ----------

def load_briefs(ctx: Ctx) -> dict[str, ci.Brief]:
    bd = ctx.briefs_dir
    out: dict[str, ci.Brief] = {}
    for path in sorted(bd.glob("leaf-*.md")) + sorted(bd.glob("shard-*/leaf-*.md")):
        if path.name.endswith(".ASSUMPTIONS.md"):
            continue
        b = ci.parse_brief(path)
        if b is not None:
            out[b.leaf_id] = b
    return out


def declared_paths(b: ci.Brief) -> list[str]:
    return ci._leaf_paths(b, "test") + ci._leaf_paths(b, "impl")


def brief_title(b: ci.Brief) -> str:
    m = re.search(r"^##\s+Task\s*\n+(.+)$", b.body, re.M)
    line = (m.group(1) if m else b.body.strip().splitlines()[0] if b.body.strip() else "").strip()
    return re.sub(r"\s+", " ", line)[:72]


def acceptance_cmd(b: ci.Brief) -> str | None:
    """First backticked command under `## Acceptance` that looks runnable."""
    m = re.search(r"^##\s+Acceptance\s*$(.*?)(?=^##\s|\Z)", b.body, re.M | re.S)
    if not m:
        return None
    for cmd in re.findall(r"`([^`\n]+)`", m.group(1)):
        if re.match(r"^(python3?|pytest|npm|npx|node|pnpm|yarn|bun|go|cargo|make|\./)", cmd.strip()):
            return cmd.strip()
    return None


# ---------- base.json ----------

def read_base(ctx: Ctx, wave: int) -> dict[str, Any]:
    p = ctx.base_path(wave)
    if not p.exists():
        raise Refuse(f"no {p.relative_to(ctx.root)} — run `base --slug {ctx.slug} --wave {wave}` first (Phase 4.0)")
    return json.loads(p.read_text())


def write_base(ctx: Ctx, wave: int, data: dict[str, Any]) -> None:
    ctx.base_path(wave).write_text(json.dumps(data, indent=1) + "\n")


def leaf_wave(ctx: Ctx, leaf: str) -> tuple[ci.Brief, int]:
    briefs = load_briefs(ctx)
    if leaf not in briefs:
        raise Refuse(f"leaf `{leaf}` not found under {ctx.briefs_dir}")
    return briefs[leaf], ci._wave(briefs[leaf])


# ---------- umbrella ----------

def named_passes(cmd: str, cwd: Path) -> tuple[set[str], int, bool]:
    """Run the umbrella command; return (named passes, count, count_only)."""
    argv = shlex.split(cmd)
    if "pytest" in cmd and "-v" not in argv:
        argv += ["-v", "--tb=no", "-q", "-p", "no:cacheprovider"]
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    text = proc.stdout + "\n" + proc.stderr
    names = {line.split(" ")[0] for line in text.splitlines() if " PASSED" in line}
    if names:
        return names, len(names), False
    m = re.search(r"(\d+) passed", text)
    if m:
        return set(), int(m.group(1)), True
    # JS runners: "Tests: N passed" or "✓ name"
    m = re.search(r"Tests:\s+(\d+) passed", text)
    if m:
        return set(), int(m.group(1)), True
    ticks = {line.strip() for line in text.splitlines() if line.strip().startswith(("✓", "✔", "ok "))}
    return ticks, len(ticks), not ticks


# ---------- post-review log ----------

def append_log(ctx: Ctx, wave: int, shard: str, leaf: str, files: list[str], delta: str,
               status: str, leaf_sha: str, merge_sha: str) -> None:
    log = ctx.review_log
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(LOG_HEADER)
    header_cols = 7
    for line in log.read_text().splitlines():
        if line.startswith("| wave"):
            header_cols = line.count("|") - 1
            break
    ts = now()
    if header_cols >= 9:
        row = f"| {wave} | {shard or 'default'} | {leaf} | {', '.join(files)} | {delta} | {ts} | {status} | {leaf_sha[:12]} | {merge_sha[:12] if merge_sha else '—'} |\n"
    else:  # legacy 7-column log: fold the shas into status so the table stays well-formed
        row = f"| {wave} | {shard or 'default'} | {leaf} | {', '.join(files)} | {delta} | {ts} | {status} (leaf {leaf_sha[:12]}{', merge ' + merge_sha[:12] if merge_sha else ''}) |\n"
    with log.open("a") as fh:
        fh.write(row)


def gates_clear(ctx: Ctx, wave: int, leaf: str) -> Path:
    p = ctx.cdir / "audits" / f"wave-{wave}" / f"{leaf}.GATES.md"
    if not p.exists():
        raise Refuse(f"no {p.relative_to(ctx.root)} — run run_gates.py --leaf {leaf} first (Phase 6.5)")
    fails = [line for line in p.read_text().splitlines() if "| FAIL |" in line]
    if fails:
        raise Refuse(f"{leaf} has blocking gates:\n  " + "\n  ".join(fails))
    return p


def append_gate_row(ctx: Ctx, wave: int, leaf: str, gate: str, result: str, evidence: str) -> None:
    p = ctx.cdir / "audits" / f"wave-{wave}" / f"{leaf}.GATES.md"
    if p.exists():
        with p.open("a") as fh:
            fh.write(f"\n| {gate} | {result} | {evidence.replace('|', '/')} | {now()} |\n")


# ---------- subcommands ----------

def cmd_preflight(ctx: Ctx, git: Git) -> int:
    r = ctx.root
    if git.run(["rev-parse", "--git-dir"], r, check=False).returncode != 0:
        raise Refuse("not a git repository — manager-mode requires git (worktree isolation)")
    branch = git.out(["rev-parse", "--abbrev-ref", "HEAD"], r)
    if branch == "HEAD":
        raise Refuse("detached HEAD — check out a branch before running a cascade")
    status = git.out(["status", "--porcelain", "--untracked-files=normal"], r)
    tracked = [l for l in status.splitlines() if not l.startswith("??")]
    untracked = [l[3:] for l in status.splitlines() if l.startswith("??")]
    problems: list[str] = []
    if tracked:
        problems.append("tracked changes present — commit or stash first:\n  " + "\n  ".join(tracked[:20]))
    wts = [l[9:] for l in git.out(["worktree", "list", "--porcelain"], r).splitlines() if l.startswith("worktree ")]
    leftovers_wt = [w for w in wts if str(ctx.cdir / "worktrees") in w]
    leftovers_br = git.out(["branch", "--list", "--format=%(refname:short)", f"swarm/{ctx.slug}/**"], r).split()
    if leftovers_wt or leftovers_br:
        problems.append(
            f"leftover state from a previous run of `{ctx.slug}`:\n"
            + "".join(f"  worktree {w}\n" for w in leftovers_wt)
            + "".join(f"  branch   {b}\n" for b in leftovers_br)
            + f"  → inspect, then `worktree_ops.py cleanup --slug {ctx.slug} --purge --yes`")
    if problems:
        raise Refuse("\n".join(problems))
    print(f"preflight ok: branch `{branch}`, clean tree, no swarm/{ctx.slug}/* leftovers")
    if untracked:
        print("note: untracked files will NOT exist inside leaf worktrees "
              "(add to `worktree_copy` if a leaf needs them):")
        for u in untracked[:20]:
            print(f"  {u}")
    return 0


def cmd_base(ctx: Ctx, git: Git, wave: int, commit_artifacts: bool, yes: bool) -> int:
    r = ctx.root
    status = git.out(["status", "--porcelain"], r)
    if status:
        paths = porcelain_paths(status)
        if not commit_artifacts:
            raise Refuse("uncommitted changes in the checkout — Phase 1–3 artifacts must be committed "
                         "before the wave base is taken. Either commit them yourself or re-run with "
                         "`--commit-artifacts --yes` to commit exactly these paths:\n  " + "\n  ".join(paths[:40]))
        if not yes:
            print("would commit these paths on the current branch (re-run with --yes):")
            for p in paths:
                print(f"  {p}")
            raise NeedsYes()
        git.run(["add", "-A", "--", *paths], r)
        git.run(["commit", "-q", "-m", f"swarm({ctx.slug}): wave {wave} base — spec/contract/umbrella/briefs/tests"], r)
        print(f"committed {len(paths)} artifact path(s) on the user's branch "
              f"(undo: git reset --soft HEAD~1)")
    user_branch = git.out(["rev-parse", "--abbrev-ref", "HEAD"], r)
    base = git.out(["rev-parse", "HEAD"], r)
    have_int = git.run(["show-ref", "--verify", "--quiet", f"refs/heads/{ctx.int_branch}"], r, check=False).returncode == 0
    if not have_int:
        git.run(["branch", ctx.int_branch, base], r)
        git.run(["worktree", "add", str(ctx.int_dir), ctx.int_branch], r)
        plant_deps(ctx, git, ctx.int_dir)
    else:
        if not ctx.int_dir.is_dir():
            git.run(["worktree", "add", str(ctx.int_dir), ctx.int_branch], r)
            plant_deps(ctx, git, ctx.int_dir)
        anc = git.run(["merge-base", "--is-ancestor", base, ctx.int_branch], r, check=False).returncode == 0
        if not anc:
            raise Refuse(f"HEAD ({base[:12]}) is not on the {ctx.int_branch} line — run `sync` first, "
                         f"or the user's branch diverged from integration")
        base = git.out(["rev-parse", "HEAD"], ctx.int_dir)
    data = {"wave": wave, "slug": ctx.slug, "base_sha": base,
            "integration_sha": git.out(["rev-parse", ctx.int_branch], r),
            "user_branch": user_branch, "created_at": now(), "leaves": {}}
    if ctx.base_path(wave).exists():
        old = json.loads(ctx.base_path(wave).read_text())
        if old.get("leaves"):
            raise Refuse(f"{ctx.base_path(wave).name} already has leaves recorded; a wave base is taken once")
    write_base(ctx, wave, data)
    print(f"wave {wave} base = {base[:12]} on {user_branch}; integration worktree at {ctx.int_dir.relative_to(r)}")
    return 0


def cmd_add(ctx: Ctx, git: Git, wave: int, leaves: list[str]) -> int:
    r = ctx.root
    data = read_base(ctx, wave)
    briefs = load_briefs(ctx)
    targets = leaves or [l for l, b in briefs.items() if ci._wave(b) == wave]
    if not targets:
        raise Refuse(f"no briefs with wave {wave} under {ctx.briefs_dir}")
    failures = []
    for leaf in targets:
        if leaf not in briefs:
            failures.append(f"{leaf}: no brief")
            continue
        wt = ctx.wt_dir(leaf)
        proc = git.run(["worktree", "add", "-b", ctx.leaf_branch(leaf), str(wt), data["base_sha"]], r, check=False)
        if proc.returncode != 0:  # exit 255 (branch exists) or 128 (path/ref) — both refusals
            failures.append(f"{leaf}: {proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else 'worktree add failed'}")
            continue
        planted = plant_deps(ctx, git, wt)
        data["leaves"][leaf] = {"branch": ctx.leaf_branch(leaf), "worktree": str(wt.relative_to(r)),
                                "commit": None, "created_at": now()}
        print(f"{leaf}: worktree {wt.relative_to(r)} on {ctx.leaf_branch(leaf)} @ {data['base_sha'][:12]}"
              + (f" (linked {', '.join(planted)})" if planted else ""))
    write_base(ctx, wave, data)
    if failures:
        raise Refuse("some leaves could not be added:\n  " + "\n  ".join(failures))
    return 0


def cmd_commit(ctx: Ctx, git: Git, leaf: str) -> int:
    brief, wave = leaf_wave(ctx, leaf)
    data = read_base(ctx, wave)
    wt = ctx.wt_dir(leaf)
    if not wt.is_dir():
        raise Refuse(f"no worktree at {wt} — was `add` run for {leaf}?")
    head = git.out(["rev-parse", "HEAD"], wt)
    problems: list[str] = []
    if head != data["base_sha"]:
        problems.append(f"HEAD moved ({head[:12]} != base {data['base_sha'][:12]}): the leaf ran git. "
                        f"Worktree kept for inspection.")
    ignore = effective_ignore(ctx.cfg)
    status = git.out(["status", "--porcelain", "--untracked-files=all"], wt)
    changed = [p for p in porcelain_paths(status) if not _ignored(p, ignore)]
    declared = declared_paths(brief)
    impl = ci._leaf_paths(brief, "impl")
    if not changed and not problems:
        raise Refuse(f"{leaf}: no changes in {wt.relative_to(ctx.root)} — the leaf reported green "
                     f"without producing its declared files")
    undeclared = sorted(set(changed) - set(declared))
    if undeclared:
        problems.append("undeclared writes (worktree kept for inspection):\n    " + "\n    ".join(undeclared[:30]))
    missing = [p for p in impl if not (wt / p).exists()]
    if missing:
        problems.append("declared impl_files missing from the worktree: " + ", ".join(missing))
    if problems:
        raise Refuse(f"{leaf}: refusing to commit\n  " + "\n  ".join(problems))
    to_add = [p for p in declared if p in changed]
    git.run(["add", "--", *to_add], wt)
    git.run(["commit", "-q", "-m", f"swarm({ctx.slug}): {leaf} — {brief_title(brief)}"], wt)
    sha = git.out(["rev-parse", "HEAD"], wt)
    data["leaves"].setdefault(leaf, {"branch": ctx.leaf_branch(leaf), "worktree": str(wt.relative_to(ctx.root))})
    data["leaves"][leaf]["commit"] = sha
    data["leaves"][leaf]["committed_at"] = now()
    write_base(ctx, wave, data)
    marker = ctx.cdir / "audits" / f"wave-{wave}" / f"{leaf}.COMMIT"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(sha + "\n")
    print(f"{leaf}: committed {len(to_add)} file(s) as {sha[:12]} on {ctx.leaf_branch(leaf)}")
    return 0


def _remove_worktree(ctx: Ctx, git: Git, leaf: str) -> None:
    wt = ctx.wt_dir(leaf)
    if wt.exists():
        # --force is required because worktree_link symlinks are untracked
        # (DRYRUN.md finding 7). Safe here: the leaf's commit already exists.
        git.run(["worktree", "remove", "--force", str(wt)], ctx.root)


def cmd_admit(ctx: Ctx, git: Git, leaf: str, confirm_same: bool) -> int:
    brief, wave = leaf_wave(ctx, leaf)
    data = read_base(ctx, wave)
    rec = data["leaves"].get(leaf) or {}
    if not rec.get("commit"):
        raise Refuse(f"{leaf}: no commit recorded — run `commit --leaf {leaf}` first (Phase 5.1)")
    gates_clear(ctx, wave, leaf)
    it = ctx.int_dir
    if not it.is_dir():
        raise Refuse(f"integration worktree missing at {it} — run `base` again")
    ignore = effective_ignore(ctx.cfg)
    dirty = [p for p in porcelain_paths(git.out(["status", "--porcelain", "--untracked-files=all"], it))
             if not _ignored(p, ignore)]
    if dirty:
        raise Refuse(f"integration worktree is dirty: {dirty[:10]} — refusing to merge into it")
    shard = ci._shard(brief)
    declared = declared_paths(brief)
    leaf_sha = rec["commit"]
    umbrella = ctx.cfg.get("umbrella_test_cmd") or ""
    pre_sha = git.out(["rev-parse", "HEAD"], it)

    already_merged = git.run(["merge-base", "--is-ancestor", leaf_sha, "HEAD"], it, check=False).returncode == 0
    if already_merged and not confirm_same:
        raise Refuse(f"{leaf}: commit {leaf_sha[:12]} is already in integration — "
                     f"use `--confirm-same` to finish a same-count admit, or `revert`")

    # actual changed-set overlap against every other leaf's commit in this wave (DRYRUN finding 6)
    mine = set(git.out(["diff", "--name-only", f"{data['base_sha']}..{leaf_sha}"], ctx.root).splitlines())
    for other, orec in data["leaves"].items():
        if other == leaf or not orec.get("commit"):
            continue
        theirs = set(git.out(["diff", "--name-only", f"{data['base_sha']}..{orec['commit']}"], ctx.root).splitlines())
        overlap = sorted(mine & theirs)
        if overlap:
            append_gate_row(ctx, wave, leaf, "G1/overlap breach", "FAIL", f"changed-set overlap with {other}: {overlap}")
            raise Refuse(f"{leaf}: changed files overlap {other}: {overlap} — file-disjoint invariant broken; not admitted")

    if not already_merged:
        pre_names, pre_count, count_only = named_passes(umbrella, it) if umbrella else (set(), 0, True)
        proc = git.run(["merge", "--no-ff", "--no-edit", ctx.leaf_branch(leaf)], it, check=False)
        if proc.returncode != 0:
            git.run(["merge", "--abort"], it, check=False)
            append_gate_row(ctx, wave, leaf, "G1/overlap breach", "FAIL", f"merge conflict: {proc.stdout.strip()[-300:]}")
            append_log(ctx, wave, shard, leaf, declared, "BLOCKED", "merge conflict — overlap breach", leaf_sha, "")
            raise Refuse(f"{leaf}: merge conflict — treated as overlap breach; integration reset to {pre_sha[:12]}")
        merge_sha = git.out(["rev-parse", "HEAD"], it)
        post_names, post_count, count_only2 = named_passes(umbrella, it) if umbrella else (set(), 0, True)
        count_only = count_only or count_only2
        acc = acceptance_cmd(brief)
        acc_ok, acc_tail = True, ""
        if acc:
            ap = subprocess.run(shlex.split(acc), cwd=it, capture_output=True, text=True)
            acc_ok = ap.returncode == 0
            acc_tail = (ap.stdout + ap.stderr)[-800:]
        regressed = sorted(pre_names - post_names) if not count_only else []
        delta = post_count - pre_count
        if regressed or (count_only and delta < 0) or not acc_ok:
            reason = (f"regression: {regressed}" if regressed else
                      f"umbrella count fell {pre_count}->{post_count}" if delta < 0 else "acceptance failed")
            _do_revert(ctx, git, leaf, wave, shard, declared, pre_sha, leaf_sha, reason, acc_tail)
            return 1
        if delta == 0 and not confirm_same:
            # 6.8 yellow flag: merge left in place; overlord asks the user
            data["leaves"][leaf]["merge_pending"] = merge_sha
            write_base(ctx, wave, data)
            print(f"{leaf}: umbrella count unchanged ({pre_count}) — merge {merge_sha[:12]} left in place.\n"
                  f"Ask the user; then `admit --leaf {leaf} --confirm-same` or `revert --leaf {leaf}`.")
            return 3
        delta_str = f"+{delta}" if delta >= 0 else str(delta)
    else:
        merge_sha = data["leaves"][leaf].get("merge_pending") or git.out(["rev-parse", "HEAD"], it)
        delta_str = "+0 (confirmed)"
    _remove_worktree(ctx, git, leaf)
    git.run(["branch", "-d", ctx.leaf_branch(leaf)], it)   # cwd INT: HEAD contains the merge (DRYRUN finding 5)
    git.run(["worktree", "prune"], ctx.root)
    data["leaves"][leaf].update({"merge": merge_sha, "admitted_at": now(), "status": "admitted"})
    data["leaves"][leaf].pop("merge_pending", None)
    write_base(ctx, wave, data)
    append_log(ctx, wave, shard, leaf, declared, delta_str, "clean", leaf_sha, merge_sha)
    print(f"{leaf}: ADMITTED merge {merge_sha[:12]} into {ctx.int_branch} (umbrella {delta_str})")
    return 0


def _do_revert(ctx: Ctx, git: Git, leaf: str, wave: int, shard: str, declared: list[str],
               pre_sha: str, leaf_sha: str, reason: str, tail: str) -> None:
    it = ctx.int_dir
    git.run(["reset", "--hard", pre_sha], it)
    _remove_worktree(ctx, git, leaf)
    git.run(["branch", "-m", ctx.leaf_branch(leaf), ctx.reverted_branch(leaf)], ctx.root)
    git.run(["worktree", "prune"], ctx.root)
    data = read_base(ctx, wave)
    data["leaves"][leaf].update({"status": "reverted", "reverted_at": now(), "reason": reason,
                                 "branch": ctx.reverted_branch(leaf)})
    data["leaves"][leaf].pop("merge_pending", None)
    write_base(ctx, wave, data)
    append_log(ctx, wave, shard, leaf, declared, "REVERTED", reason, leaf_sha, "")
    bp = ctx.briefs_dir / f"{leaf}.md"
    if bp.exists():
        with bp.open("a") as fh:
            fh.write(f"\n## Post-review regression\n\n{now()}: {reason}. Commit kept on "
                     f"`{ctx.reverted_branch(leaf)}`.\n\n```\n{tail}\n```\n")
    print(f"{leaf}: REVERTED — {reason}; integration back at {pre_sha[:12]}; "
          f"commit kept on {ctx.reverted_branch(leaf)}")


def cmd_revert(ctx: Ctx, git: Git, leaf: str) -> int:
    brief, wave = leaf_wave(ctx, leaf)
    data = read_base(ctx, wave)
    rec = data["leaves"].get(leaf) or {}
    pending = rec.get("merge_pending")
    if not pending:
        raise Refuse(f"{leaf}: no pending merge to revert (only a same-count admit leaves one)")
    pre_sha = git.out(["rev-parse", f"{pending}^1"], ctx.int_dir)
    _do_revert(ctx, git, leaf, wave, ci._shard(brief), declared_paths(brief), pre_sha, rec["commit"],
               "user declined same-count admit", "")
    return 1


def cmd_sync(ctx: Ctx, git: Git, yes: bool) -> int:
    r = ctx.root
    ahead = git.out(["log", "--oneline", f"HEAD..{ctx.int_branch}"], r)
    if not ahead:
        print("user branch already up to date with integration")
        return 0
    print(f"integration is ahead of the user's branch by:\n{ahead}")
    if not yes:
        raise NeedsYes()
    proc = git.run(["merge", "--ff-only", ctx.int_branch], r, check=False)
    if proc.returncode != 0:
        raise Refuse(f"fast-forward impossible — the user's branch has commits integration lacks.\n"
                     f"Do NOT rebase or merge on the user's behalf. Options for the user:\n"
                     f"  git merge {ctx.int_branch}          # merge commit on their branch\n"
                     f"  git rebase {ctx.int_branch}         # only if they want a linear history")
    print(f"fast-forwarded to {git.out(['rev-parse', '--short', 'HEAD'], r)}")
    return 0


def cmd_finish(ctx: Ctx, git: Git, yes: bool) -> int:
    rc = cmd_sync(ctx, git, yes)
    if rc != 0:
        return rc
    return cmd_cleanup(ctx, git, purge=False, yes=yes)


def _residual(ctx: Ctx, git: Git) -> list[tuple[str, str, str]]:
    r = ctx.root
    out: list[tuple[str, str, str]] = []
    for line in git.out(["worktree", "list", "--porcelain"], r).splitlines():
        if line.startswith("worktree ") and str(ctx.cdir / "worktrees") in line:
            path = line[9:]
            name = Path(path).name
            kind = "integration" if name == "integration" else "leaf-worktree"
            out.append((kind, name, path))
    for b in git.out(["branch", "--list", "--format=%(refname:short)", f"swarm/{ctx.slug}/**"], r).split():
        kind = ("integration" if b == ctx.int_branch else
                "reverted" if "/reverted/" in b else "leaf-branch")
        out.append((kind, b, ""))
    return out


def cmd_status(ctx: Ctx, git: Git) -> int:
    rows = _residual(ctx, git)
    print(f"Residual git state for `{ctx.slug}`:")
    if not rows:
        print("  (none)")
        return 0
    for kind, name, path in rows:
        print(f"  {kind:14} {name} {path}")
    return 0


def cmd_cleanup(ctx: Ctx, git: Git, purge: bool, yes: bool) -> int:
    r = ctx.root
    rows = _residual(ctx, git)
    plan: list[str] = []
    for kind, name, path in rows:
        if kind == "leaf-worktree":
            plan.append(f"remove worktree {path}" + ("" if purge else " (refused/uncommitted — needs --purge)"))
        elif kind == "leaf-branch":
            plan.append(f"delete branch {name}" + ("" if purge else " (needs --purge)"))
        elif kind == "reverted":
            plan.append(f"delete branch {name}" + ("" if purge else " (forensic — needs --purge)"))
    int_merged = git.run(["merge-base", "--is-ancestor", ctx.int_branch, "HEAD"], r, check=False).returncode == 0 \
        if any(k == "integration" for k, _, _ in rows) else False
    if any(k == "integration" for k, _, _ in rows):
        plan.append(f"remove integration worktree + branch {ctx.int_branch}"
                    + ("" if int_merged else " (NOT yet fast-forwarded into the user's branch — refusing)"))
    if not plan:
        git.run(["worktree", "prune"], r)
        print("nothing to clean")
        return 0
    print("cleanup plan:")
    for p in plan:
        print(f"  {p}")
    if not yes:
        raise NeedsYes()
    for kind, name, path in rows:
        if kind == "leaf-worktree" and purge:
            git.run(["worktree", "remove", "--force", path], r)
        elif kind in ("leaf-branch", "reverted") and purge:
            git.run(["branch", "-D", name], r)
    if any(k == "integration" for k, _, _ in rows) and int_merged:
        if ctx.int_dir.exists():
            git.run(["worktree", "remove", "--force", str(ctx.int_dir)], r)
        git.run(["branch", "-d", ctx.int_branch], r)
    git.run(["worktree", "prune"], r)
    print("cleanup done; residual:")
    return cmd_status(ctx, git)


# ---------- main ----------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", type=Path, default=Path.cwd(), help="any path inside the repo or a worktree")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--slug", required=True, help="cascade slug (.swarm/<slug>/)")

    s = sub.add_parser("preflight"); common(s)
    s = sub.add_parser("base"); common(s); s.add_argument("--wave", type=int, required=True)
    s.add_argument("--commit-artifacts", action="store_true"); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("add"); common(s); s.add_argument("--wave", type=int, required=True)
    s.add_argument("--leaf", action="append", default=[])
    s = sub.add_parser("commit"); common(s); s.add_argument("--leaf", required=True)
    s = sub.add_parser("admit"); common(s); s.add_argument("--leaf", required=True)
    s.add_argument("--confirm-same", action="store_true")
    s = sub.add_parser("revert"); common(s); s.add_argument("--leaf", required=True)
    s = sub.add_parser("sync"); common(s); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("finish"); common(s); s.add_argument("--yes", action="store_true")
    s = sub.add_parser("status"); common(s)
    s = sub.add_parser("cleanup"); common(s); s.add_argument("--purge", action="store_true")
    s.add_argument("--yes", action="store_true")
    args = p.parse_args(argv)

    root = main_root(args.root.resolve())
    cfg = ci.load_config(root)
    slug = ci.discover_cascade_slug(root, args.slug) or args.slug
    ctx = Ctx(root=root, slug=slug, cfg=cfg)
    git = Git(ctx.ops_log)
    try:
        if args.cmd == "preflight":
            return cmd_preflight(ctx, git)
        if args.cmd == "base":
            return cmd_base(ctx, git, args.wave, args.commit_artifacts, args.yes)
        if args.cmd == "add":
            return cmd_add(ctx, git, args.wave, args.leaf)
        if args.cmd == "commit":
            return cmd_commit(ctx, git, args.leaf)
        if args.cmd == "admit":
            return cmd_admit(ctx, git, args.leaf, args.confirm_same)
        if args.cmd == "revert":
            return cmd_revert(ctx, git, args.leaf)
        if args.cmd == "sync":
            return cmd_sync(ctx, git, args.yes)
        if args.cmd == "finish":
            return cmd_finish(ctx, git, args.yes)
        if args.cmd == "status":
            return cmd_status(ctx, git)
        if args.cmd == "cleanup":
            return cmd_cleanup(ctx, git, args.purge, args.yes)
    except Refuse as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    except NeedsYes:
        print("needs confirmation: re-run with --yes after the user approves", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
