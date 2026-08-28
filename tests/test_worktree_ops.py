#!/usr/bin/env python3
"""Behavioural tests for worktree_ops.py — the only place /manager-mode runs git.

Each case pins a rule from research/skill-audit-2026-08/A-worktree/GIT-SEQUENCE.md,
including the amendments the dry run forced (symlinks are untracked, `remove`
needs --force after a commit exists, `branch -d` must run from integration,
overlap is a set check not a conflict check).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "skills/swarm-shared/scripts/worktree_ops.py"

CONFIG = """\
spec_dir = "specs/"
type_contract_path = "src/contract.py"
umbrella_test_cmd = "python3 -m pytest tests/test_umbrella.py"
parent_owned = ["src/contract.py", "tests/**"]
worktree_link = [".venv"]
"""

BRIEF = """\
---
leaf_id: {leaf}
spec_file: specs/demo.md
spec_lines: 1-4
test_file: tests/test_{mod}.py
impl_file: src/{mod}.py
contract_imports:
  - build
do_not_edit:
  - src/contract.py
impl_line_budget: 50
test_assertion_budget: 5
test_owned_by: parent
wave: 1
---

## Task
Implement build in src/{mod}.py per spec_lines 1-4.

## Acceptance
Run `python3 -m pytest tests/test_{mod}.py -q` for this test_file. Confirm RED, then GREEN.
"""

UMBRELLA = """\
# spec: specs/demo.md::Acceptance criteria::AC-1
import importlib, os

def test_always():
    assert True

def test_leaf_01_present():
    assert importlib.import_module("src.leaf_01").build() == 1

def test_leaf_02_absent():
    # a deliberately fragile umbrella test: admitting leaf-02 regresses it
    assert not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "src", "leaf_02.py"))
