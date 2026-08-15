#!/usr/bin/env python3
"""Executable contract for the Manager Mode skill documents.

These assertions intentionally test the public, file-based workflow rather than
an LLM's prose quality. They prevent a future edit from silently dropping a
load-bearing gate, while leaving the wording of any individual phase free to
evolve.

Negative assertions matter as much as positive ones here. Manager Mode
deliberately has *no* post-admission agent review — test quality is judged
before any leaf spawns (Phase 3.4), and the only downstream checks are
scripted gates. An edit that reintroduces a post-admission review pass would
change the skill's core claim, so the absence is pinned explicitly.
"""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGULAR = (ROOT / "skills/manager-mode/SKILL.md").read_text()
HARDCORE = (ROOT / "skills/manager-mode-hardcore/SKILL.md").read_text()


class ManagerModeContractTests(unittest.TestCase):
    def test_phase_skeleton_is_retained(self) -> None:
        required = (
            "Phase 0 — Preflight", "Phase 1 — Lite-discovery",
            "Phase 2 — Decompose", "Phase 3 — Audit briefs",
            "Phase 4 — Spawn leaves", "Phase 5 — Wait + aggregate sweep",
            "Phase 6 — Admission loop", "Phase 7 — Final report",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_admission_gates_are_retained(self) -> None:
        """G1-G9 plus the surrounding admission machinery.

        These match each gate's *definition* rather than its bare label —
        "G8" alone also appears in Phase 3.4's prose, so a bare-token check
        would still pass after the gate itself was deleted.
        """
        required = (
            "G7 wave-sweep check", "G1 parent-owned check",
            "**G2 ASSUMPTIONS file**", "**G3 open-question**",
            "**G4 contract-proposal**", "**G5 wave-snapshot integrity**",
            "**G6 escalation-trigger**", "**G8 test-quality gate**",
            "**G9 complexity gate**",
            "check_invariants.py", "test_quality_gate.py", "complexity_gate.py",
            "parent_owned", "bypass", "wave-snapshot", "Assumption-sweep",
            "admit-or-revert", "File-match rule", "Apex",
            "post-review-log.md", "| wave | shard | leaf_id |",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_leaf_cap_is_a_hard_refusal_at_16(self) -> None:
        self.assertIn("**> 16:** **refuse**", REGULAR)
        self.assertIn("non-negotiable", REGULAR)
        self.assertIn("No file overlap across shards", REGULAR)

    def test_no_agent_grades_its_own_tests(self) -> None:
        """The authorship separation is the skill's central structural claim.

        Leaves write impl only; a separate shard-test-writer authors the tests;
        a third fresh-context auditor judges them. Collapsing any two of those
        roles reintroduces the failure mode the cascade exists to prevent.
        """
        required = (
            "shard-test-writer", "test_owned_by: parent",
            "no agent ever grades its own tests",
            "Do not modify the test files",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_test_quality_audit_runs_before_any_leaf_spawns(self) -> None:
        required = (
            "TEST-AUDIT-BRIEF.md", "TEST-AUDIT.md",
            "before any leaf spawns", "fresh-context",
            "GOAL FIDELITY", "UMBRELLA ALIGNMENT", "TEST QUALITY",
            ".swarm/audits/wave-<wave>/<shard-or-default>/",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_no_post_admission_agent_review_exists(self) -> None:
        """Pinned as an absence — see module docstring."""
        forbidden = (
            "Phase 8", "Batched evidence audit", "POST-MORTEM.md",
            "batch-<NN>", "ESCALATION-ONLY", "adversarial audit",
        )
        for token in forbidden:
            self.assertNotIn(token, REGULAR, token)

    def test_model_tiers_are_pinned_per_role(self) -> None:
        """Leaves must not silently inherit the overlord's model."""
        required = (
            "Opus 5", "Sonnet 5", 'model: "opus"', 'model: "sonnet"',
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_scale_and_boundary_chain_is_wired_end_to_end(self) -> None:
        """Each link exists in the phase that owns it.

        The chain only works whole: a growth claim stated in the spec but
        never carried into a brief field, or a boundary sweep with nowhere
        to escalate to, degrades silently rather than failing loudly.
        """
        required = (
            "## Scale & Boundary Profile",          # 1.A — the source of truth
            "unbounded-unknown",                    # 1.A — the honest escape hatch
            "**Hot paths**",                        # 2.2 — decomposition axis
            "`growth_claim`, `scale_assertions`",   # 2.5 — brief frontmatter
            "test-design.md",                       # 2.6 — test-writer's rules
            "BOUNDARIES.md",                        # 2.6 — the swept artifact
            "BOUNDARY & SCALE FIDELITY",            # 3.4.2 — auditor check
            "**G10 scale gate**",                   # 6.5 — the gate
            "scale_gate.py",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_spec_silent_boundaries_escalate_rather_than_guess(self) -> None:
        self.assertIn(".swarm/questions/", REGULAR)
        self.assertIn("guessed boundary", REGULAR)

    def test_absolute_timings_belong_to_apex_not_to_leaves(self) -> None:
        """Leaves run under contention; only apex can hold a wall-clock budget."""
        self.assertIn("Apex owns absolute numbers", REGULAR)

    def test_spec_link_rule_shape(self) -> None:
        self.assertIn("# spec: <spec_path>::<section>::AC-<N>", REGULAR)
        self.assertIn("-- spec: <spec_path>::<section>::AC-<N>", REGULAR)


class HardcoreContractTests(unittest.TestCase):
    def test_hardcore_keeps_the_base_flow_intact(self) -> None:
        required = (
            "Phases 0–7 unchanged", "G1–G10", "bypass detection",
            "apex testing", "Shards remain file-disjoint",
            "`--strict`", "scale_gate.py",
        )
        for token in required:
            self.assertIn(token, HARDCORE, token)

    def test_hardcore_doubles_the_pre_impl_audit(self) -> None:
        required = (
            "two fresh-context auditors", "Neither auditor may see the other",
            "third fresh-context reviewer", "CONFIRMED", "DENIED", "UNVERIFIED",
            "test-auditor-1.md", "test-auditor-2.md",
            "TEST-AUDIT-ADJUDICATION.md", "PRE-IMPL-AUDIT-SUMMARY.md",
        )
        for token in required:
            self.assertIn(token, HARDCORE, token)

    def test_hardcore_fails_loudly_on_a_missing_auditor(self) -> None:
        self.assertIn("AUDIT-FAILURE.md", HARDCORE)
        self.assertIn("missing, malformed, or arrives after", HARDCORE)
        self.assertIn("do not spawn the adjudicator", HARDCORE)

    def test_hardcore_adds_no_post_admission_review_either(self) -> None:
        for token in ("Phase 8", "POST-MORTEM.md", "batch-<NN>"):
            self.assertNotIn(token, HARDCORE, token)


if __name__ == "__main__":
    unittest.main()
