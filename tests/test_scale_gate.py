#!/usr/bin/env python3
"""Regression cases for the Phase 6 scale gate (G10).

Two layers, matching how G8 and G9 were actually validated:

  * fixture tests exercise the CLI end-to-end, the same copytree pattern
    test_check_invariants.py uses;
  * unit tests pin the antipattern detector's precision directly, because
    every false positive this gate produced during development came from a
    shape that looks identical in the AST to a legitimate one (`dict.get`
    vs an HTTP `get`, a numeric accumulator vs a string one, a loop over a
    literal field list vs a loop over input). Those distinctions are the
    gate's whole value and are invisible from the CLI surface.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/swarm-shared/scripts"
GATE = SCRIPTS / "scale_gate.py"
FIXTURES = ROOT / "tests/fixtures/scale"

sys.path.insert(0, str(SCRIPTS))
import scale_gate as sg  # noqa: E402


def _kinds(src: str) -> list[str]:
    """Run the antipattern detector over a source string."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "m.py").write_text(src)
        return [f.kind for f in sg.check_antipatterns(d, ["m.py"])]


class ScaleGateFixtureTests(unittest.TestCase):
    def run_fixture(self, name: str, *, strict: bool) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(FIXTURES / name, project)
            argv = ["python3", str(GATE), "--leaf", "leaf-01", "--root", str(project)]
            if strict:
                argv.append("--strict")
            return subprocess.run(argv, text=True, capture_output=True, check=False)

    def test_quadratic_impl_is_flagged(self) -> None:
        r = self.run_fixture("quadratic", strict=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("membership-in-loop", r.stdout)

    def test_advisory_by_default_does_not_block(self) -> None:
        """Same fixture, no --strict: reported, but exit 0.

        This is the G8/G9 convention — a flagged shape is evidence, not
        proof, so base manager-mode surfaces it and hardcore blocks on it.
        """
        r = self.run_fixture("quadratic", strict=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ADVISORY", r.stdout)
        self.assertIn("membership-in-loop", r.stdout)

    def test_clean_leaf_passes(self) -> None:
        r = self.run_fixture("clean", strict=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_declared_scale_assertion_must_actually_compare_two_sizes(self) -> None:
        r = self.run_fixture("missing-scale-assertion", strict=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("missing-scale-assertion", r.stdout)


class AntipatternDetectionTests(unittest.TestCase):
    def test_detects_each_antipattern(self) -> None:
        cases = {
            "membership-in-loop": "def f(xs, seen):\n for x in xs:\n  if x in seen: pass\n",
            "nested-loop": "def f(xs):\n for a in xs:\n  for b in xs: pass\n",
            "concat-in-loop": 'def f(xs):\n s = ""\n for x in xs:\n  s += x\n return s\n',
            "sort-in-loop": "def f(xs):\n for x in xs:\n  y = sorted(xs)\n",
            "io-in-loop": "def f(xs, cursor):\n for x in xs:\n  cursor.execute(x)\n",
        }
        for kind, src in cases.items():
            self.assertIn(kind, _kinds(src), kind)

    def test_not_in_is_detected_as_well_as_in(self) -> None:
        """`not in` is ast.NotIn, a separate node — an early version missed it."""
        src = "def f(xs, seen):\n for x in xs:\n  if x not in seen: pass\n"
        self.assertIn("membership-in-loop", _kinds(src))

    def test_numeric_accumulator_is_not_a_string_concat(self) -> None:
        src = "def f(xs):\n total = 0\n for x in xs:\n  total += x\n return total\n"
        self.assertEqual(_kinds(src), [])

    def test_dict_get_is_not_network_io(self) -> None:
        """`d.get(k)` shares a method name with HTTP but is O(1) local work."""
        src = "def f(xs, d):\n for x in xs:\n  y = d.get(x)\n"
        self.assertEqual(_kinds(src), [])

    def test_client_receiver_still_flags_get(self) -> None:
        src = "def f(xs, session):\n for x in xs:\n  session.get(x)\n"
        self.assertIn("io-in-loop", _kinds(src))

    def test_membership_against_a_set_local_is_not_flagged(self) -> None:
        src = 'def f(xs):\n seen = {"a"}\n for x in xs:\n  if x in seen: pass\n'
        self.assertEqual(_kinds(src), [])

    def test_membership_against_a_module_level_dict_is_not_flagged(self) -> None:
        """A lookup table defined at import time is the normal shape."""
        src = 'CATALOG = {"a": 1}\n\n\ndef f(xs):\n for x in xs:\n  if x not in CATALOG: pass\n'
        self.assertEqual(_kinds(src), [])

    def test_get_with_a_set_default_types_the_result(self) -> None:
        src = ('def f(xs, order):\n approvals = order.get("a", set())\n'
               " for x in xs:\n  if x not in approvals: pass\n")
        self.assertEqual(_kinds(src), [])

    def test_constant_bounded_loop_is_not_a_scaling_risk(self) -> None:
        """Work repeated a fixed number of times cannot grow with input."""
        src = 'def f(order):\n for field in ("items", "region"):\n  if field not in order: pass\n'
        self.assertEqual(_kinds(src), [])

    def test_bounded_loop_inside_an_unbounded_one_still_flags(self) -> None:
        src = ('def f(xs, lst):\n for x in xs:\n  for i in range(3):\n'
               "   if i in lst: pass\n")
        self.assertIn("membership-in-loop", _kinds(src))

    def test_work_in_the_loop_header_is_not_per_iteration(self) -> None:
        """`for p in sorted(a) + sorted(b):` sorts once, before iterating."""
        src = "def f(a, b):\n for p in sorted(a) + sorted(b):\n  pass\n"
        self.assertEqual(_kinds(src), [])

    def test_sorting_in_the_body_still_flags(self) -> None:
        src = "def f(a, xs):\n for p in xs:\n  q = sorted(a)\n"
        self.assertIn("sort-in-loop", _kinds(src))

    def test_distinct_collections_are_not_a_self_join(self) -> None:
        src = "def f(xs, ys):\n for a in xs:\n  for b in ys: pass\n"
        self.assertEqual(_kinds(src), [])

    def test_range_loops_are_keyed_by_their_bounds(self) -> None:
        same = "def f(n):\n for i in range(n):\n  for j in range(n): pass\n"
        diff = "def f(n):\n for i in range(3):\n  for j in range(n): pass\n"
        self.assertIn("nested-loop", _kinds(same))
        self.assertEqual(_kinds(diff), [])


class RatioAssertionTests(unittest.TestCase):
    def _has_ratio(self, src: str) -> bool:
        v = sg._RatioVisitor()
        v.visit(ast.parse(src))
        return v.found

    def test_ratio_comparison_is_recognised(self) -> None:
        self.assertTrue(self._has_ratio("assert _ops(4000) / _ops(2000) < 3.0"))

    def test_single_size_assertion_is_not(self) -> None:
        self.assertFalse(self._has_ratio("assert _ops(4000) < 5000"))


class BandArithmeticTests(unittest.TestCase):
    """Pins the bands from test-design.md as code.

    The thresholds are only defensible because of where the complexity
    classes actually land under doubling; asserting that here means a
    future edit to the reference table cannot silently drift away from
    numbers that still separate the classes it claims to separate.
    """

    # ratio of cost(2N)/cost(N) at N = 1000
    CLASSES = {
        "O(1)": 1.00,
        "O(log n)": 1.10,
        "O(n)": 2.00,
        "O(n log n)": 2.20,
        "O(n^2)": 4.00,
        "O(n^3)": 8.00,
    }
    BANDS = {"sublinear": 1.5, "linear-ish": 3.0, "quadratic-ok": 6.0}

    def test_sublinear_band(self) -> None:
        for name in ("O(1)", "O(log n)"):
            self.assertLess(self.CLASSES[name], self.BANDS["sublinear"], name)
        self.assertGreater(self.CLASSES["O(n)"], self.BANDS["sublinear"])

    def test_linear_ish_band_admits_both_n_and_n_log_n(self) -> None:
        for name in ("O(n)", "O(n log n)"):
            self.assertLess(self.CLASSES[name], self.BANDS["linear-ish"], name)
        self.assertGreater(self.CLASSES["O(n^2)"], self.BANDS["linear-ish"])

    def test_quadratic_ok_band(self) -> None:
        self.assertLess(self.CLASSES["O(n^2)"], self.BANDS["quadratic-ok"])
        self.assertGreater(self.CLASSES["O(n^3)"], self.BANDS["quadratic-ok"])

    def test_n_and_n_log_n_are_not_separable(self) -> None:
        """The reason linear-ish merges them, asserted rather than asserted-in-prose."""
        gap = self.CLASSES["O(n log n)"] / self.CLASSES["O(n)"] - 1
        self.assertLess(gap, 0.15)


if __name__ == "__main__":
    unittest.main()
