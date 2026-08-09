"""discounts.py — spec: specs/order-pricing-e3.md::Acceptance criteria::AC-2..AC-5

stack_discounts implements its OWN canonical order: coupon first, then
volume, then membership — per the spec's "Discount-order resolution"
section (this is the resolved half of the deliberate coupon-first vs
coupon-last contradiction inherited from the bible).
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
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code!r}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount {amount} below min_spend for coupon {code!r}")
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    amount = subtotal
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))
    return round(amount, 2)
