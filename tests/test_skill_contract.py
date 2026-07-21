#!/usr/bin/env python3
"""Executable contract for the Manager Mode skill documents.

These assertions intentionally test the public, file-based workflow rather than
an LLM's prose quality. They prevent a future edit from silently dropping a
load-bearing gate while allowing the Phase 8 audit topology to evolve.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGULAR = (ROOT / "skills/manager-mode/SKILL.md").read_text()
HARDCORE = (ROOT / "skills/manager-mode-hardcore/SKILL.md").read_text()


def batches(leaves: list[str]) -> list[list[str]]:
    """The documented deterministic batch partition, exercised at boundaries."""
    return [leaves[i:i + 3] for i in range(0, len(leaves), 3)]


class ManagerModeContractTests(unittest.TestCase):
    def test_base_safety_contract_is_retained(self) -> None:
        required = (
            "Phase 0 — Preflight", "Phase 1 — Lite-discovery",
            "Phase 2 — Decompose", "Phase 3 — Audit briefs",
            "Phase 4 — Spawn leaves", "Phase 5 — Wait + aggregate sweep",
            "Phase 6 — Admission loop", "Phase 7 — Final report",
            "check_invariants.py", "≤ 12", "13–16", "> 16",
            "parent_owned", "Stage outputs", "G1", "G2", "G3", "G4",
            "G5", "G6", "G7", "bypass", "wave snapshot",
            "Assumption-sweep", "questions", "proposals", "umbrella",
            "admit-or-revert", "Apex", "No file overlap across shards",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_regular_phase_8_is_batched_evidence_audit(self) -> None:
        required = (
            "Batched evidence audit", "at most three", "ascending `leaf-NN`",
            "batch-01", "one fresh-context", "Dispatch all batches",
            "concrete test or probe command", "observed output",
            "source or\nlocked-spec citation", "Do not edit any file",
            "ESCALATION-ONLY", "POST-MORTEM.md", "confirmed repairs",
            "affected leaf tests first", "umbrella/full suite",
            "accepted/denied/unverified", "changed paths", "final suite status",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)
        self.assertNotIn("Runs once per wave, after Phase 7's report, against everything admitted", REGULAR)
        self.assertIn("writable footprint** — only its admitted leaves' `impl_files` + `test_files`", REGULAR)
        self.assertIn("read-only audit context", REGULAR)
        self.assertNotIn("`test_files`, plus the umbrella test", REGULAR)
        self.assertNotIn("or (if you can run one) an actual command/test output", REGULAR)

    def test_hardcore_keeps_admission_and_adds_two_plus_one_review(self) -> None:
        required = (
            "Phases 0–7 unchanged", "normal admission loop before any hardcore review batch",
            "two fresh-context auditors", "Neither auditor may see the other",
            "third fresh-context reviewer", "CONFIRMED", "DENIED", "UNVERIFIED",
            "ESCALATION-ONLY", "within the batch's declared implementation/test footprint",
            "affected leaf tests first", "umbrella/full suite", "REVIEW.md",
            "POST-MORTEM.md", "G1–G7", "bypass detection", "apex testing",
            "Shards remain file-disjoint", "wave` and `shard` columns",
            "AUDIT-FAILURE.md", "missing, malformed, or arrives after",
        )
        for token in required:
            self.assertIn(token, HARDCORE, token)

    def test_batch_boundaries_and_artifact_paths(self) -> None:
        self.assertEqual(batches(["leaf-01"]), [["leaf-01"]])
        self.assertEqual(batches(["leaf-01", "leaf-02", "leaf-03"]), [["leaf-01", "leaf-02", "leaf-03"]])
        self.assertEqual(batches(["leaf-01", "leaf-02", "leaf-03", "leaf-04"]), [["leaf-01", "leaf-02", "leaf-03"], ["leaf-04"]])
        leaves = [f"leaf-{i:02d}" for i in range(1, 9)]
        self.assertEqual([len(batch) for batch in batches(leaves)], [3, 3, 2])
        self.assertRegex(REGULAR, r"\.swarm/audits/wave-<wave>/<shard-or-default>/batch-<NN>/")
        self.assertRegex(HARDCORE, r"\.swarm/audits/wave-<wave>/<shard-or-default>/batch-<NN>/")

    def test_admission_identity_prevents_cross_wave_or_shard_batching(self) -> None:
        self.assertIn("| wave | shard | leaf_id |", REGULAR)
        self.assertIn("rows whose `wave` and `shard` columns match", REGULAR)
        self.assertIn("legacy row without wave/shard identity is not eligible", REGULAR)


if __name__ == "__main__":
    unittest.main()
