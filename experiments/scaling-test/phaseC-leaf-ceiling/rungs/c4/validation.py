"""Order payload validation for the pricing engine."""

VALID_REGIONS = ("US-CA", "US-OR", "US-NY", "EU")
VALID_MEMBERSHIP_TIERS = ("none", "silver", "gold", "platinum")
VALID_CURRENCIES = ("USD", "EUR", "GBP")


def _fail(field, reason):
    raise ValueError(f"invalid '{field}': {reason}")


def _validate_items(items):
    if not isinstance(items, list) or len(items) == 0:
        _fail("items", "must be a non-empty list")
    for entry in items:
        if not isinstance(entry, dict):
            _fail("items", "each item must be an object")
        sku = entry.get("sku")
        qty = entry.get("qty")
        if not isinstance(sku, str):
            _fail("items", "each item must have a string 'sku'")
        if not isinstance(qty, int) or isinstance(qty, bool):
            _fail("items", "each item must have an integer 'qty'")
        if qty <= 0:
            _fail("items", "each item 'qty' must be > 0")


def _validate_region(region):
    if region not in VALID_REGIONS:
        _fail("region", f"must be one of {VALID_REGIONS}")


def _validate_membership_tier(tier):
    if tier not in VALID_MEMBERSHIP_TIERS:
        _fail("membership_tier", f"must be one of {VALID_MEMBERSHIP_TIERS}")


def _validate_shipping(shipping):
    if not isinstance(shipping, dict):
        _fail("shipping", "must be an object")

    weight_kg = shipping.get("weight_kg")
    distance_km = shipping.get("distance_km")
    express = shipping.get("express")

    if not isinstance(weight_kg, (int, float)) or isinstance(weight_kg, bool):
        _fail("shipping", "'weight_kg' must be a number")
    if weight_kg <= 0:
        _fail("shipping", "'weight_kg' must be > 0")

    if not isinstance(distance_km, (int, float)) or isinstance(distance_km, bool):
        _fail("shipping", "'distance_km' must be a number")
    if distance_km <= 0:
        _fail("shipping", "'distance_km' must be > 0")

    if not isinstance(express, bool):
        _fail("shipping", "'express' must be a bool")


def _validate_currency(currency):
    if currency not in VALID_CURRENCIES:
        _fail("currency", f"must be one of {VALID_CURRENCIES}")


def _validate_optional_fields(order):
    if "coupon_code" in order:
        coupon_code = order["coupon_code"]
        if not isinstance(coupon_code, str):
            _fail("coupon_code", "must be a string")

    if "loyalty_points_to_redeem" in order:
        points = order["loyalty_points_to_redeem"]
        if not isinstance(points, int) or isinstance(points, bool):
            _fail("loyalty_points_to_redeem", "must be an int")
        if points < 0:
            _fail("loyalty_points_to_redeem", "must be >= 0")


def validate_order(order: dict) -> None:
    """Validate an order payload. Raises ValueError naming the offending field."""
    if not isinstance(order, dict):
        raise ValueError("invalid order: must be an object")

    if "items" not in order:
        _fail("items", "is required")
    _validate_items(order["items"])

    if "region" not in order:
        _fail("region", "is required")
    _validate_region(order["region"])

    if "membership_tier" not in order:
        _fail("membership_tier", "is required")
    _validate_membership_tier(order["membership_tier"])

    if "shipping" not in order:
        _fail("shipping", "is required")
    _validate_shipping(order["shipping"])

    if "currency" not in order:
        _fail("currency", "is required")
    _validate_currency(order["currency"])

    _validate_optional_fields(order)
