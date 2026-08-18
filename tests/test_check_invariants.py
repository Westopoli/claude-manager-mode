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

    def test_shard_sizing_cap(self) -> None:
        self.run_fixture("shard-sizing", "exceeds max_leaves_per_shard=6")

    def test_shard_sizing_passes_at_the_cap(self) -> None:
        """Six leaves is the cap, not one past it."""
        def drop_seventh(project: Path) -> None:
            (project / ".swarm/briefs/leaf-07.md").unlink()
        result = self.mutate_fixture("shard-sizing", drop_seventh)
        self.assertNotIn("shard-sizing:", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shard_sizing_counts_each_shard_separately(self) -> None:
        """Splitting the same leaves across two shard dirs clears the cap."""
        def split(project: Path) -> None:
            briefs = project / ".swarm/briefs"
            for name, leaves in (("shard-A", ("01", "02", "03", "04")),
                                 ("shard-B", ("05", "06", "07"))):
                (briefs / name).mkdir()
                for leaf in leaves:
                    (briefs / f"leaf-{leaf}.md").rename(
                        briefs / name / f"leaf-{leaf}.md")
        result = self.mutate_fixture("shard-sizing", split)
        self.assertNotIn("shard-sizing:", result.stdout)

    def test_shard_is_not_inferred_from_an_ancestor_directory(self) -> None:
        """`_shard` once walked every parent, so a project checked out under
        any path with a `shard-*` component inherited a phantom shard on every
        brief — which pushes staging resolution at `pending/<shard>/leaf-NN/`,
        a directory that does not exist, ahead of the real one. Only the
        brief's own directory may name a shard."""
        def bury(project: Path) -> None:
            nested = project.parent / "shard-ancestor"
            nested.mkdir()
            project.rename(nested / project.name)
            project.symlink_to(nested / project.name)
        result = self.mutate_fixture("shard-sizing", bury)
        self.assertIn("wave-1/default:", result.stdout)
        self.assertNotIn("shard-ancestor", result.stdout)

    def test_missing_or_malformed_spec_link(self) -> None:
        self.run_fixture("malformed-spec-link", "missing Spec Link Rule header")
        self.run_fixture("missing-spec-link", "declared test file `tests/missing.py` not found")

    def mutate_fixture(self, name: str, edit) -> subprocess.CompletedProcess[str]:
        """Copy a fixture, let `edit(project_dir)` change it, then audit."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(FIXTURES / name, project)
            edit(project)
            return subprocess.run(
                ["python3", str(CHECKER), "--root", str(project)],
                text=True, capture_output=True, check=False,
            )

    def test_test_owned_by_is_required_not_defaulted(self) -> None:
        """An omitted `test_owned_by` used to parse silently as `leaf`.

        That is the wrong answer for every brief /manager-mode emits, and it is
        invisible: the audit passes, and the test paths quietly join the
        non-overlap and parent-owned checks under the wrong owner.
        """
        def drop_field(project: Path) -> None:
            brief = project / ".swarm/briefs/leaf-01.md"
            kept = [ln for ln in brief.read_text().splitlines(keepends=True)
                    if not ln.startswith("test_owned_by:")]
            brief.write_text("".join(kept))

        result = self.mutate_fixture("overlap", drop_field)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing required field `test_owned_by`", result.stdout)

    def test_test_owned_by_rejects_an_unknown_value(self) -> None:
        def bad_value(project: Path) -> None:
            brief = project / ".swarm/briefs/leaf-01.md"
            brief.write_text(brief.read_text().replace(
                "test_owned_by: parent", "test_owned_by: shared"))

        result = self.mutate_fixture("overlap", bad_value)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("test_owned_by `shared` is not one of", result.stdout)


class CascadeSlugResolutionTests(unittest.TestCase):
    """`.swarm/<slug>/` is the documented layout; flat `.swarm/` is the legacy
    one. The scripts previously hardcoded flat, so a per-cascade run found no
    briefs and reported the leaf as not-applicable instead of failing."""

    def audit(self, project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(CHECKER), "--root", str(project), *extra],
            text=True, capture_output=True, check=False,
        )

    def stage(self, tmp: str, slug: str | None) -> Path:
        project = Path(tmp) / "project"
        shutil.copytree(FIXTURES / "overlap", project)
        if slug is not None:
            # An explicit briefs_dir always wins over the derivation, so a
            # fixture that pins the flat path has to drop it to exercise this.
            cfg = project / ".claude-swarm.toml"
            cfg.write_text("".join(
                ln for ln in cfg.read_text().splitlines(keepends=True)
                if not ln.startswith("briefs_dir")))
            target = project / ".swarm" / slug
            target.mkdir(parents=True, exist_ok=True)
            (project / ".swarm/briefs").rename(target / "briefs")
        return project

    def test_per_cascade_layout_resolves_without_a_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.audit(self.stage(tmp, "my-cascade"))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("already owned", result.stdout)

    def test_flat_layout_still_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.audit(self.stage(tmp, None))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("already owned", result.stdout)

    def test_ambiguous_cascades_ask_instead_of_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.stage(tmp, "cascade-a")
            second = project / ".swarm/cascade-b/briefs"
            second.mkdir(parents=True)
            shutil.copy(project / ".swarm/cascade-a/briefs/leaf-01.md", second)

            result = self.audit(project)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("pass --cascade", result.stderr)

            # The flag must actually select, not merely unblock: cascade-a
            # holds the overlapping pair, cascade-b holds one brief alone.
            chose_a = self.audit(project, "--cascade", "cascade-a")
            self.assertEqual(chose_a.returncode, 1, chose_a.stdout + chose_a.stderr)
            self.assertIn("already owned", chose_a.stdout)

            chose_b = self.audit(project, "--cascade", "cascade-b")
            self.assertEqual(chose_b.returncode, 0, chose_b.stdout + chose_b.stderr)
            self.assertIn("1/1 briefs PASS", chose_b.stdout)


if __name__ == "__main__":
    unittest.main()
