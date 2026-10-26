#!/usr/bin/env python3
"""Behavioural tests for sabotage_run.py (Phase 3.5.2 runner)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_degenerate_sweep import BRIEF, CONFIG, git  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills/swarm-shared/scripts/sabotage_run.py"

TESTS = (
    "# spec: specs/demo.md::Acceptance criteria::AC-1\n"
    "import unittest\nfrom src.leaf_01 import build, other\n\n"
    "class T(unittest.TestCase):\n"
    "    def test_target(self):\n        self.assertEqual(build(2), 4)\n"
    "    def test_other(self):\n        self.assertEqual(other(1), 9)\n")

CORRECT = "def build(x):\n    return x * 2\n\ndef other(x):\n    raise NotImplementedError\n"
FLIPPED = "def build(x):\n    return x * 3\n\ndef other(x):\n    raise NotImplementedError\n"
BROKEN = "def build(x):\n    return x * 2\n\ndef other(x):\n    return 0\n"


class SabotageRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        for d in ("specs", "src", "tests", ".swarm/demo/briefs"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        (self.root / ".claude-swarm.toml").write_text(CONFIG)
        (self.root / "src/__init__.py").write_text("")
        (self.root / "tests/__init__.py").write_text("")
        (self.root / "tests/test_demo.py").write_text(TESTS)
        (self.root / ".swarm/demo/briefs/leaf-01.md").write_text(BRIEF.format(impl="src/leaf_01.py"))
        self.scratch = self.root / "scratch"
        (self.scratch / "tests").mkdir(parents=True)
        (self.scratch / "src").mkdir()
        (self.scratch / "src/__init__.py").write_text("")
        (self.scratch / "tests/__init__.py").write_text("")
        (self.scratch / "tests/test_demo.py").write_text(TESTS)
        self.fakes = self.root / "fakes"
        self.fakes.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_fake(self, src: str, lhs: str = "src/leaf_01.py") -> subprocess.CompletedProcess:
        f = self.fakes / "fake.py"
        f.write_text(src)
        return subprocess.run(
            [sys.executable, str(RUNNER), "--cascade", "demo", "--root", str(self.root), "--leaf", "leaf-01",
             "--scratch-dir", str(self.scratch), "--fake", f"{lhs}={f}", "--label", "correct", "--target", "doubling"],
            capture_output=True, text=True)

    def test_correct_fake_is_green_in_scope_and_out_of_scope_elsewhere(self) -> None:
        r = self.run_fake(CORRECT)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["states"]["tests.test_demo.T.test_target"], "PASS")
        self.assertEqual(data["states"]["tests.test_demo.T.test_other"], "OUT_OF_SCOPE")
        self.assertEqual(data["counts"], {"PASS": 1, "OUT_OF_SCOPE": 1, "FAIL": 0})
        self.assertNotIn("tests.test_demo.T.test_other", data["in_scope"])
        for key in ("leaf", "label", "target", "cmd", "returncode", "states", "counts",
                    "in_scope", "out_of_scope", "collected"):
            self.assertIn(key, data)

    def test_flipped_fake_reports_fail(self) -> None:
        data = json.loads(self.run_fake(FLIPPED).stdout)
        self.assertEqual(data["states"]["tests.test_demo.T.test_target"], "FAIL")

    def test_non_notimplemented_failure_is_fail_not_out_of_scope(self) -> None:
        data = json.loads(self.run_fake(BROKEN).stdout)
        self.assertEqual(data["states"]["tests.test_demo.T.test_other"], "FAIL")

    def test_refuses_fake_outside_impl_files(self) -> None:
        r = self.run_fake(CORRECT, lhs="src/contract.py")
        self.assertEqual(r.returncode, 2)
        self.assertIn("REFUSED", r.stderr)
        self.assertFalse((self.scratch / "src/contract.py").exists())


if __name__ == "__main__":
    unittest.main()
