"""Product catalog and line-item aggregation."""

CATALOG = {
    "widget": {"unit_price": 9.99, "stock": 100, "tax_exempt": False},
    "gadget": {"unit_price": 24.50, "stock": 5, "tax_exempt": False},
    "book": {"unit_price": 14.00, "stock": 50, "tax_exempt": True},
}


def build_line_items(items: list) -> tuple:
    """Aggregate order items against CATALOG.

    Returns (line_items_by_sku, order_subtotal, total_qty).
    Raises KeyError for an unknown sku, ValueError for insufficient stock.
    """
    line_items = {}
    subtotal = 0.0
    total_qty = 0

    for entry in items:
        sku = entry["sku"]
        qty = entry["qty"]

        if sku not in CATALOG:
            raise KeyError(f"unknown sku: {sku}")

        product = CATALOG[sku]
        if qty > product["stock"]:
            raise ValueError(f"insufficient stock for sku: {sku}")

        line_subtotal = round(product["unit_price"] * qty, 2)

        if sku in line_items:
            line_items[sku]["qty"] += qty
            line_items[sku]["line_subtotal"] = round(
                line_items[sku]["line_subtotal"] + line_subtotal, 2
            )
        else:
            line_items[sku] = {
                "qty": qty,
                "unit_price": product["unit_price"],
                "line_subtotal": line_subtotal,
            }

        subtotal = round(subtotal + line_subtotal, 2)
        total_qty += qty

    return line_items, subtotal, total_qty


def order_tax_exempt(items: list) -> bool:
    """Determine whether the whole order should be treated as tax-exempt.

    AMBIGUITY NOTE: the source spec described this "as appropriate" without
    specifying the aggregation rule across mixed line items (all-exempt vs.
    any-exempt). This implementation takes the conservative reading: the
    order is exempt only when EVERY line item's sku is tax-exempt in
    CATALOG. A single taxable line item makes the whole order taxable. This
    is a judgment call standing in for a real product/tax decision and
    should be confirmed against actual tax policy before shipping to
    production.
    """
    if not items:
        return False
    return all(CATALOG[entry["sku"]]["tax_exempt"] for entry in items)
