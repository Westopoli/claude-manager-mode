def validate_order(order):
    items = order.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("items must be a non-empty list")

    if "region" not in order:
        raise ValueError("region is required")

    if "membership_tier" not in order:
        raise ValueError("membership_tier is required")

    if "currency" not in order:
        raise ValueError("currency is required")
