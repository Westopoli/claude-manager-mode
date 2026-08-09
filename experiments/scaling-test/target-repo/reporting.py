"""reporting.py — implements contract.summarize_orders (SPEC.md::reporting.py::AC-7)."""


def summarize_orders(orders: list) -> dict:
    """spec: SPEC.md::reporting.py::AC-7"""
    order_count = 0
    total_revenue = 0.0
    units_sold = 0

    for order in orders:
        if not isinstance(order, dict):
            continue
        if "sku" not in order or "qty" not in order or "total" not in order:
            continue

        sku = order["sku"]
        qty = order["qty"]
        total = order["total"]

        if not isinstance(sku, str):
            continue
        if not isinstance(qty, int) or isinstance(qty, bool):
            continue
        if not isinstance(total, (int, float)) or isinstance(total, bool):
            continue

        order_count += 1
        units_sold += qty
        total_revenue += total

    return {
        "order_count": order_count,
        "total_revenue": round(total_revenue, 2),
        "units_sold": units_sold,
    }