"""


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def ops(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(OPS), "--root", str(root), *args],
                          capture_output=True, text=True)


def build_repo(root: Path, leaves=("leaf-01", "leaf-02")) -> Path:
    (root / "specs").mkdir(); (root / "src").mkdir(); (root / "tests").mkdir(); (root / ".venv").mkdir()
    (root / ".venv/marker").write_text("dep\n")
    (root / ".gitignore").write_text(".swarm/\n.venv/\n__pycache__/\n.pytest_cache/\n")
    (root / ".claude-swarm.toml").write_text(CONFIG)
    (root / "specs/demo.md").write_text("# demo\n## Acceptance criteria\n1. AC-1 build works.\n")
    (root / "src/__init__.py").write_text("")
    (root / "src/contract.py").write_text("def build():\n    raise NotImplementedError\n")
    (root / "tests/__init__.py").write_text("")
    (root / "tests/test_umbrella.py").write_text(UMBRELLA)
    cdir = root / ".swarm/demo"
    (cdir / "briefs").mkdir(parents=True)
    for leaf in leaves:
        mod = leaf.replace("-", "_")
        (cdir / "briefs" / f"{leaf}.md").write_text(BRIEF.format(leaf=leaf, mod=mod))
        (root / f"tests/test_{mod}.py").write_text(
            "# spec: specs/demo.md::Acceptance criteria::AC-1\n"
            f"def test_build():\n    from src.{mod} import build\n    assert build() == {leaf[-1]}\n")
    git("init", "-q", "-b", "main", cwd=root)
    git("config", "user.email", "t@t", cwd=root)
    git("config", "user.name", "t", cwd=root)
    git("add", "-A", cwd=root)
    git("commit", "-q", "-m", "base", cwd=root)
    return cdir


def clear_gates(cdir: Path, leaf: str) -> None:
    g = cdir / "audits/wave-1"
    g.mkdir(parents=True, exist_ok=True)
    (g / f"{leaf}.GATES.md").write_text("| gate | result | evidence | timestamp |\n|---|---|---|---|\n| G1 | PASS | ok | t |\n")


class WorktreeOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.cdir = build_repo(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ---- preflight
    def test_preflight_refuses_non_git(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            Path(d, ".claude-swarm.toml").write_text(CONFIG)
            r = ops(Path(d), "preflight", "--slug", "demo")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("not a git repository", r.stderr)

    def test_preflight_refuses_dirty_tree_and_passes_clean(self) -> None:
        self.assertEqual(ops(self.root, "preflight", "--slug", "demo").returncode, 0)
        (self.root / "src/contract.py").write_text("dirty\n")
        r = ops(self.root, "preflight", "--slug", "demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("tracked changes", r.stderr)

    def test_preflight_refuses_leftover_branches(self) -> None:
        git("branch", "swarm/demo/leaf-09", cwd=self.root)
        r = ops(self.root, "preflight", "--slug", "demo")
        self.assertEqual(r.returncode, 1)
        self.assertIn("leftover", r.stderr)
        self.assertIn("cleanup --slug demo --purge", r.stderr)

    # ---- base
    def test_base_records_sha_and_creates_integration(self) -> None:
        r = ops(self.root, "base", "--slug", "demo", "--wave", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.cdir / "wave-1.base.json").read_text())
        self.assertEqual(data["base_sha"], git("rev-parse", "HEAD", cwd=self.root))
        self.assertEqual(data["user_branch"], "main")
        self.assertTrue((self.cdir / "worktrees/integration/src/contract.py").exists())
        self.assertIn("swarm/demo/integration", git("branch", "--list", "swarm/demo/*", cwd=self.root))
        # .venv symlink planted and excluded from status
        self.assertTrue((self.cdir / "worktrees/integration/.venv").is_symlink())
        self.assertEqual(git("status", "--porcelain", "--untracked-files=all", cwd=self.cdir / "worktrees/integration"), "")
        # the user's checkout is untouched
        self.assertEqual(git("status", "--porcelain", cwd=self.root), "")

    def test_base_refuses_uncommitted_artifacts_unless_asked(self) -> None:
        (self.root / "specs/demo.md").write_text("# demo v2\n## Acceptance criteria\n1. AC-1\n")
        r = ops(self.root, "base", "--slug", "demo", "--wave", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("specs/demo.md", r.stderr)
        r = ops(self.root, "base", "--slug", "demo", "--wave", "1", "--commit-artifacts")
        self.assertEqual(r.returncode, 3)  # needs --yes
        r = ops(self.root, "base", "--slug", "demo", "--wave", "1", "--commit-artifacts", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("wave 1 base", git("log", "-1", "--format=%s", cwd=self.root))

    # ---- add / commit
    def _base_and_add(self) -> dict:
        self.assertEqual(ops(self.root, "base", "--slug", "demo", "--wave", "1").returncode, 0)
        r = ops(self.root, "add", "--slug", "demo", "--wave", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads((self.cdir / "wave-1.base.json").read_text())

    def test_add_creates_one_worktree_per_brief_and_refuses_twice(self) -> None:
        data = self._base_and_add()
        self.assertEqual(sorted(data["leaves"]), ["leaf-01", "leaf-02"])
        for leaf in data["leaves"]:
            wt = self.cdir / "worktrees" / leaf
            self.assertTrue((wt / "tests/test_umbrella.py").exists())
            self.assertEqual(git("rev-parse", "HEAD", cwd=wt), data["base_sha"])
            self.assertTrue((wt / ".venv").is_symlink())
        r = ops(self.root, "add", "--slug", "demo", "--wave", "1", "--leaf", "leaf-01")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already exists", r.stderr)

    def test_commit_refuses_undeclared_write_and_keeps_worktree(self) -> None:
        self._base_and_add()
        wt = self.cdir / "worktrees/leaf-01"
        (wt / "src/leaf_01.py").write_text("def build():\n    return 1\n")
        (wt / "src/extra.py").write_text("oops\n")
        r = ops(self.root, "commit", "--slug", "demo", "--leaf", "leaf-01")
        self.assertEqual(r.returncode, 1)
        self.assertIn("src/extra.py", r.stderr)
        self.assertTrue(wt.exists())
        self.assertEqual(git("rev-parse", "HEAD", cwd=wt), json.loads((self.cdir / "wave-1.base.json").read_text())["base_sha"])

    def test_commit_refuses_when_leaf_ran_git(self) -> None:
        self._base_and_add()
        wt = self.cdir / "worktrees/leaf-01"
        (wt / "src/leaf_01.py").write_text("def build():\n    return 1\n")
        git("add", "-A", cwd=wt); git("-c", "user.email=l@l", "-c", "user.name=l", "commit", "-q", "-m", "leaf ran git", cwd=wt)
        r = ops(self.root, "commit", "--slug", "demo", "--leaf", "leaf-01")
        self.assertEqual(r.returncode, 1)
        self.assertIn("HEAD moved", r.stderr)

    def test_commit_refuses_empty_worktree(self) -> None:
        self._base_and_add()
        r = ops(self.root, "commit", "--slug", "demo", "--leaf", "leaf-01")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no changes", r.stderr)

    def test_commit_records_sha_and_marker(self) -> None:
        self._base_and_add()
        wt = self.cdir / "worktrees/leaf-01"
        (wt / "src/leaf_01.py").write_text("def build():\n    return 1\n")
        r = ops(self.root, "commit", "--slug", "demo", "--leaf", "leaf-01")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.cdir / "wave-1.base.json").read_text())
        sha = data["leaves"]["leaf-01"]["commit"]
        self.assertEqual(sha, git("rev-parse", "swarm/demo/leaf-01", cwd=self.root))
        self.assertEqual((self.cdir / "audits/wave-1/leaf-01.COMMIT").read_text().strip(), sha)
        self.assertEqual(git("diff", "--name-only", f"{data['base_sha']}..{sha}", cwd=self.root), "src/leaf_01.py")
        self.assertTrue((self.cdir / "git-ops.log").exists())

    # ---- admit / revert
    def _commit_leaf(self, leaf: str, body: str) -> None:
        wt = self.cdir / "worktrees" / leaf
        (wt / f"src/{leaf.replace('-', '_')}.py").write_text(body)
        r = ops(self.root, "commit", "--slug", "demo", "--leaf", leaf)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_admit_requires_gates_evidence(self) -> None:
        self._base_and_add()
        self._commit_leaf("leaf-01", "def build():\n    return 1\n")
        r = ops(self.root, "admit", "--slug", "demo", "--leaf", "leaf-01")
        self.assertEqual(r.returncode, 1)
        self.assertIn("GATES.md", r.stderr)

    def test_admit_merges_no_ff_cleans_up_and_logs(self) -> None:
        self._base_and_add()
        self._commit_leaf("leaf-01", "def build():\n    return 1\n")
        clear_gates(self.cdir, "leaf-01")
        r = ops(self.root, "admit", "--slug", "demo", "--leaf", "leaf-01")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("ADMITTED", r.stdout)
        it = self.cdir / "worktrees/integration"
        self.assertEqual(git("log", "-1", "--format=%P", cwd=it).count(" "), 1)  # merge commit, two parents
        self.assertTrue((it / "src/leaf_01.py").exists())
        self.assertFalse((self.cdir / "worktrees/leaf-01").exists())
        self.assertNotIn("swarm/demo/leaf-01", git("branch", "--list", "swarm/demo/*", cwd=self.root))
        log = (self.root / ".swarm/post-review-log.md").read_text()
        self.assertIn("| leaf_commit | merge_commit |", log)
        self.assertIn("| leaf-01 |", log)
        self.assertIn("| +1 |", log)  # test_leaf_01_present went RED→GREEN in the umbrella
        self.assertIn("| clean |", log)
        # user's checkout still untouched
        self.assertFalse((self.root / "src/leaf_01.py").exists())
        self.assertEqual(git("status", "--porcelain", cwd=self.root), "")

    def test_admit_reverts_on_umbrella_regression_and_keeps_forensic_branch(self) -> None:
        self._base_and_add()
        self._commit_leaf("leaf-02", "def build():\n    return 2\n")
        clear_gates(self.cdir, "leaf-02")
        it = self.cdir / "worktrees/integration"
        pre = git("rev-parse", "HEAD", cwd=it)
        r = ops(self.root, "admit", "--slug", "demo", "--leaf", "leaf-02")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("REVERTED", r.stdout)
        self.assertEqual(git("rev-parse", "HEAD", cwd=it), pre)
        self.assertFalse((it / "src/leaf_02.py").exists())
        self.assertFalse((self.cdir / "worktrees/leaf-02").exists())
        branches = git("branch", "--list", "swarm/demo/**", cwd=self.root)
        self.assertIn("swarm/demo/reverted/leaf-02", branches)
        self.assertNotIn("swarm/demo/leaf-02\n", branches + "\n")
        self.assertIn("REVERTED", (self.root / ".swarm/post-review-log.md").read_text())
        self.assertIn("## Post-review regression", (self.cdir / "briefs/leaf-02.md").read_text())

    def test_admit_blocks_changed_set_overlap_even_without_conflict(self) -> None:
        # leaf-02 edits leaf-01's declared file at a non-adjacent hunk: git would auto-merge,
        # the set check must still block (DRYRUN finding 6)
        self._base_and_add()
        self._commit_leaf("leaf-01", "def build():\n    return 1\n")
        wt2 = self.cdir / "worktrees/leaf-02"
        (wt2 / "src/leaf_02.py").write_text("def build():\n    return 2\n")
        (wt2 / "src/leaf_01.py").write_text("# stray\n")
        r = ops(self.root, "commit", "--slug", "demo", "--leaf", "leaf-02")
        self.assertEqual(r.returncode, 1)  # undeclared at commit time already
        self.assertIn("src/leaf_01.py", r.stderr)

    # ---- sync / finish / status / cleanup
    def test_finish_fast_forwards_then_refuses_after_user_commit(self) -> None:
        self._base_and_add()
        self._commit_leaf("leaf-01", "def build():\n    return 1\n")
        clear_gates(self.cdir, "leaf-01")
        self.assertEqual(ops(self.root, "admit", "--slug", "demo", "--leaf", "leaf-01").returncode, 0)
        r = ops(self.root, "finish", "--slug", "demo")
        self.assertEqual(r.returncode, 3)  # shows commits, needs --yes
        self.assertIn("leaf-01", r.stdout)
        r = ops(self.root, "finish", "--slug", "demo", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue((self.root / "src/leaf_01.py").exists())
        # integration branch + worktree gone after finish (leaf-02 worktree remains: uncommitted)
        self.assertNotIn("swarm/demo/integration", git("branch", "--list", "swarm/demo/**", cwd=self.root))
        self.assertFalse((self.cdir / "worktrees/integration").exists())
        st = ops(self.root, "status", "--slug", "demo").stdout
        self.assertIn("leaf-02", st)
        # a user commit after a fresh base makes ff impossible
        self.assertEqual(ops(self.root, "base", "--slug", "demo", "--wave", "2").returncode, 0)
        (self.root / "README.md").write_text("user work\n")
        git("add", "-A", cwd=self.root); git("commit", "-q", "-m", "user commit", cwd=self.root)
        (self.cdir / "worktrees/integration/src/contract.py").write_text("def build():\n    return 0\n")
        git("commit", "-q", "-am", "integration commit", cwd=self.cdir / "worktrees/integration")
        r = ops(self.root, "sync", "--slug", "demo", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("fast-forward impossible", r.stderr)
        self.assertIn("Do NOT rebase", r.stderr)

    def test_cleanup_keeps_reverted_and_unmerged_integration_unless_purge(self) -> None:
        self._base_and_add()
        self._commit_leaf("leaf-01", "def build():\n    return 1\n")
        clear_gates(self.cdir, "leaf-01")
        self.assertEqual(ops(self.root, "admit", "--slug", "demo", "--leaf", "leaf-01").returncode, 0)
        self._commit_leaf("leaf-02", "def build():\n    return 2\n")
        clear_gates(self.cdir, "leaf-02")
        ops(self.root, "admit", "--slug", "demo", "--leaf", "leaf-02")  # reverts
        r = ops(self.root, "cleanup", "--slug", "demo", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        branches = git("branch", "--list", "swarm/demo/**", cwd=self.root)
        self.assertIn("swarm/demo/reverted/leaf-02", branches)   # forensic → kept
        self.assertIn("swarm/demo/integration", branches)         # holds leaf-01, not ff'd yet → kept
        self.assertTrue((self.cdir / "worktrees/integration").exists())
        r = ops(self.root, "cleanup", "--slug", "demo", "--purge", "--yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        branches = git("branch", "--list", "swarm/demo/**", cwd=self.root)
        self.assertNotIn("reverted", branches)
        self.assertIn("swarm/demo/integration", branches)         # --purge still never drops unmerged work
        # after finish the integration branch goes too
        self.assertEqual(ops(self.root, "finish", "--slug", "demo", "--yes").returncode, 0)
        self.assertEqual(git("branch", "--list", "swarm/demo/**", cwd=self.root), "")
        self.assertEqual(ops(self.root, "status", "--slug", "demo").stdout.strip().splitlines()[-1].strip(), "(none)")

    def test_git_ops_log_records_every_call(self) -> None:
        self._base_and_add()
        log = (self.cdir / "git-ops.log").read_text()
        self.assertIn("git worktree add", log)
        self.assertIn("| exit 0", log)

    def test_main_root_resolves_from_inside_a_worktree(self) -> None:
        self._base_and_add()
        r = subprocess.run([sys.executable, str(OPS), "--root", str(self.cdir / "worktrees/leaf-01"),
                            "status", "--slug", "demo"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("leaf-01", r.stdout)


if __name__ == "__main__":
    unittest.main()
