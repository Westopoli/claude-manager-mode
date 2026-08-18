#!/usr/bin/env python3
"""Behavioural tests for the Phase 6.5 gate runner.

Every case here is a rule that used to be prose. The survey that motivated the
runner found `BOUNDARIES.md` present in 0 of 64 cascades, the wave snapshot in
12, and 13 of 15 post-review-log files holding a header and no rows — so the
cases that matter most are the ones asserting a *missing artifact* is loud.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills/swarm-shared/scripts/run_gates.py"

CONFIG = """\
spec_dir = "specs/"
type_contract_path = "src/contract.py"
umbrella_test_cmd = "python3 -m pytest tests/"
parent_owned = ["src/contract.py", "tests/**"]
"""

BRIEF = """\
---
leaf_id: {leaf}
spec_file: specs/demo.md
spec_lines: 1-4
test_file: tests/test_demo.py
impl_file: src/{leaf_slug}.py
contract_imports:
  - build
do_not_edit:
  - src/contract.py
impl_line_budget: 50
test_assertion_budget: 5
test_owned_by: parent
---

## Task
Implement build per spec_lines 1-4.
"""


def build_cascade(root: Path, slug: str = "demo", leaves: tuple[str, ...] = ("leaf-01",)):
    """A minimal cascade that passes every gate, as the baseline to break."""
    (root / "specs").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / ".claude-swarm.toml").write_text(CONFIG)
    (root / "specs/demo.md").write_text("# demo\n## Acceptance criteria\n1. build works.\n")
    (root / "src/contract.py").write_text("def build():\n    raise NotImplementedError\n")
    (root / "tests/test_demo.py").write_text(
        "# spec: specs/demo.md::Acceptance criteria::AC-1\n"
        "def test_build():\n    assert True\n")

    cdir = root / ".swarm" / slug
    briefs = cdir / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)
    for leaf in leaves:
        slug_name = leaf.replace("-", "_")
        (briefs / f"{leaf}.md").write_text(
            BRIEF.format(leaf=leaf, leaf_slug=slug_name))

    # Phase 4.0 baseline: every file, before any leaf ran.
    hashes = {}
    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(root).as_posix()
        if rel.startswith(".swarm/"):
            continue
        hashes[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    (cdir / "wave-1.snapshot.json").write_text(json.dumps(
        {"wave": 1, "created_at": "2026-08-18T00:00:00Z",
         "leaf_owned_paths": [], "hashes": hashes}))

    audits = cdir / "audits/wave-1/default"
    audits.mkdir(parents=True, exist_ok=True)
    (audits / "TEST-AUDIT.md").write_text("# audit\nno findings\n")
    (audits / "BOUNDARIES.md").write_text("# boundaries\n| input | boundary |\n")

    for leaf in leaves:
        # Sandbox: baseline plus the leaf's own declared impl file.
        sandbox = cdir / "sandbox" / leaf
        sandbox.mkdir(parents=True, exist_ok=True)
        for rel in hashes:
            dest = sandbox / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((root / rel).read_bytes())
        slug_name = leaf.replace("-", "_")
        (sandbox / f"src/{slug_name}.py").write_text("def build():\n    return 1\n")

        staging = cdir / "pending" / leaf
        (staging / "src").mkdir(parents=True, exist_ok=True)
        (staging / "tests").mkdir(parents=True, exist_ok=True)
        (staging / f"src/{slug_name}.py").write_text("def build():\n    return 1\n")
        (staging / "tests/test_demo.py").write_text(
            (root / "tests/test_demo.py").read_text())

    # SWEEP must be newer than every ASSUMPTIONS (G7).
    time.sleep(0.01)
    (cdir / "wave-1.SWEEP.md").write_text("Assumption-sweep clean.\n")
    return cdir


def run(root: Path, leaf: str = "leaf-01", *extra: str):
    return subprocess.run(
        [sys.executable, str(RUNNER), "--leaf", leaf, "--root", str(root), *extra],
        text=True, capture_output=True,
    )


class GateRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        self.cdir = build_cascade(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def gates_file(self, leaf: str = "leaf-01") -> Path:
        return self.cdir / f"audits/wave-1/{leaf}.GATES.md"

    def test_clean_cascade_passes_and_writes_evidence(self) -> None:
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("clear to admit", r.stdout)
        self.assertTrue(self.gates_file().exists())
        self.assertIn("| G5 footprint | PASS", self.gates_file().read_text())

    def test_evidence_is_written_even_when_gates_fail(self) -> None:
        """The evidence file is the audit trail; a blocked leaf needs it most."""
        (self.cdir / "wave-1.snapshot.json").unlink()
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("A1 wave-baseline snapshot | FAIL", self.gates_file().read_text())

    def test_missing_snapshot_blocks(self) -> None:
        (self.cdir / "wave-1.snapshot.json").unlink()
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Phase 4.0 never ran", r.stdout)

    def test_missing_sweep_blocks(self) -> None:
        (self.cdir / "wave-1.SWEEP.md").unlink()
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Phase 5.2 never ran", r.stdout)

    def test_sweep_older_than_assumptions_blocks(self) -> None:
        """G7's real condition — a sweep that predates a leaf's own log never
        read that log."""
        assumptions = self.cdir / "briefs/leaf-01.ASSUMPTIONS.md"
        assumptions.write_text("## Assumptions\n- thing: value\n")
        sweep = self.cdir / "wave-1.SWEEP.md"
        old = time.time() - 600
        os.utime(sweep, (old, old))
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("is older than", r.stdout)

    def test_missing_test_audit_blocks(self) -> None:
        (self.cdir / "audits/wave-1/default/TEST-AUDIT.md").unlink()
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Phase 3.4 never ran", r.stdout)

    def test_missing_boundaries_is_advisory_by_default_and_blocks_under_strict(self) -> None:
        (self.cdir / "audits/wave-1/default/BOUNDARIES.md").unlink()
        self.assertEqual(run(self.root).returncode, 0)
        self.assertEqual(run(self.root, "leaf-01", "--strict").returncode, 1)

    def test_file_match_rejects_a_missing_declared_file(self) -> None:
        """The defect a real cascade shipped: staging held impl only."""
        (self.cdir / "pending/leaf-01/tests/test_demo.py").unlink()
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing ['tests/test_demo.py']", r.stdout)

    def test_file_match_rejects_an_extra_file(self) -> None:
        (self.cdir / "pending/leaf-01/src/sneaky.py").write_text("x = 1\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unexpected", r.stdout)

    def test_parent_owned_exempts_parent_authored_tests(self) -> None:
        """`parent_owned` includes `tests/**` and the brief is
        `test_owned_by: parent`. Checking the test path would fail every leaf
        in the default configuration."""
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("G1 parent-owned | PASS", self.gates_file().read_text())
        self.assertIn("exempt", self.gates_file().read_text())

    def test_parent_owned_still_catches_a_leaf_owned_violation(self) -> None:
        brief = self.cdir / "briefs/leaf-01.md"
        brief.write_text(brief.read_text().replace(
            "impl_file: src/leaf_01.py", "impl_file: src/contract.py"))
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("G1 parent-owned", r.stdout)
        self.assertIn("matches", r.stdout)

    def test_footprint_catches_an_undeclared_sandbox_write(self) -> None:
        """The write the old G5 structurally could not see: a leaf editing a
        parent-owned file inside its own sandbox."""
        (self.cdir / "sandbox/leaf-01/src/contract.py").write_text("def build():\n    return 0\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("sandbox:src/contract.py", r.stdout)

    def test_footprint_catches_a_live_tree_write_before_admission(self) -> None:
        (self.root / "src/contract.py").write_text("def build():\n    return 99\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("live:src/contract.py", r.stdout)

    def test_open_question_without_answer_or_tag_blocks(self) -> None:
        qdir = self.cdir / "questions"
        qdir.mkdir(parents=True, exist_ok=True)
        (qdir / "leaf-01-Q1.md").write_text(
            "---\nleaf_id: leaf-01\nquestion_id: Q1\nstatus: open\n---\n\n## Question\nWhich?\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("G3 open-question", r.stdout)

    def test_open_question_with_unanswered_tag_passes(self) -> None:
        qdir = self.cdir / "questions"
        qdir.mkdir(parents=True, exist_ok=True)
        (qdir / "leaf-01-Q1.md").write_text("---\nleaf_id: leaf-01\n---\n")
        (self.cdir / "briefs/leaf-01.ASSUMPTIONS.md").write_text(
            "- **thing**: v — source: best-guess, question leaf-01-Q1, unanswered: true\n")
        sweep = self.cdir / "wave-1.SWEEP.md"
        sweep.write_text(sweep.read_text())
        self.assertEqual(run(self.root).returncode, 0)

    def test_pending_proposal_blocks(self) -> None:
        pdir = self.cdir / "proposals"
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "leaf-01.md").write_text(
            "---\nleaf_id: leaf-01\ntarget_file: src/contract.py\nstatus: pending\n---\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("still `status: pending`", r.stdout)

    def test_nested_git_dirs_are_ignored(self) -> None:
        """A vendored checkout otherwise reports hundreds of undeclared
        differences, every one of them somebody else's git objects."""
        nested = self.root / "vendor/thing/.git"
        nested.mkdir(parents=True)
        (nested / "config").write_text("[core]\n")
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class BypassDetectionTests(unittest.TestCase):
    """6.0. A log row records an admission; it is not evidence a gate ran."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        self.cdir = build_cascade(self.root, leaves=("leaf-01", "leaf-02"))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_log(self, rows: str) -> None:
        (self.root / ".swarm/post-review-log.md").write_text(textwrap.dedent(f"""\
            # Post-Review Log — append-only, do not edit manually

            | wave | shard | leaf_id | files | delta | timestamp | status |
            |------|-------|---------|-------|-------|-----------|--------|
            {rows}"""))

    def test_prior_leaf_with_a_log_row_but_no_evidence_is_a_bypass(self) -> None:
        self.write_log("| 1 | default | leaf-01 | src/leaf_01.py | +1 | 2026-08-18T00:00:00Z | clean |\n")
        r = run(self.root, "leaf-02")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no GATES.md", r.stdout)

    def test_prior_leaf_with_evidence_but_no_log_row_is_a_bypass(self) -> None:
        self.write_log("")
        (self.cdir / "audits/wave-1/leaf-01.GATES.md").write_text("# evidence\n")
        r = run(self.root, "leaf-02")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no log row", r.stdout)

    def test_prior_leaf_with_both_passes(self) -> None:
        self.write_log("| 1 | default | leaf-01 | src/leaf_01.py | +1 | 2026-08-18T00:00:00Z | clean |\n")
        (self.cdir / "audits/wave-1/leaf-01.GATES.md").write_text("# evidence\n")
        r = run(self.root, "leaf-02")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
