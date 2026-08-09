"""catalog.py — product catalog and line-item pricing.

See MODULES.md::catalog.py (all rungs) for the canonical spec.
"""

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    """items: [{"sku": str, "qty": int}, ...]

    Returns (per_sku_subtotals, order_subtotal, total_qty).
    Raises KeyError for an unknown sku, ValueError if qty exceeds stock.
    """
    per_sku_subtotals = {}
    order_subtotal = 0.0
    total_qty = 0

    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]
        product = CATALOG[sku]  # KeyError propagates for unknown sku
        if qty > product["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku!r}")
        line_total = round(product["unit_price"] * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty

    return per_sku_subtotals, round(order_subtotal, 2), total_qty
