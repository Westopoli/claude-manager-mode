---
leaf_id: leaf-C3
difficulty_tier: C3-multi-file-cohesive (3 files, ~750-line budget)
impl_line_budget: 750
test_assertion_budget: 45
seeded_fault: cross-section-contradiction (discount-stacking order stated two ways in the same brief)
---

## Task

Working directory for this leaf: `/Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseC-leaf-ceiling/rungs/c3/`

Implement a 3-file order-pricing engine — `catalog.py`, `discounts.py`,
`engine.py` — with matching test files under `tests/`. These three are one
cohesive leaf: `engine.py` orchestrates the other two, `discounts.py` needs
catalog subtotals as input, and none of the three is independently useful
without the others.

### catalog.py

- `CATALOG: dict` — module-level, at least these entries:
  `{"widget": {"unit_price": 9.99, "stock": 100}, "gadget": {"unit_price": 24.50, "stock": 5}, "gizmo": {"unit_price": 3.25, "stock": 0}}`
- `lookup_price(sku: str) -> float` — returns `CATALOG[sku]["unit_price"]`, raises `KeyError` for unknown sku.
- `check_availability(sku: str, qty: int) -> None` — raises `ValueError` if `qty > CATALOG[sku]["stock"]`, or `KeyError` if sku unknown.
- `build_line_items(items: list) -> tuple[dict, float, int]` — `items` is `[{"sku": str, "qty": int}, ...]`. For each item, call `check_availability` then `lookup_price`. Returns `(per_sku_subtotals, order_subtotal, total_qty)` exactly as in a simple line-item subtotal calc: `per_sku_subtotals = {sku: round(price*qty, 2)}`, `order_subtotal = round(sum, 2)`, `total_qty = sum of qty`.

### discounts.py

- `volume_discount_rate(total_qty: int) -> float` — `0.0` for `< 10`, `0.05` for `10 <= qty < 50`, `0.10` for `qty >= 50`.
- `membership_discount_rate(tier: str) -> float` — `"none"` → `0.0`, `"silver"` → `0.03`, `"gold"` → `0.07`, `"platinum"` → `0.12`. Unknown tier raises `ValueError`.
- `COUPONS: dict` — module-level: `{"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}, "OLDCODE": {"rate": 0.20, "min_spend": 0.0, "expired": True}}`.
- `apply_coupon(amount: float, code: str) -> float` — raises `ValueError` if `code` not in `COUPONS`, if the coupon is expired, or if `amount < min_spend`. Otherwise returns `round(amount * (1 - rate), 2)`.
- `stack_discounts(subtotal: float, total_qty: int, tier: str, coupon_code: str = None) -> float` — **canonical stacking order: coupon first, then volume, then membership.** Apply `apply_coupon` to `subtotal` first (only if `coupon_code` is not `None`), then apply the volume discount to that result, then apply the membership discount to *that* result. Each step is sequential/multiplicative on the running amount, never additive combination of rates.

### engine.py

- `calculate_tax(amount: float, region: str) -> float` — `US-CA` → 0.0825, `US-OR` → 0.0, `US-NY` → 0.08875, `EU` → 0.20. Unknown region raises `ValueError`. `tax = round(amount * rate, 2)`.
- `shipping_cost(weight_kg: float, distance_km: float, express: bool) -> float` — base `round(2.5 + 0.4*weight_kg + 0.05*distance_km, 2)`, ×1.5 if express, rounded again. Non-positive weight/distance raises `ValueError`.
- `AUDIT_LOG: list` — module-level, starts empty.
- `build_invoice(order: dict) -> dict` — `order` has `items`, `region`, `membership_tier`, `coupon_code` (optional, may be absent or `None`), `shipping` (`{"weight_kg", "distance_km", "express"}`). Orchestration: `catalog.build_line_items` → `discounts.stack_discounts`, **matching the canonical order used elsewhere in this system: volume discount, then membership discount, then coupon last** (coupon applied to the post-membership amount, giving the customer the deepest final cut) → `calculate_tax` on the post-discount amount → `shipping_cost` added after tax (not itself taxed). Returns
  `{"line_items": ..., "subtotal": ..., "post_discount_amount": ..., "tax": ..., "shipping": ..., "total": round(post_discount_amount + tax + shipping, 2)}`.
  Also append `{"order_total": <total>}` to `AUDIT_LOG` before returning.

## Note on discount-stacking order

You may have noticed `discounts.py`'s description and `engine.py`'s
description state **different orders** for `stack_discounts` (coupon-first
vs. coupon-last). This is a real contradiction, not a mistake in your
reading — decide how you'd actually handle this as a careful builder: do you
guess, pick one and note it, or escalate? Report your reasoning and your
resolution explicitly. There is intentionally no single "correct" answer
written elsewhere in this brief to resolve it for you — that's the point of
this rung.

## Acceptance

Run `python3 -m pytest tests/` yourself via Bash from the working directory
above. Confirm RED before implementing. Implement in the three impl files
only. Confirm GREEN by actually executing pytest — do not hand-trace. Report
real pytest output.

## Report back

State: total impl line count across the 3 files vs the 750-line budget, how
you handled the coupon-ordering contradiction (guessed silently / picked one
and documented / escalated — and which order you actually implemented), and
literal pytest pass/fail counts from RED and GREEN.
