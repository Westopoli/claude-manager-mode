"""Catalog: SKU pricing, stock, and line-item subtotal calculations."""

CATALOG: dict = {
    "widget": {"unit_price": 9.99, "stock": 100},
    "gadget": {"unit_price": 24.50, "stock": 5},
    "gizmo": {"unit_price": 3.25, "stock": 0},
}


def lookup_price(sku: str) -> float:
    """Return the unit price for sku. Raises KeyError for unknown sku."""
    return CATALOG[sku]["unit_price"]


def check_availability(sku: str, qty: int) -> None:
    """Raise ValueError if qty exceeds stock. Raises KeyError for unknown sku."""
    stock = CATALOG[sku]["stock"]
    if qty > stock:
        raise ValueError(
            f"Requested qty {qty} for sku '{sku}' exceeds available stock {stock}"
        )


def build_line_items(items: list) -> tuple:
    """Build per-sku subtotals, order subtotal, and total quantity.

    items: [{"sku": str, "qty": int}, ...]
    Returns (per_sku_subtotals, order_subtotal, total_qty).
    """
    per_sku_subtotals = {}
    order_subtotal = 0.0
    total_qty = 0

    for item in items:
        sku = item["sku"]
        qty = item["qty"]
        check_availability(sku, qty)
        price = lookup_price(sku)
        line_total = round(price * qty, 2)
        per_sku_subtotals[sku] = line_total
        order_subtotal += line_total
        total_qty += qty

    order_subtotal = round(order_subtotal, 2)
    return per_sku_subtotals, order_subtotal, total_qty
