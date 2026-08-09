"""validation.py — spec: specs/order-pricing-e3.md::Acceptance criteria::AC-6"""


def validate_order(order):
    items = order.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("items must be a non-empty list")
    if "region" not in order or not isinstance(order["region"], str):
        raise ValueError("region is missing or wrong-typed")
    if "membership_tier" not in order or not isinstance(order["membership_tier"], str):
        raise ValueError("membership_tier is missing or wrong-typed")
    if "currency" not in order or not isinstance(order["currency"], str):
        raise ValueError("currency is missing or wrong-typed")
