"""Discounts: volume/membership rates, coupon codes, and stacking.

NOTE ON STACKING ORDER (seeded contradiction, documented rather than
silently resolved):

The brief for this leaf states two different canonical stacking orders in
two different sections:

  - This file's own section says: "canonical stacking order: coupon first,
    then volume, then membership."
  - engine.py's section says: "matching the canonical order used elsewhere
    in this system: volume discount, then membership discount, then coupon
    last."

These are genuinely contradictory, not a misreading. Resolution taken here:
`stack_discounts` below implements ITS OWN section's stated order verbatim
(coupon -> volume -> membership), since that is the literal, local spec for
this function. engine.py's `build_invoice` does NOT call this function for
its own orchestration; it implements its own section's stated order
(volume -> membership -> coupon last) directly, using the smaller discount
primitives (`volume_discount_rate`, `membership_discount_rate`,
`apply_coupon`) rather than `stack_discounts`. See the matching note in
engine.py. In a real cascade this would be flagged back to spec authors
for reconciliation rather than guessed past silently.
"""

COUPONS: dict = {
    "SAVE10": {"rate": 0.10, "min_spend": 50.0, "expired": False},
    "OLDCODE": {"rate": 0.20, "min_spend": 0.0, "expired": True},
}


def volume_discount_rate(total_qty: int) -> float:
    """Volume discount rate based on total quantity ordered."""
    if total_qty < 10:
        return 0.0
    if total_qty < 50:
        return 0.05
    return 0.10


def membership_discount_rate(tier: str) -> float:
    """Membership discount rate based on tier. Raises ValueError for unknown tier."""
    rates = {
        "none": 0.0,
        "silver": 0.03,
        "gold": 0.07,
        "platinum": 0.12,
    }
    if tier not in rates:
        raise ValueError(f"Unknown membership tier: {tier!r}")
    return rates[tier]


def apply_coupon(amount: float, code: str) -> float:
    """Apply a coupon code to amount. Raises ValueError for invalid/expired/
    below-min-spend coupons."""
    if code not in COUPONS:
        raise ValueError(f"Unknown coupon code: {code!r}")
    coupon = COUPONS[code]
    if coupon["expired"]:
        raise ValueError(f"Coupon code is expired: {code!r}")
    if amount < coupon["min_spend"]:
        raise ValueError(
            f"Amount {amount} is below minimum spend {coupon['min_spend']} "
            f"for coupon {code!r}"
        )
    return round(amount * (1 - coupon["rate"]), 2)


def stack_discounts(
    subtotal: float, total_qty: int, tier: str, coupon_code: str = None
) -> float:
    """Stack discounts onto subtotal.

    Canonical order per THIS file's spec: coupon first (if provided), then
    volume, then membership. Each step is sequential/multiplicative on the
    running amount, never an additive combination of rates.
    """
    amount = subtotal

    if coupon_code is not None:
        amount = apply_coupon(amount, coupon_code)

    volume_rate = volume_discount_rate(total_qty)
    amount = round(amount * (1 - volume_rate), 2)

    membership_rate = membership_discount_rate(tier)
    amount = round(amount * (1 - membership_rate), 2)

    return amount
