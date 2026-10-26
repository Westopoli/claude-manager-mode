#!/usr/bin/env python3
"""Phase 3.5.2 runner — run one leaf's tests against a saboteur's partial fake.

The saboteur (a fresh agent) writes a fake impl for ONE target (a boundary
value, a rule, an AC-named value) in two forms: a correct fake and a flipped
fake. This script copies the fake into the scratch worktree, runs the leaf's
tests, and classifies every test:

  PASS          test passed
  OUT_OF_SCOPE  test failed/errored with NotImplementedError — the fake
                deliberately implements only the target, so this test is not
                evidence either way
  FAIL          test failed/errored for any other reason

The saboteur reads the JSON: the correct fake must leave every in-scope test
green; the flipped fake must turn at least one in-scope test red.

Never runs git, never removes the scratch worktree. Exit 0 ran, 2 refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import check_invariants as ci  # noqa: E402
import run_gates as rg  # noqa: E402
import test_results as tr  # noqa: E402


def classify(run: tr.TestRun) -> dict[str, str]:
    out: dict[str, str] = {}
    for tid, state in run.states.items():
        if state == "PASS":
            out[tid] = "PASS"
        elif "NotImplementedError" in run.failure_text.get(tid, ""):
            out[tid] = "OUT_OF_SCOPE"
        else:
            out[tid] = "FAIL"
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--cascade")
    p.add_argument("--leaf", required=True)
    p.add_argument("--scratch-dir", type=Path, required=True)
    p.add_argument("--fake", action="append", default=[], metavar="IMPL_REL=SRC",
                   help="impl path (relative, must be in the brief's impl_files) = fake source file")
    p.add_argument("--label", default="")
    p.add_argument("--target", default="")
    p.add_argument("--test-cmd")
    p.add_argument("--timeout", type=int)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--briefs-dir", type=Path)
    p.add_argument("--json", action="store_true", help="accepted for symmetry; output is always JSON")
    args = p.parse_args(argv)

    root = ci.git_root(args.root.resolve())
    cfg = ci.load_config(root)
    slug = ci.discover_cascade_slug(root, args.cascade)
    bdir = ci.resolve_briefs_dir(root, cfg, args.briefs_dir, slug)
    b = rg.find_brief(bdir, args.leaf)
    if b is None:
        print(f"REFUSED: leaf `{args.leaf}` not found under {bdir}", file=sys.stderr)
        return 2
    if not args.scratch_dir.is_dir():
        print(f"REFUSED: scratch dir {args.scratch_dir} does not exist", file=sys.stderr)
        return 2
    impls = set(ci._leaf_paths(b, "impl"))
    pairs: list[tuple[str, Path]] = []
    for item in args.fake:
        lhs, sep, rhs = item.partition("=")
        if not sep or lhs not in impls:
            print(f"REFUSED: --fake `{lhs}` is not one of {args.leaf}'s impl_files {sorted(impls)}",
                  file=sys.stderr)
            return 2
        if not Path(rhs).is_file():
            print(f"REFUSED: fake source {rhs} not found", file=sys.stderr)
            return 2
        pairs.append((lhs, Path(rhs)))
    if not pairs:
        print("REFUSED: at least one --fake is required", file=sys.stderr)
        return 2

    for rel, src in pairs:
        dst = args.scratch_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text())

    sys.path.insert(0, str(SCRIPT_DIR))
    import degenerate_sweep as ds  # noqa: E402  (shared command resolution)
    cmd = ds.test_command(b, args.test_cmd)
    timeout = args.timeout or int(cfg["sabotage"]["timeout_seconds"])
    run = tr.run_tests(cmd, args.scratch_dir, timeout=timeout)
    states = classify(run)
    counts = {k: sum(1 for v in states.values() if v == k) for k in ("PASS", "OUT_OF_SCOPE", "FAIL")}
    in_scope = {t: s for t, s in states.items() if s != "OUT_OF_SCOPE"}
    print(json.dumps({
        "leaf": args.leaf, "label": args.label, "target": args.target, "cmd": " ".join(run.cmd),
        "returncode": run.returncode, "states": states, "counts": counts,
        "in_scope": in_scope,
        "out_of_scope": sorted(t for t, s in states.items() if s == "OUT_OF_SCOPE"),
        "collected": run.collected,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
