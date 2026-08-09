"""discounts.py — AC-5 (rate primitives, coupon) and AC-6 (stacking order).

Canonical stacking order (see .swarm/questions/leaf-D2-Q1.md for the
AC-6/AC-9 contradiction and its resolution): coupon first, then volume,
then membership.
"""

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(total_qty):
    if total_qty < 10:
        return 0.0
    if total_qty < 50:
        return 0.05
    return 0.10


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
        raise ValueError(f"amount {amount} below min_spend {coupon['min_spend']}")
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    amount = subtotal
    if coupon_code:
        amount = apply_coupon(amount, coupon_code)
    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))
    return round(amount, 2)
