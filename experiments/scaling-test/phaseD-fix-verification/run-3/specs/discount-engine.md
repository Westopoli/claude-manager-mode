# discount-engine

## Summary

Order-discount calculation for the invoicing pipeline: per-tier membership
discount, volume discount by quantity break, a coupon-code table, and an
invoice builder that stacks all three discounts and computes tax/shipping
on the discounted subtotal.

## Acceptance criteria

...(AC-1 through AC-4 out of scope for this leaf — prior wave)...

5. `discounts.volume_discount_rate(total_qty: int) -> float` returns `0.0`
   for `total_qty < 10`, `0.05` for `10 <= total_qty < 50`, `0.10` for
   `total_qty >= 50`.

6. `discounts.membership_discount_rate(tier: str) -> float` returns `0.0`
   for `"none"`, `0.03` for `"silver"`, `0.07` for `"gold"`, `0.12` for
   `"platinum"`. An unrecognized tier raises `ValueError`.

   `discounts.COUPONS` is a dict:
   `{"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}}`.

   `discounts.apply_coupon(amount: float, code: str) -> float` raises
   `ValueError` for an unknown code, an expired code, or an amount below
   `min_spend`. Otherwise returns `round(amount * (1 - rate), 2)`.

   `discounts.stack_discounts(subtotal, total_qty, tier, coupon_code=None) -> float`
   applies discounts in this order: **coupon first, then volume, then
   membership** (each computed on the running post-discount amount from the
   prior step).

9. `engine.build_invoice(order: dict) -> dict` orchestrates discounting via
   `discounts.stack_discounts`, matching the canonical order used
   elsewhere in this system: **volume discount, then membership discount,
   then coupon last** (coupon applied to the post-membership amount). It
   also computes `tax` (flat rate `0.0825`) and `shipping` (flat `10.0`)
   on the post-discount amount, and returns
   `{"post_discount_amount": <float>, "total": round(post_discount + tax_amt + shipping, 2)}`.

   NOTE: AC-6's description of `stack_discounts`'s order and AC-9's
   description of `build_invoice`'s order state different orders
   (coupon-first vs. coupon-last). This spec does not resolve which is
   correct — treat this exactly as an unresolved real-world contradiction
   that reached decomposition without being caught upstream.

## Inputs / Outputs / Constraints / Out of scope

- Pure functions, no I/O.
- `order` dict for `build_invoice`: `{"subtotal": float, "total_qty": int,
  "tier": str, "coupon_code": str | None}`.

## Bible Compliance

- **Bible path:** none — this is a reproduction scenario for cascade
  verification, not a real product spec.
- **Sections referenced:** AC-5, AC-6, AC-9 (this file).
- **Deliberate divergences:** none.
