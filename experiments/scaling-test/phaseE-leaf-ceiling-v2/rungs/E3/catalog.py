"""catalog.py — spec: specs/order-pricing-e3.md::Acceptance criteria::AC-1"""

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    per_sku_subtotals = {}
    total_qty = 0
    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]
        product = CATALOG[sku]  # raises KeyError for unknown sku
        if qty > product["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku!r}")
        per_sku_subtotals[sku] = round(product["unit_price"] * qty, 2)
        total_qty += qty
    order_subtotal = round(sum(per_sku_subtotals.values()), 2)
    return per_sku_subtotals, order_subtotal, total_qty
