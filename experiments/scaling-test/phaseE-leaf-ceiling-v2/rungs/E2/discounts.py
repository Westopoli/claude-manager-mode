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


COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def apply_coupon(amount, code):
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code!r}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(
            f"amount {amount} is below coupon min_spend {coupon['min_spend']}"
        )
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal, total_qty, tier, coupon_code=None):
    """Canonical order per this module's own contract: coupon first, then
    volume, then membership. See leaf-E2.TESTWRITER-DECISION.md for why
    this order (not engine.py's prose description) is the one the test
    suite pins down, and test_discounts.py's
    test_stack_discounts_order_proof_coupon_first for the numeric proof.
    """
    amount = subtotal
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))
    return round(amount, 2)
