# Phase H — ceiling search — REPORT

All 3 rungs run under genuine 3-agent isolation (test-writer → fresh
auditor → builder, zero shared context between any two spawns, per
`../phaseG-isolated-single-file/SPEC.md`). H3 run and independently
verified this session; H1/H2 were run in an earlier session and are
re-verified here (fresh reruns, not trusted from prior reports) so this
report reflects one consistent, independently-checked pass across all
three.

## Results table

| Rung | LOC budget | Actual LOC | Utilization | Tests | Correction cycles | Result |
|---|---|---|---|---|---|---|
| H1 | 2200 | 471 | 21.4% | 68/68 | 1 (audit FAIL→REVISE→PASS) | GREEN |
| H2 | 5000 | 585 | 11.7% | 82/82 | 1 (audit FAIL→REVISE→PASS) | GREEN |
| H3 | 9000 | 527 | 5.9% | 103/103 | 1 (builder-side rounding/identity bug, fixed same pass) | GREEN |

All three independently reran via `python3 -m pytest tests/test_pricing_engine.py -q`
directly against each rung's own `src/`, not taken from any agent's
self-report.

**Headline: the ceiling was never found.** LOC utilization actively
*fell* as the budget grew 1.6x→3.6x→6.4x past G4 (21% → 12% → 6%) —
actual file size stayed roughly flat (471/585/527 lines) while budget
exploded. The domain's genuine complexity, even with H1's approval
workflow, H2's campaign stacking, and H3's tax cascading + reversal
bookkeeping all stacked into one file, still doesn't require anywhere
near the LOC these budgets allow. This confirms G4's own hypothesis
(flagged in Phase G's REPORT.md) that the domain's real ceiling sits well
below where these experiments have been probing — Phase H pushed 6.4x
further than G4 and still didn't hit it.

## Within-file consistency (H3's specific addition to the methodology)

All three carried-forward seeded ambiguities resolve identically at every
call site inside H3's single file — independently verified by reading
the actual resolution code, not just grepping for a comment:

- **Coupon-order → coupon-last**: `apply_coupon` applies discounts in the
  order volume → membership → coupon (coupon last), matching the pinned
  precedent from every prior rung (Phase G/H1/H2). Single implementation
  site, no drift possible.
- **Currency-timing → convert-last**: `confirm_order` computes
  `settlement_total` by converting the already-finalized USD `total` as
  its last step, comment explicitly resolves the seeded contradiction
  in-line, consistent with H1/H2.
- **Campaign-order → campaigns-after**: `apply_campaign` reads/mutates
  `order["post_discount_amount"]` — i.e. operates on the value already
  produced by the coupon/volume/membership chain, not a re-stack from raw
  subtotal. Consistent with H1/H2's pinned resolution.

No within-file drift found — H3 does not trip the "broken" criterion #2
(contradictory internal conventions within the same file).

`partial_refund` (H3's own new logic, the rung's actual point) correctly
reverses composed effects rather than re-running forward logic on a
smaller quantity: proportional share computed from `total_qty`, tax
reversed via `compute_tax`'s own per-order logic (not a flat re-guess,
so it respects the `special_district` toggle), loyalty points credited
back via `points_available` (not subtracted from `total`), campaign
effect implicitly reversed because the proportional share is taken from
`post_discount_amount`, which already reflects the campaign mutation.
Verified by reading the implementation directly (see file, lines 490-527)
against the brief's exact requirements — not the builder's self-report.

## "What broken means" — checked against all 4 pre-declared criteria, H3

1. **Correction cycles beyond budget** — 1 cycle (a rounding-precision bug
   and a `confirm_order` return-identity bug, both fixed same pass). Under
   the "more than 2 cycles" threshold. Not broken.
2. **Contradictory internal conventions** — none found (see above). Not
   broken.
3. **Builder escalation behavior** — no escalation triggered; the builder
   fixed both bugs directly as mechanical corrections (same pattern as
   Phase G's G3 finding) rather than over- or under-escalating. Not
   broken.
4. **Superlinear token cost** — H3's builder spawn (isolated 3-agent
   pipeline, this session) cost more in absolute tokens than H1/H2 due to
   the larger cumulative test surface, but this report does not have a
   clean apples-to-apples per-role token comparison against H1/H2's
   original run (different session, cost not recorded the same way at the
   time). Flagged as unverified rather than claimed either way — do not
   cite a token-scaling verdict for H3 without rerunning H1/H2 for a fair
   comparison.

**H3 verdict: not broken. Inconclusive on the ceiling** (same category as
G4) — comfortably under budget, zero unresolved defects, real new
complexity (tax cascading + genuine reversal bookkeeping) still didn't
fill anywhere close to the 9000-line budget.

## What this means for a follow-up

Per SPEC.md's own framing, an under-utilized-but-clean result is not a
failure, it's information: this domain (12 base modules + state machine +
audit helper + currency + approvals + campaigns + tax cascading +
proportional reversal) tops out around 500-600 real lines no matter how
generously the file's line budget is set. Finding an actual breaking
point would need either (a) a genuinely bigger domain (more independent
modules, not more layers stacked onto the same order-pricing concept), or
(b) accepting that single-large-file TDD leaves may simply not break at
any LOC count this kind of layered-business-logic domain can realistically
reach — which is itself a real, useful finding for `impl_line_budget`
calibration (the 1000-1500 target / 2500 hard cap in `playbook.md` looks
generous relative to what real single-concern domains actually need, not
tight).

Not scoping a Phase I here — flag as an open follow-up only if the user
wants to pursue a genuinely different (not just bigger) domain.
