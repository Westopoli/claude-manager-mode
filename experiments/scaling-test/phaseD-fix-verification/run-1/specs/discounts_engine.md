# Order Discount Engine

## Summary

A small order-pricing module that computes volume and membership discount
rates, validates and applies coupon codes, stacks all three discount types
into a single multiplier chain, and orchestrates a full invoice
(discounted subtotal + tax + shipping).

## Acceptance criteria

### AC-5: Discount rate lookups

1. `volume_discount_rate(total_qty: int) -> float` returns `0.0` for
   `total_qty < 10`, `0.05` for `10 <= total_qty < 50`, `0.10` for
   `total_qty >= 50`.
2. `membership_discount_rate(tier: str) -> float` returns `0.0` for
   `"none"`, `0.03` for `"silver"`, `0.07` for `"gold"`, `0.12` for
   `"platinum"`. Any other string raises `ValueError`.

### AC-6: Coupon application

3. `COUPONS: dict` is a module-level dict on `discounts.py` with at least
   the entry `{"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}}`.
4. `apply_coupon(amount: float, code: str) -> float` raises `ValueError`
   if `code` is not in `COUPONS`, if the coupon's `expired` flag is `True`,
   or if `amount` is below the coupon's `min_spend`. Otherwise it returns
   `round(amount * (1 - rate), 2)`.

### AC-9: Discount stacking and invoice orchestration

5. `stack_discounts(subtotal: float, total_qty: int, tier: str,
   coupon_code: str | None = None) -> float`, defined in `discounts.py`,
   stacks the coupon, volume, and membership discounts into a single
   multiplier chain applied to `subtotal`. **Canonical order: coupon
   first, then volume, then membership.** If `coupon_code` is `None`, skip
   the coupon step. Round the final result to 2 decimal places.
6. `build_invoice(order: dict) -> dict`, defined in `engine.py`,
   orchestrates discounting via `discounts.stack_discounts` — **matching
   the canonical order used elsewhere in this system: volume discount,
   then membership discount, then coupon last** (coupon applied to the
   post-membership amount). `build_invoice` also computes `tax` (flat rate
   `0.0825`) and `shipping` (flat `10.0`), both applied to the
   post-discount amount, and returns
   `{"post_discount_amount": <float>, "total": round(post_discount_amount + post_discount_amount * 0.0825 + 10.0, 2)}`.

## Inputs / Outputs / Constraints / Out of scope

- Inputs: `order` dict has keys `subtotal` (float), `total_qty` (int),
  `tier` (str), `coupon_code` (str or None, optional).
- Out of scope: persistence, currency formatting, multi-currency.

## Bible Compliance

- **Bible path:** none — this project has no source-of-truth doc beyond
  this spec.
- **Sections referenced:** AC-5, AC-6, AC-9 (all sections above).
- **Deliberate divergences:** none.

## Known open issue

AC-9's item 5 (`stack_discounts`) and item 6 (`build_invoice`) state two
different stacking orders for the same three discounts — coupon-first vs.
coupon-last. This is a real, unresolved contradiction in this locked
spec; no other section of this document states which order is the ground
truth. Flagged for a future spec revision. Any leaf/test-writer working
against AC-9 must escalate this rather than silently pick a side inside
impl only.
