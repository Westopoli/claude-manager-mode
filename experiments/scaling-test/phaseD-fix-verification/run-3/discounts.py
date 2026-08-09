# spec: specs/discount-engine.md::Acceptance criteria::AC-5, AC-6

COUPONS = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
}


def volume_discount_rate(total_qty: int) -> float:
    if total_qty < 10:
        return 0.0
    if total_qty < 50:
        return 0.05
    return 0.10


def membership_discount_rate(tier: str) -> float:
    rates = {"none": 0.0, "silver": 0.03, "gold": 0.07, "platinum": 0.12}
    if tier not in rates:
        raise ValueError(f"unknown membership tier: {tier!r}")
    return rates[tier]


def apply_coupon(amount: float, code: str) -> float:
    coupon = COUPONS.get(code)
    if coupon is None:
        raise ValueError(f"unknown coupon code: {code!r}")
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount below min_spend for coupon: {code!r}")
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(subtotal: float, total_qty: int, tier: str,
                     coupon_code: str | None = None) -> float:
    # Canonical order (AC-6): coupon first, then volume, then membership.
    amount = subtotal
    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)
    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))
    return round(amount, 2)
