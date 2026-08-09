"""pricing.py — implements contract.unit_price, contract.line_total (SPEC.md AC-3, AC-4)."""

_TIER_MULTIPLIERS = {
    "standard": 1.0,
    "bulk": 0.9,
    "rush": 1.15,
}


def unit_price(base_price: float, sku_tier: str) -> float:
    """spec: SPEC.md::pricing.py::AC-3"""
    if sku_tier not in _TIER_MULTIPLIERS:
        raise ValueError(f"unknown sku_tier: {sku_tier!r}")
    return base_price * _TIER_MULTIPLIERS[sku_tier]


def line_total(unit_price: float, qty: int) -> float:
    """spec: SPEC.md::pricing.py::AC-4"""
    if qty <= 0:
        raise ValueError("qty must be positive")
    return round(unit_price * qty, 2)
