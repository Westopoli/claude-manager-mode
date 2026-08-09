"""notifications.py — implements contract.low_stock_alert (SPEC.md AC-8)."""


def low_stock_alert(catalog: dict, threshold: int) -> list:
    """spec: SPEC.md::notifications.py::AC-8"""
    return sorted(sku for sku, qty in catalog.items() if qty < threshold)
