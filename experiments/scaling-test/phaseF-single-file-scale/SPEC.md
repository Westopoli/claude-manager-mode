# Phase F — single-file scale axis (inverse of Phase E)

Phase E scaled file COUNT (3→12 files) while LOC stayed nearly flat (119→148
impl LOC). It proved the composition/reachability gate holds across file
count. But `test_quality_gate.py`'s own reachability/composition check is
gated on `impl_files >= 2` (see `skills/swarm-shared/scripts/test_quality_gate.py`
docstring: "no-op for any leaf with fewer than 2 impl_files"). A single huge
file NEVER triggers that gate, regardless of size — an axis Phase E never
tested.

Phase F holds `impl_files = 1` and scales total responsibility/LOC instead,
using the exact same domain, same modules, same seeded contradiction as
`../phaseE-leaf-ceiling-v2/MODULES.md` — just merged into one file per rung
instead of split across files. This makes F1/F2/F3 directly scope-matched to
E1/E3/E5 so results are comparable apples-to-apples on the file-count axis
alone.

## Rungs

| Rung | Matches | Modules folded into `src/pricing_engine.py` | Impl LOC budget |
|---|---|---|---|
| F1 | E1 scope | catalog, discounts, engine (`MODULES.md` lines 7-24) | 750 |
| F2 | E3 scope | + validation, currency, shipping, notifications | 1900 |
| F3 | E5 scope | + tax, loyalty, reporting, audit_log, inventory (full 12-module set) | 3200 |

All function/dict names, signatures, and behavior identical to `MODULES.md`
— just declared as top-level names in one file instead of one file per
module. No new domain logic to design.

## The contradiction, restated for single-file form

`MODULES.md`'s `discounts.py`/`engine.py` sections seed a coupon-order
contradiction between two *different files*. In single-file form there is no
second file to disagree with — the contradiction must be seeded as two
different docstrings/comments **within the same file** (e.g. a module-level
docstring near the discount functions stating one order, and `build_invoice`'s
own docstring/inline comment stating the other), with no external tiebreaker.
This tests whether an intra-file contradiction gets caught as reliably as an
inter-file one, when there's no "does the orchestrator actually call the
right thing" cross-file signal to lean on.

## What each rung's agent does (full solo pipeline, same as Phase E)

1. Write tests first (shard-test-writer role) against `src/pricing_engine.py`
   (not yet written). Confirm RED.
2. Implement `src/pricing_engine.py` only. Confirm GREEN.
3. Run `check_invariants.py` and `test_quality_gate.py` against the leaf.
   **Expect `test_quality_gate.py` to report SKIP** (fewer than 2
   `impl_files`) — that's the known, correct behavior being probed, not a
   bug. Note whether the agent notices and states this explicitly, or
   silently assumes "gate passed" without checking why.
4. Report: did it catch the intra-file contradiction before writing impl?
   How was it resolved? Any correction passes needed? Any point where the
   single file's size made it lose track of an earlier decision made
   elsewhere in the same file?

## What would falsify "file size doesn't matter, only file count does"

- Contradiction missed or resolved inconsistently at F2/F3 where it wasn't
  at F1 or at any Phase E rung.
- Agent conflates "gate passed" with "gate ran and found nothing" (the SKIP
  case) — a process-blind-spot finding, not a code-quality one, but real.
- Correction passes concentrated at the top rung (F3) the same way Phase E
  found them concentrated at the *parent/spec* role for E5, not the
  *builder* role — if so, single-file has the same profile as multi-file
  and the axis genuinely doesn't matter. If correction passes instead show
  up mid-implementation (builder loses the thread inside one big file),
  that's the actual new failure mode this phase exists to find.

## Verification discipline (same as every prior phase)

Independently rerun pytest, both gates, and grep for the actual seeded
contradiction's resolution in the impl — never take an agent's self-report
alone.
