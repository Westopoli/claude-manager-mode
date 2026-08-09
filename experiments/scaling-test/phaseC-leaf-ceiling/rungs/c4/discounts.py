"""Discount stacking: volume, membership, coupon, loyalty points."""

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
    return {
        "none": 0.0,
        "silver": 0.03,
        "gold": 0.07,
        "platinum": 0.12,
    }[tier]


def apply_coupon(amount: float, code: str) -> float:
    if code not in COUPONS:
        raise ValueError(f"unknown coupon code: {code}")

    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"coupon expired: {code}")
    if amount < coupon["min_spend"]:
        raise ValueError(f"amount below minimum spend for coupon: {code}")

    return round(amount * (1 - coupon["rate"]), 2)


def redeem_loyalty_points(amount: float, points_available: int, points_to_redeem: int) -> float:
    if points_to_redeem < 0:
        raise ValueError("points_to_redeem must be >= 0")
    if points_to_redeem > points_available:
        raise ValueError("points_to_redeem cannot exceed points_available")

    result = round(amount - points_to_redeem / 100, 2)
    return max(result, 0.0)


def stack_discounts(
    subtotal,
    total_qty,
    tier,
    coupon_code=None,
    points_available=0,
    points_to_redeem=0,
) -> float:
    amount = subtotal

    amount = amount * (1 - volume_discount_rate(total_qty))
    amount = amount * (1 - membership_discount_rate(tier))

    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)

    if points_to_redeem > 0:
        amount = redeem_loyalty_points(amount, points_available, points_to_redeem)

    return amount
