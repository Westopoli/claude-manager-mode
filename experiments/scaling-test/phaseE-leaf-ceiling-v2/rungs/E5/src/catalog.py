CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def build_line_items(items):
    per_sku_subtotals = {}
    order_subtotal = 0.0
    total_qty = 0
    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]
        record = CATALOG[sku]
        if qty > record["stock"]:
            raise ValueError(f"qty {qty} exceeds stock for sku {sku}")
        line_total = round(record["unit_price"] * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty
    order_subtotal = round(order_subtotal, 2)
    return per_sku_subtotals, order_subtotal, total_qty
