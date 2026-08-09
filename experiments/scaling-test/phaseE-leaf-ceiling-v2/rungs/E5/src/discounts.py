def volume_discount_rate(total_qty):
    if total_qty >= 50:
        return 0.10
    if total_qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier):
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier}")
    return rates[tier]


COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def apply_coupon(amount, code):
    coupon = COUPONS.get(code)
    if coupon is None:
        raise ValueError(f"unknown coupon code: {code}")
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount below min spend for coupon: {code}")
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    # Canonical order for this system: volume discount, then membership
    # discount, then coupon applied last (to the post-membership amount).
    amount = round(subtotal * (1 - volume_discount_rate(total_qty)), 2)
    amount = round(amount * (1 - membership_discount_rate(tier)), 2)
    if coupon_code:
        amount = apply_coupon(amount, coupon_code)
    return amount
