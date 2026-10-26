#!/usr/bin/env python3
"""Behavioural tests for degenerate_sweep.py (Phase 3.5.1)."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "skills/swarm-shared/scripts/degenerate_sweep.py"
sys.path.insert(0, str(ROOT / "skills/swarm-shared/scripts"))
import degenerate_sweep as ds  # noqa: E402

CONFIG = """\
spec_dir = "specs/"
type_contract_path = "src/contract.py"
parent_owned = ["src/contract.py", "tests/**"]
worktree_link = []
"""

BRIEF = """\
---
leaf_id: leaf-01
spec_file: specs/demo.md
spec_lines: 1-4
test_file: tests/test_demo.py
impl_file: {impl}
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
Implement build per spec_lines 1-4.

## Acceptance
Run `python3 -m unittest -v tests.test_demo` to confirm.
"""

HONEST = (
    "# spec: specs/demo.md::Acceptance criteria::AC-1\n"
    "import unittest\nfrom src.leaf_01 import build\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_doubles(self):\n        self.assertEqual(build(2), 4)\n")

VACUOUS = HONEST + "    def test_vacuous(self):\n        self.assertTrue(True)\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          check=True).stdout.strip()


def build_repo(root: Path, impl: str = "src/leaf_01.py", test_src: str | None = None,
               commit_tests: bool = True) -> None:
    for d in ("specs", "src", "tests", ".swarm/demo/briefs"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(".swarm/\n__pycache__/\n")
    (root / ".claude-swarm.toml").write_text(CONFIG)
    (root / "specs/demo.md").write_text("# demo\n## Acceptance criteria\n1. build doubles.\n")
    (root / "src/__init__.py").write_text("")
    (root / "tests/__init__.py").write_text("")
    (root / "src/contract.py").write_text("def build(x):\n    raise NotImplementedError\n")
    (root / ".swarm/demo/briefs/leaf-01.md").write_text(BRIEF.format(impl=impl))
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    if test_src is not None:
        (root / "tests/test_demo.py").write_text(test_src)
        if commit_tests:
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "tests")


def sweep(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SWEEP), "--cascade", "demo", "--root", str(root), *extra],
                          capture_output=True, text=True)


class SweepTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_vacuous_test_is_a_finding(self) -> None:
        build_repo(self.root, test_src=VACUOUS)
        r = sweep(self.root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("test_vacuous", r.stdout)
        self.assertNotIn("🔴 `tests.test_demo.T.test_doubles`", r.stdout)
        out = self.root / ".swarm/demo/audits/wave-1/default"
        self.assertTrue((out / "DEGENERATE-SWEEP.md").is_file())
        self.assertTrue(json.loads((out / "DEGENERATE-SWEEP.json").read_text()))

    def test_honest_test_is_clean(self) -> None:
        build_repo(self.root, test_src=HONEST)
        r = sweep(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("clean", r.stdout)

    def test_uncommitted_test_reaches_scratch(self) -> None:
        build_repo(self.root, test_src=VACUOUS, commit_tests=False)
        r = sweep(self.root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("test_vacuous", r.stdout)

    def test_non_python_impl_is_advisory(self) -> None:
        build_repo(self.root, impl="src/leaf_01.js", test_src=HONEST)
        r = sweep(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("unsupported language, skipped", r.stdout)

    def test_leaves_no_worktree_and_root_status_unchanged(self) -> None:
        build_repo(self.root, test_src=HONEST, commit_tests=False)
        before = git(self.root, "status", "--porcelain")
        sweep(self.root)
        self.assertEqual(git(self.root, "status", "--porcelain"), before)
        self.assertNotIn("sabotage-", git(self.root, "worktree", "list"))
        self.assertFalse((self.root / ".swarm/demo/worktrees/sabotage-default").exists())

    def test_keep_leaves_scratch_in_place(self) -> None:
        build_repo(self.root, test_src=HONEST)
        sweep(self.root, "--keep")
        self.assertTrue((self.root / ".swarm/demo/worktrees/sabotage-default").is_dir())

    def test_no_matching_briefs_is_config_error(self) -> None:
        build_repo(self.root, test_src=HONEST)
        self.assertEqual(sweep(self.root, "--leaf", "leaf-99").returncode, 2)

    def test_stub_generator_covers_classes_callables_and_module_getattr(self) -> None:
        for variant, expect in (("none", None), ("const", 0), ("identity", 7), ("true", True)):
            ns: dict = {}
            exec(ds.stub_source({"Thing": "class", "run": "callable"}, variant), ns)
            self.assertEqual(ns["run"](7), expect)
            self.assertEqual(ns["Thing"](1).whatever(7), expect)
            self.assertEqual(ns["__getattr__"]("other")(7), expect)
            with self.assertRaises(AttributeError):
                ns["__getattr__"]("__path__")

    @unittest.skipUnless(importlib.util.find_spec("pytest"), "pytest not installed")
    def test_pytest_runner_collects(self) -> None:
        pt = ("# spec: specs/demo.md::Acceptance criteria::AC-1\n"
              "from src.leaf_01 import build\n\n"
              "def test_vacuous():\n    assert True\n")
        build_repo(self.root, test_src=pt)
        r = sweep(self.root, "--test-cmd", "python3 -m pytest tests/test_demo.py")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
