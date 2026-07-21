#!/usr/bin/env python3
"""Black-box regression cases for the Phase 3 invariant checker."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "skills/swarm-shared/scripts/check_invariants.py"
FIXTURES = ROOT / "tests/fixtures/invariants"


class InvariantFixtureTests(unittest.TestCase):
    def run_fixture(self, name: str, expected: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(FIXTURES / name, project)
            result = subprocess.run(
                ["python3", str(CHECKER), "--root", str(project)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(expected, result.stdout)

    def test_overlapping_files(self) -> None:
        self.run_fixture("overlap", "already owned")

    def test_parent_owned_violation(self) -> None:
        self.run_fixture("parent-owned", "matches parent-owned glob")

    def test_ambiguous_design_language(self) -> None:
        self.run_fixture("ambiguous-language", "ambiguous verb `Decide`")

    def test_invalid_contract_import(self) -> None:
        self.run_fixture("invalid-contract-import", "not in locked contract")

    def test_sizing_limit(self) -> None:
        self.run_fixture("sizing", "exceeds project max")

    def test_missing_or_malformed_spec_link(self) -> None:
        self.run_fixture("malformed-spec-link", "missing Spec Link Rule header")
        self.run_fixture("missing-spec-link", "declared test file `tests/missing.py` not found")


if __name__ == "__main__":
    unittest.main()
