"""Single-file order-pricing engine.

Pipeline: validate_order -> line_item_subtotal -> volume_discount_rate +
membership_discount_rate (applied sequentially, not additively) ->
calculate_tax -> shipping_cost -> build_invoice.

NOTE on discount stacking: the brief for this module contains two
contradictory descriptions of how the volume discount and membership
discount combine:

  (a) sequential-multiplicative (canonical, per the numbered rule):
      after_volume = subtotal * (1 - volume_rate)
      after_membership = after_volume * (1 - membership_rate)

  (b) additive/combined-rate (mentioned as an aside, explicitly called
      out as WRONG in the brief):
      combined_rate = volume_rate + membership_rate
      after_membership = subtotal * (1 - combined_rate)

This implementation follows (a), the sequential-multiplicative rule,
because the brief explicitly names it as canonical and explicitly flags
the additive version as incorrect.
"""

REGION_TAX_RATES = {
    "US-CA": 0.0825,
    "US-OR": 0.0,
    "US-NY": 0.08875,
    "EU": 0.20,
}

MEMBERSHIP_DISCOUNT_RATES = {
    "none": 0.0,
    "silver": 0.03,
    "gold": 0.07,
    "platinum": 0.12,
}

REQUIRED_ORDER_FIELDS = ("items", "region", "membership_tier", "shipping")


def validate_order(order: dict) -> None:
    for field in REQUIRED_ORDER_FIELDS:
        if field not in order:
            raise ValueError(f"order is missing required field: {field}")

    items = order["items"]
    if not items:
        raise ValueError("order field 'items' must not be empty")

    for item in items:
        if item.get("unit_price", 0) <= 0:
            raise ValueError(
                f"item {item.get('sku')!r} has invalid unit_price: "
                f"{item.get('unit_price')!r} (must be > 0)"
            )
        if item.get("qty", 0) <= 0:
            raise ValueError(
                f"item {item.get('sku')!r} has invalid qty: "
                f"{item.get('qty')!r} (must be > 0)"
            )


def line_item_subtotal(items: list) -> tuple:
    per_sku_subtotals = {}
    total_qty = 0
    for item in items:
        sku = item["sku"]
        unit_price = item["unit_price"]
        qty = item["qty"]
        line_total = round(unit_price * qty, 2)
        per_sku_subtotals[sku] = line_total
        total_qty += qty

    order_subtotal = round(sum(per_sku_subtotals.values()), 2)
    return per_sku_subtotals, order_subtotal, total_qty


def volume_discount_rate(total_qty: int) -> float:
    if total_qty >= 50:
        return 0.10
    if total_qty >= 10:
        return 0.05
    return 0.0


def membership_discount_rate(tier: str) -> float:
    if tier not in MEMBERSHIP_DISCOUNT_RATES:
        raise ValueError(f"unknown membership_tier: {tier!r}")
    return MEMBERSHIP_DISCOUNT_RATES[tier]


def calculate_tax(amount: float, region: str) -> float:
    if region not in REGION_TAX_RATES:
        raise ValueError(f"unknown region: {region!r}")
    rate = REGION_TAX_RATES[region]
    return round(amount * rate, 2)


def shipping_cost(weight_kg: float, distance_km: float, express: bool) -> float:
    if weight_kg <= 0:
        raise ValueError(f"invalid weight_kg: {weight_kg!r} (must be > 0)")
    if distance_km <= 0:
        raise ValueError(f"invalid distance_km: {distance_km!r} (must be > 0)")

    base = round(2.5 + 0.4 * weight_kg + 0.05 * distance_km, 2)
    if express:
        base = round(base * 1.5, 2)
    return base


def build_invoice(order: dict) -> dict:
    validate_order(order)

    per_sku_subtotals, order_subtotal, total_qty = line_item_subtotal(
        order["items"]
    )

    volume_rate = volume_discount_rate(total_qty)
    membership_rate = membership_discount_rate(order["membership_tier"])

    # Sequential-multiplicative stacking (canonical rule) — NOT additive.
    after_volume = order_subtotal * (1 - volume_rate)
    after_membership = after_volume * (1 - membership_rate)

    discount_amount = round(order_subtotal - after_membership, 2)
    post_discount_amount = round(after_membership, 2)

    tax = calculate_tax(after_membership, order["region"])

    shipping = order["shipping"]
    ship_cost = shipping_cost(
        shipping["weight_kg"], shipping["distance_km"], shipping["express"]
    )

    total = round(after_membership + tax + ship_cost, 2)

    return {
        "line_items": per_sku_subtotals,
        "subtotal": order_subtotal,
        "discount_amount": discount_amount,
        "post_discount_amount": post_discount_amount,
        "tax": tax,
        "shipping": ship_cost,
        "total": total,
    }
