"""discounts.py — volume, membership, and coupon discounts.

See MODULES.md::discounts.py (all rungs) for the canonical spec.

Discount-order note: MODULES.md states two different orders for
stack_discounts (this module's own section says coupon-first; engine.py's
section says volume, then membership, then coupon-last). This is a
deliberately unresolved contradiction (see .swarm/questions/leaf-E1-Q1.md
and .swarm/answers/leaf-E1-Q1.md). Resolved here as: volume, then
membership, then coupon-last — matching engine.py's stated order for the
orchestrator this function feeds.
"""

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(total_qty):
    if total_qty >= 50:
        return 0.10
    if total_qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier):
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier!r}")
    return rates[tier]


def apply_coupon(amount, code):
    coupon = COUPONS.get(code)
    if coupon is None:
        raise ValueError(f"unknown coupon code: {code!r}")
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(
            f"amount {amount} is below min_spend {coupon['min_spend']} "
            f"for coupon {code!r}"
        )
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    amount = round(subtotal * (1 - volume_discount_rate(total_qty)), 2)
    amount = round(amount * (1 - membership_discount_rate(tier)), 2)
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    return amount
