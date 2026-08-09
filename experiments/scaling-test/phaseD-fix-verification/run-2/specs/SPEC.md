# SPEC — Order discount + invoice engine

## Summary

A small order-discounting subsystem: `discounts.py` computes discount rates
and stacks them; `engine.py` orchestrates discounting plus tax/shipping to
build a final invoice.

## Acceptance criteria

### AC-5: Discount rate + coupon primitives (discounts.py)

1. `volume_discount_rate(total_qty: int) -> float` — `0.0` for `< 10`, `0.05`
   for `10 <= qty < 50`, `0.10` for `qty >= 50`.
2. `membership_discount_rate(tier: str) -> float` — `"none"` -> `0.0`,
   `"silver"` -> `0.03`, `"gold"` -> `0.07`, `"platinum"` -> `0.12`. Unknown
   tier raises `ValueError`.
3. `COUPONS: dict` — `{"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}}`.
4. `apply_coupon(amount: float, code: str) -> float` — unknown/expired/below-
   min-spend all raise `ValueError`. Otherwise `round(amount * (1 - rate), 2)`.

### AC-6: Discount stacking (discounts.py)

`stack_discounts(subtotal, total_qty, tier, coupon_code=None) -> float` —
**canonical order: coupon first, then volume, then membership.**

### AC-9: Invoice orchestration (engine.py)

`build_invoice(order: dict) -> dict` orchestrates discounting via
`discounts.stack_discounts`, **matching the canonical order used elsewhere
in this system: volume discount, then membership discount, then coupon last**
(coupon applied to the post-membership amount). Also computes `tax` (flat
0.0825) and `shipping` (flat 10.0) on the post-discount amount, returns
`{"post_discount_amount": ..., "total": round(post_discount + tax_amt + shipping, 2)}`.

## Note

AC-6 and AC-9 state different stacking orders (coupon-first vs coupon-last).
This is a real, deliberately unresolved contradiction — there is no third
source in this document that resolves it.
