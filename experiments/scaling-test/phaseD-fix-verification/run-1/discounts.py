"""Discount rate lookups, coupon validation/application, and discount
stacking. See specs/discounts_engine.md AC-5, AC-6, AC-9 item 5."""

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(total_qty: int) -> float:
    if total_qty >= 50:
        return 0.10
    if total_qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier: str) -> float:
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier!r}")
    return rates[tier]


def apply_coupon(amount: float, code: str) -> float:
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code!r}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(
            f"amount {amount} below min_spend {coupon['min_spend']} for {code!r}"
        )
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal: float, total_qty: int, tier: str,
                     coupon_code: str | None = None) -> float:
    """Canonical order: coupon first, then volume, then membership."""
    amount = subtotal
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))
    return round(amount, 2)
