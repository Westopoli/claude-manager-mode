---
leaf_id: leaf-C2
difficulty_tier: C2-single-file-large (1 file, ~450-line budget)
impl_line_budget: 450
test_assertion_budget: 35
seeded_fault: internal-contradiction (discount-stacking rule, semantic not numeric)
---

## Task

Working directory for this leaf: `/Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseC-leaf-ceiling/rungs/c2/`

Implement a single-file order-pricing engine at `pricing_engine.py`. Write its
tests first at `tests/test_pricing_engine.py`. This is one cohesive module —
all functions below belong in the same file because they form one pipeline
(`build_invoice` calls the rest).

**Canonical rules (ground truth):**

1. `validate_order(order: dict) -> None` — raises `ValueError` (with a
   message naming the field) if `order` is missing any of: `items` (list of
   `{"sku": str, "unit_price": float, "qty": int}`), `region` (str),
   `membership_tier` (str), `shipping` (`{"weight_kg": float, "distance_km": float, "express": bool}`).
   Also raises `ValueError` if `items` is empty, or if any `unit_price` or
   `qty` is `<= 0`.

2. `line_item_subtotal(items: list) -> tuple[dict, float, int]` — returns
   `(per_sku_subtotals, order_subtotal, total_qty)` where
   `per_sku_subtotals = {sku: round(unit_price * qty, 2)}`,
   `order_subtotal = round(sum of per-sku subtotals, 2)`,
   `total_qty = sum of qty`.

3. `volume_discount_rate(total_qty: int) -> float` — `0.0` for `< 10`,
   `0.05` for `10 <= qty < 50`, `0.10` for `qty >= 50`.

4. `membership_discount_rate(tier: str) -> float` — `"none"` → `0.0`,
   `"silver"` → `0.03`, `"gold"` → `0.07`, `"platinum"` → `0.12`. Any other
   string raises `ValueError`.

5. **Discount stacking — apply sequentially, not additively.** First apply
   volume discount to `order_subtotal` to get an intermediate amount, then
   apply the membership discount to *that intermediate amount* (not to the
   original subtotal, and not by summing the two rates into one combined
   rate). i.e. `after_volume = subtotal * (1 - volume_rate)`;
   `after_membership = after_volume * (1 - membership_rate)`.

   (Note: you may see a comment elsewhere in this brief describing discount
   stacking as "combined_rate = volume_rate + membership_rate, apply once to
   subtotal" — that is wrong. The sequential-multiplicative rule stated in
   this numbered item is the canonical one. If you notice this contradiction,
   report which version you implemented and why, exactly as you would flag a
   real spec/brief conflict.)

6. `calculate_tax(amount: float, region: str) -> float` — `US-CA` → 0.0825,
   `US-OR` → 0.0, `US-NY` → 0.08875, `EU` → 0.20. Unknown region raises
   `ValueError`. `tax = round(amount * rate, 2)`.

7. `shipping_cost(weight_kg: float, distance_km: float, express: bool) -> float`
   — base = `round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)`. If
   `express` is `True`, multiply the base by `1.5` before rounding again to
   2 decimals. `weight_kg <= 0` or `distance_km <= 0` raises `ValueError`.

8. `build_invoice(order: dict) -> dict` — orchestrates 1–7 in order (validate
   → line items → discounts, sequentially per rule 5 → tax on the
   post-discount amount → shipping, added after tax, not taxed itself) and
   returns:
   ```
   {
     "line_items": <per_sku_subtotals from step 2>,
     "subtotal": <order_subtotal>,
     "discount_amount": round(order_subtotal - after_membership, 2),
     "post_discount_amount": after_membership,
     "tax": <from step 6, computed on after_membership>,
     "shipping": <from step 7>,
     "total": round(after_membership + tax + shipping, 2),
   }
   ```
   (Comment aside — the combined-rate discount approach described as wrong in
   item 5 also applies here: do not use it.)

## Acceptance

Run `python3 -m pytest tests/test_pricing_engine.py` yourself via Bash from
the working directory above. Confirm RED before implementing. Implement in
`pricing_engine.py` only. Confirm GREEN by actually executing pytest — do not
hand-trace. Report the real pytest output.

## Report back

State: final impl line count vs the 450-line budget, whether you caught the
discount-stacking contradiction (additive vs sequential-multiplicative) and
which version you implemented, and literal pytest pass/fail counts from both
the RED and GREEN runs.
