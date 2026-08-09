# Phase D brief — reused verbatim across all 3 runs

Working directory for this run: given to you separately per run.

Domain: a 2-file order-discount leaf, `discounts.py` + `engine.py` — the same
shape as the leaf that broke in the prior experiment (Phase C, rung C3).

**Canonical rules** you are implementing, from a locked spec (treat this
exactly as if it were `SPEC.md`'s AC-5/AC-6/AC-9 sections, already reviewed):

- `volume_discount_rate(total_qty: int) -> float` — `0.0` for `< 10`, `0.05`
  for `10 <= qty < 50`, `0.10` for `qty >= 50`.
- `membership_discount_rate(tier: str) -> float` — `"none"` → `0.0`,
  `"silver"` → `0.03`, `"gold"` → `0.07`, `"platinum"` → `0.12`. Unknown
  tier raises `ValueError`.
- `COUPONS: dict` — `{"SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False}}`.
- `apply_coupon(amount: float, code: str) -> float` — unknown/expired/below-
  min-spend all raise `ValueError`. Otherwise `round(amount * (1 - rate), 2)`.
- `stack_discounts(subtotal, total_qty, tier, coupon_code=None) -> float` in
  `discounts.py` — **canonical order: coupon first, then volume, then
  membership.**
- `build_invoice(order: dict) -> dict` in `engine.py` — orchestrates
  discounting via `discounts.stack_discounts`, **matching the canonical
  order used elsewhere in this system: volume discount, then membership
  discount, then coupon last** (coupon applied to the post-membership
  amount). Also computes `tax` (flat 0.0825) and `shipping` (flat 10.0) on
  the post-discount amount, returns
  `{"post_discount_amount": ..., "total": round(post_discount + tax_amt + shipping, 2)}`.

You will notice `stack_discounts`'s description and `build_invoice`'s
description state **different orders** for applying volume/membership/
coupon (coupon-first vs. coupon-last). This is a real, deliberately
unresolved contradiction in this brief — there is no third source in this
document that resolves it. Handle it exactly as you would in a real
production leaf under the current `/manager-mode` process.
