"""Engine: tax, shipping, and full invoice orchestration.

NOTE ON STACKING ORDER (seeded contradiction, documented rather than
silently resolved) -- see the matching, longer note in discounts.py.

This section of the original brief states: "matching the canonical order
used elsewhere in this system: volume discount, then membership discount,
then coupon last (coupon applied to the post-membership amount, giving the
customer the deepest final cut)". discounts.py's own section states the
opposite order for `stack_discounts` (coupon first). Rather than silently
picking one and burying the conflict, `build_invoice` below deliberately
does NOT call `discounts.stack_discounts` (which implements the
coupon-first order per its own section). Instead it applies the three
discount steps directly, in THIS section's stated order (volume ->
membership -> coupon last), using the smaller discount primitives. This
keeps both files internally consistent with their own local spec text
instead of forcing one file to silently override the other's explicit
statement. In a real cascade, this contradiction would be escalated to
spec authors for reconciliation instead of guessed past.
"""

import catalog
import discounts

TAX_RATES = {
    "US-CA": 0.0825,
    "US-OR": 0.0,
    "US-NY": 0.08875,
    "EU": 0.20,
}

AUDIT_LOG: list = []


def calculate_tax(amount: float, region: str) -> float:
    """Calculate tax for amount in region. Raises ValueError for unknown region."""
    if region not in TAX_RATES:
        raise ValueError(f"Unknown tax region: {region!r}")
    rate = TAX_RATES[region]
    return round(amount * rate, 2)


def shipping_cost(weight_kg: float, distance_km: float, express: bool) -> float:
    """Calculate shipping cost. Raises ValueError for non-positive weight/distance."""
    if weight_kg <= 0 or distance_km <= 0:
        raise ValueError("weight_kg and distance_km must be positive")
    base = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = round(base * 1.5, 2)
    return base


def build_invoice(order: dict) -> dict:
    """Orchestrate a full invoice: line items -> discounts -> tax -> shipping.

    order: {
        "items": [{"sku": str, "qty": int}, ...],
        "region": str,
        "membership_tier": str,
        "coupon_code": str | None,   # optional
        "shipping": {"weight_kg": float, "distance_km": float, "express": bool},
    }
    """
    items = order["items"]
    region = order["region"]
    tier = order["membership_tier"]
    coupon_code = order.get("coupon_code")
    shipping_info = order["shipping"]

    line_items, subtotal, total_qty = catalog.build_line_items(items)

    # Discount order per THIS module's section: volume, then membership,
    # then coupon last (applied to the post-membership amount).
    amount = subtotal

    volume_rate = discounts.volume_discount_rate(total_qty)
    amount = round(amount * (1 - volume_rate), 2)

    membership_rate = discounts.membership_discount_rate(tier)
    amount = round(amount * (1 - membership_rate), 2)

    if coupon_code is not None:
        amount = discounts.apply_coupon(amount, coupon_code)

    post_discount_amount = amount

    tax = calculate_tax(post_discount_amount, region)

    shipping = shipping_cost(
        shipping_info["weight_kg"],
        shipping_info["distance_km"],
        shipping_info["express"],
    )

    total = round(post_discount_amount + tax + shipping, 2)

    invoice = {
        "line_items": line_items,
        "subtotal": subtotal,
        "post_discount_amount": post_discount_amount,
        "tax": tax,
        "shipping": shipping,
        "total": total,
    }

    AUDIT_LOG.append({"order_total": total})

    return invoice
