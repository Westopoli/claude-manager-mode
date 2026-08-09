"""Locked type contract — scaling-test target repo. Stub bodies only; leaves implement."""


def add_stock(catalog: dict, sku: str, qty: int) -> None:
    """spec: SPEC.md::inventory.py::AC-1"""
    raise NotImplementedError


def remove_stock(catalog: dict, sku: str, qty: int) -> None:
    """spec: SPEC.md::inventory.py::AC-2"""
    raise NotImplementedError


def unit_price(base_price: float, sku_tier: str) -> float:
    """spec: SPEC.md::pricing.py::AC-3"""
    raise NotImplementedError


def line_total(unit_price: float, qty: int) -> float:
    """spec: SPEC.md::pricing.py::AC-4"""
    raise NotImplementedError


def bulk_discount_rate(qty: int) -> float:
    """spec: SPEC.md::discounts.py::AC-5"""
    raise NotImplementedError


def apply_discount(total: float, rate: float) -> float:
    """spec: SPEC.md::discounts.py::AC-6"""
    raise NotImplementedError


def summarize_orders(orders: list) -> dict:
    """spec: SPEC.md::reporting.py::AC-7"""
    raise NotImplementedError


def low_stock_alert(catalog: dict, threshold: int) -> list:
    """spec: SPEC.md::notifications.py::AC-8"""
    raise NotImplementedError


def shipping_cost(weight_kg: float, distance_km: float) -> float:
    """spec: SPEC.md::shipping.py::AC-9"""
    raise NotImplementedError


def rate_tier(distance_km: float) -> str:
    """spec: SPEC.md::shipping_rates.py::AC-10"""
    raise NotImplementedError
