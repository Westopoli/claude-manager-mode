# Phase G — isolated single-file validation (post-redesign)

Validates the redesigned `/manager-mode` (see `/Users/westley/.claude/plans/this-has-me-thinking-happy-moth.md`) under genuine 3-agent isolation: a test-writer, a fresh test-auditor, and a builder, as three separate agent spawns with no shared context — unlike Phase F, where one agent played all roles sequentially in one session.

Reuses the order-pricing domain from `../phaseE-leaf-ceiling-v2/MODULES.md` (catalog, discounts, engine, validation, currency, shipping, notifications, tax, loyalty, reporting, audit_log, inventory — same names/signatures/behavior as that file) plus new complexity below that Phase E/F didn't have, to force genuine LOC growth rather than budget headroom.

**Every rung is `impl_files: 1`** — testing the single-file axis throughout, same as Phase F.

## New complexity (beyond `MODULES.md`), by rung

### G2+: order lifecycle state machine

- `OrderState` — one of the strings `"draft"`, `"validated"`, `"priced"`, `"confirmed"`, `"shipped"`, in that order.
- Each of these functions requires the order to be in a specific prior state, and raises `ValueError` naming the required state if it isn't: `validate_order` requires `"draft"` (transitions to `"validated"` on success); pricing (the part of `build_invoice` that computes `post_discount_amount`/`total`) requires `"validated"` (transitions to `"priced"`); `confirm_order(order) -> dict` requires `"priced"` (transitions to `"confirmed"`, returns the order); `ship_order(order) -> dict` requires `"confirmed"` (transitions to `"shipped"`, returns the order). An order's state lives at `order["state"]`, defaulting to `"draft"` if absent.

### G3+: shared audit-log entry helper

- `_audit_entry(action: str, order_id: str, detail: dict) -> dict` — returns `{"action": action, "order_id": order_id, "detail": detail}`. Every state-mutating function (`reserve_stock`, `redeem_loyalty_points`, `confirm_order`, `apply_coupon`) must call this helper and append its return value to `AUDIT_LOG` — same shape every time, one shared call site pattern, not four different inline dict literals.

### G4: multi-currency settlement + a second, independent seeded ambiguity

- `confirm_order` accepts an optional `settlement_currency` argument. When given, the order's `total` (computed in USD by the pricing step) must be converted via `convert()` at a specific point in the pipeline — **seed this ambiguity intra-file**: a comment near `convert()`/`format_currency()` states conversion happens "as the very last step, after `total` is finalized"; a separate comment on `confirm_order` states conversion happens "before tax is applied, so tax is computed in the settlement currency." These give numerically different results (rounding at a different stage changes the total by cents) and neither is confirmed anywhere else in this document. This ambiguity has **no precedent in any prior phase** (E1-E5, F1-F3 never had a currency-timing question) — unlike the coupon-order contradiction below, which does.

## The coupon-order contradiction (kept from Phase E/F, all rungs)

Same as Phase E/F: seed intra-file, two comment blocks in the same file stating different orders for `stack_discounts` (coupon-first-then-volume-then-membership vs. volume-then-membership-then-coupon-last). By G3/G4 this has 6 prior data points as precedent (E1-E5, F1-F3) if an agent looks for it — kept deliberately, this is part of what's being measured, not a confound to remove.

## Rungs

| Rung | Modules in scope | New complexity | Impl LOC budget |
|---|---|---|---|
| G1 | catalog, discounts, engine (`MODULES.md` lines 7-24) | none | 220 |
| G2 | + validation, currency, shipping, notifications | order lifecycle state machine | 480 |
| G3 | + tax, loyalty, reporting, audit_log, inventory (full `MODULES.md` set) | + shared audit-log helper, called from 4 sites | 900 |
| G4 | same as G3 | + multi-currency settlement timing ambiguity | 1400 |

## Wording note for whoever writes each rung's goal statement

Do not use these words in Task-style prose handed to the test-writer or builder: decide, choose, design, determine, figure out, resolve, "as appropriate", "use your judgment", pick, "select an approach" — `check_invariants.py`'s `no-design` check scans for them literally, in Task prose specifically (fixed in this redesign to no longer scan brief boilerplate, but genuine Task-section use still trips it, confirmed via direct replay). Say "apply the tiebreaker precedent" or "pick whichever the orchestrator's own code implements as authoritative" instead of "resolve"; say "the test-writer's own tiebreaker call" instead of "determine".
