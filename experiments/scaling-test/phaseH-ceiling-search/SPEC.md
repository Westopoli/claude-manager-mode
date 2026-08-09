# Phase H — escalating-complexity ceiling search (post-Phase-G)

Phase G (`../phaseG-isolated-single-file/`) validated the redesigned
`/manager-mode` under genuine 3-agent isolation (test-writer → fresh
auditor → builder, no shared context between any two spawns — see
`../phaseG-isolated-single-file/SPEC.md` line 3, reused verbatim here, not
re-derived) across G1-G4 (220-1400 impl-LOC budgets), with zero unresolved
defects and a largest actual file of 339 LOC (24-75% utilization, mean
46%) — G never got close to finding a ceiling. G4's own REPORT.md flagged
that the domain's genuine complexity ceiling for that scope may sit below
1400 lines rather than the budget being too loose.

Phase H pushes deliberately far past G4's scale, in 3 widely-spread rungs
(not G's incremental +50%-ish steps) to find where a single large file
actually starts to break, per the explicit instruction that motivated this
phase: "go high... wide variance in the test is ok... it's ok if we
overshoot... we can always do more testing after the evidence is clear to
isolate a specific size."

`impl_files: 1` throughout, same as every G rung.

## Rungs

| Rung | Impl LOC budget | vs G4 | New complexity layer |
|---|---|---|---|
| H1 | 2200 | 1.6x | multi-tier approval/authorization workflow |
| H2 | 5000 | 3.6x | promotional-campaign stacking (time-windowed, own seeded ambiguity) |
| H3 | 9000 | 6.4x | regional tax-jurisdiction cascading + refund/partial-cancellation reversal logic |

Each layer is additive on the prior rung's scope (H2 = H1 + its layer, H3 =
H2 + its layer), same pattern G used (G2 = G1 + state machine, G3 = G2 +
audit helper, G4 = G3 + currency timing). Deliberately uneven multiples
(1.6x/3.6x/6.4x from G4, not an evenly-stepped progression) — this is a
coarse first pass meant to cover a wide range in 3 data points, not a final
calibration run; a follow-up can narrow in once evidence is clear.

The 12-module order-pricing domain (`../phaseE-leaf-ceiling-v2/MODULES.md`)
is already fully exhausted by G3/G4 — every layer below is genuinely new
business logic merged into the existing single file, not a new module
file, to force real LOC growth rather than budget headroom the domain
can't fill (G4's own problem: 1400 budget, 339 actual, 24% utilization).

## New complexity, by rung

### H1: multi-tier approval/authorization workflow

- A new `OrderApproval` concern, independent of the existing `OrderState`
  lifecycle (G2+). Orders whose `total` exceeds a configurable spend
  threshold (`APPROVAL_THRESHOLD`) require one or two named approver roles
  — `"manager"` for totals under a second, higher threshold
  (`ESCALATION_THRESHOLD`), `"manager"` then `"finance"` in that order for
  totals at or above it — recorded via `record_approval(order, role) ->
  dict` before `confirm_order` may proceed. `confirm_order` must raise
  `ValueError` if a required approval is missing, naming the missing role.
- Each `record_approval` call appends an entry to `AUDIT_LOG` via the
  existing `_audit_entry` helper (G3), reusing its established shape
  rather than inventing a new one — this specifically exercises the
  magnitude-aware escalation rule (extending an existing shared pattern
  correctly is the leaf's own call, not an escalation).
- Merges into the existing single file's orchestration logic (alongside
  `confirm_order`/`ship_order`) — no new module file.

### H2: promotional-campaign stacking with time-window validity

- A `CAMPAIGNS` registry, parallel in shape to the existing `COUPONS`
  registry but with `starts_at`/`ends_at` ISO-date bounds and a per-entry
  `stacking: "multiply" | "additive"` flag.
- `apply_campaign(order, campaign_id, as_of) -> dict` applies a campaign
  only if `as_of` falls within its window, and combines with whatever
  coupon/volume/membership discount chain has already run according to
  its `stacking` flag (multiply: apply the campaign's rate to the
  already-discounted amount; additive: subtract the campaign's flat/percent
  value from the pre-campaign amount, independent of prior discounts).
- **Seeded ambiguity (H2's own, independent of the coupon-order one kept
  from Phase E/F/G below):** the spec text below is written with two
  contradictory statements about *where in the discount chain* a campaign
  applies relative to coupon/volume/membership — one passage says
  "campaigns apply after all other discounts, to the final discounted
  total," another says "campaigns apply first, before any other discount
  logic runs, since promotional pricing supersedes standing discounts."
  (Author note for whoever fleshes out the full brief text: literally
  include both sentences, in different sections, same as Phase E/F/G's
  coupon-order contradiction — this is the H2-scale measurement constant.)

