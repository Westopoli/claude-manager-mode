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
        """G1-G10 plus the surrounding admission machinery.

        These match each gate's *definition* rather than its bare label —
        "G8" alone also appears in Phase 3.4's prose, so a bare-token check
        would still pass after the gate itself was deleted.
        """
        required = (
            "G7 wave-sweep check", "G1 parent-owned check",
            "**G2 ASSUMPTIONS file**", "**G3 open-question**",
            "**G4 contract-proposal**", "**G5 footprint integrity**",
            "**G6 escalation-trigger**", "**G8 test-quality gate**",
            "**G9 complexity gate**", "**G10 scale gate**",
            "check_invariants.py", "test_quality_gate.py", "complexity_gate.py",
            "parent_owned", "bypass", "wave base commit", "Assumption-sweep",
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
            ".swarm/<cascade-slug>/audits/wave-<wave>/<shard-or-default>/",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_plan_consistency_pass_gates_decomposition(self) -> None:
        """Phase 1.5 is a gate, not a suggestion.

        Its two failure modes are being skipped on the returning-project path
        (where Phase 1 never fires) and degrading to advisory. Both are pinned.
        """
        required = (
            "Phase 1.5 — Plan-consistency pass",
            "PLAN-CHECK.md",
            "external-unverified",
            "**Blocking.** Any open finding stops Phase 2",
            "**Always runs**",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_leaves_build_in_sandboxes_not_the_live_tree(self) -> None:
        """The isolation property, and the gate that enforces it.

        A leaf's test imports impl at its real path, so "confirm GREEN" and
        "write only to staging" cannot both hold. The sandbox is what resolves
        that; the Phase 4.0 baseline is what lets G5 detect a leaf that
        escaped it. Losing either silently restores the contradiction.
        """
        required = (
            "### 4.0 Wave base commit",
            "### 4.1 Create one worktree per leaf",
            ".swarm/<cascade-slug>/worktrees/leaf-NN/",
            "worktree_link",
            "### 5.1 Commit leaf worktrees",
            "swarm/<cascade-slug>/integration",
            "--no-ff",
            "worktree_ops.py",
            "NEVER run git",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)
        # The copy-per-leaf design must not creep back in.
        for token in ("sandbox/leaf-NN", "snapshot.json", "pending/leaf-NN", "backups/leaf-NN"):
            self.assertNotIn(token, REGULAR, token)

    def test_user_branch_is_written_only_with_consent(self) -> None:
        """Two confirmed writes, nothing else: the base commit and the final ff."""
        for token in ("--commit-artifacts --yes", "### 7.4 Finish", "git reset --soft HEAD~1",
                      "never rebase", "Residual git state"):
            self.assertIn(token, REGULAR, token)

    def test_gate_evidence_backs_the_bypass_check(self) -> None:
        """A log row records an admission; it is not proof a gate ran."""
        required = (
            "### 6.5a Gate evidence",
            "leaf-NN.GATES.md",
            "Identical timestamps",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)

    def test_phase_6_gates_run_from_a_script_not_a_checklist(self) -> None:
        """Prose gates have no failure mode.

        An overlord that ran all of them and one that ran none produced the
        same clean report — which is how 64 cascades accumulated 0 boundary
        sweeps and 13 empty post-review-logs. The runner, and its refusal to
        treat a missing input as silence, are both load-bearing.
        """
        required = (
            "run_gates.py",
            "missing input as a failure rather than a silence",
            "Do not hand-write this file",
        )
        for token in required:
            self.assertIn(token, REGULAR, token)
        # The runner verifies; it must never admit.
        self.assertIn("does **not** admit anything", REGULAR)

    def test_overlord_never_authors_test_content(self) -> None:
        """The authorship split, including its one sized exception.

        The overlord may apply a fix the auditor quoted verbatim; anything
        larger goes to a fresh test-fixer. An unbounded "mechanical fix"
        hatch is how a real cascade ended up authoring a whole new test.
        """
        required = ("test-fixer", "adds no new assertion")
        for token in required:
            self.assertIn(token, REGULAR, token)
        self.assertNotIn("play the role yourself inline", REGULAR)

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
            "Opus 5", "Sonnet 4.6", 'model: "opus"', 'model: "claude-sonnet-4-6"',
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
        self.assertIn(".swarm/<cascade-slug>/questions/", REGULAR)
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
