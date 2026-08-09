"""inventory.py — implements contract.add_stock / contract.remove_stock.

spec: SPEC.md::inventory.py::AC-1, AC-2
"""


def add_stock(catalog: dict, sku: str, qty: int) -> None:
    """spec: SPEC.md::inventory.py::AC-1"""
    if qty <= 0:
        raise ValueError("qty must be positive")
    catalog[sku] = catalog.get(sku, 0) + qty


def remove_stock(catalog: dict, sku: str, qty: int) -> None:
    """spec: SPEC.md::inventory.py::AC-2"""
    if qty <= 0:
        raise ValueError("qty must be positive")
    if sku not in catalog:
        raise KeyError(sku)
    if catalog[sku] - qty < 0:
        raise ValueError("removal would take stock below zero")
    catalog[sku] -= qty