### H3: regional tax-jurisdiction cascading + refund/partial-cancellation reversal

- Multi-jurisdiction tax: `TAX_JURISDICTIONS` — state, local, and special
  district rates, each independently toggleable per region on the order's
  shipping address. `compute_tax(order) -> Decimal` sums whichever
  jurisdictions apply, each computed on the post-discount amount
  independently (not compounded on each other), stacked on the existing
  `tax.py`-equivalent scope from G3/G4.
- Refund/partial-cancellation reversal: `partial_refund(order, item_id,
  qty) -> dict` on a `"shipped"`-state order recomputes tax, campaign, and
  loyalty-point effects that were already applied to the cancelled
  quantity, **in reverse** — i.e., correctly "undoes" composed effects
  rather than just re-running forward logic on a smaller quantity. This is
  the most structurally demanding layer: it requires the implementation to
  track what was already applied to an order and in what order, so it can
  reverse it correctly — exactly the kind of thing a builder could
  plausibly lose track of in a single very large file. This is the rung
  explicitly designed to find where things break.

## The coupon-order contradiction (kept from Phase E/F/G, all rungs)

Same as every prior phase — kept as the cross-rung measurement constant,
not a confound to remove. H2 adds its own second, independent seeded
ambiguity (campaign-stacking order) rather than replacing this one.

## Isolation mechanics

Identical to Phase G — see `../phaseG-isolated-single-file/SPEC.md` for the
full description (test-writer → fresh auditor → builder, zero shared
context between any two spawns). Not re-derived here.

## Measurement methodology

Reuses Phase F's "Verification discipline" section and Phase G's
demonstrated practice (REPORT.md Findings 1-4): independent rerun of the
frozen test suite (never self-reported by any agent), per-role summed
token cost (test-writer / auditor / builder, plus any revision/re-audit
cycles), and a grep-based check of the actual resolved ambiguity at each
seeded contradiction site.

One measurement Phase H adds beyond G: a **within-file inconsistency
check** — does the seeded ambiguity (coupon-order, joined at H2+ by the
campaign-stacking one) get resolved *consistently* by every function in
the same file, or does one function in a rung disagree with another
function in the *same* file? Cross-*rung* drift (H1's resolution differing
from H3's) is expected and orthogonal per Phase G's Finding 2 — not a
failure signal on its own. Within-file drift is the actual "the file got
too big to track" signal this phase exists to look for.

## What "broken" means for this run

Pre-declared before any rung runs, so a bad result at H2 or H3 isn't
narrated after the fact. A rung is "broken" if it trips any of:

1. **Test failures at admission beyond a normal correction budget.** G1
   needed one revise/re-audit cycle, G2-G4 needed none — more than 2
   correction cycles at a single rung is itself a signal, independent of
   whether the rung eventually reaches GREEN.
2. **Contradictory internal conventions within the same file** — the same
   seeded ambiguity resolved two different ways by two different
   functions/call sites in one rung's single file (not cross-rung drift,
   which is expected per Phase G's Finding 2).
3. **Builder escalation behavior gone wrong** — either excessive
   escalation (repeated stop-and-ask instead of a confident,
   evidence-based call, the way G3's builder directly fixed the
   stock-threshold test bug rather than escalating it) or insufficient
   escalation (silently guessing at an underspecified interaction buried
   deep in a large file, which G6's escalation-trigger gate is supposed to
   catch but might miss at this scale).
4. **Token cost scaling worse than linearly** — tokens-per-output-LOC at
   H3 meaningfully exceeding H1's ratio, after accounting for the fixed
   per-spawn isolation tax Phase G's Finding 4 already documented (3-5
   spawns per rung has overhead independent of scope) — not just "H3
   costs more in total tokens" (expected, and not itself a signal).

A rung that lands under-utilized-but-clean (the G4 pattern — comfortably
under budget, zero defects) is **not** "broken" — it's inconclusive about
the ceiling, meaning the injected complexity layer still wasn't enough to
fill the budget. Worth its own note in the report as a distinct outcome
from "broke," since it changes what a follow-up experiment should try
next (bigger layer vs. bigger budget).

## Wording note

Same ambiguous-verb avoidance as Phase G's SPEC.md — do not use decide,
choose, design, determine, figure out, resolve, "as appropriate", "use
your judgment", pick, "select an approach" in Task-style prose written for
any leaf brief derived from this spec; see Phase G's SPEC.md for phrasing
alternatives already worked out for the coupon-order contradiction, reuse
the same alternatives for H2's campaign-stacking one.
