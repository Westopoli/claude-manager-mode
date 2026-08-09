# Locked type contract — rung E3.
# Parent-owned. Sentinel bodies only; the leaf-owned impl modules
# (catalog.py, discounts.py, engine.py, validation.py, currency.py,
# shipping.py, notifications.py) live at the project root and implement
# the real bodies there. This file exists so /manager-mode's brief audit
# can resolve `contract_imports` symbol names against a locked source; it
# is not imported by the real implementation modules or by the tests.

CATALOG = {}  # type: dict

COUPONS = {}  # type: dict

EXCHANGE_RATES = {}  # type: dict


def build_line_items(items: list) -> tuple:
    """catalog.build_line_items — spec: order-pricing-e3.md AC-1."""
    raise NotImplementedError


def volume_discount_rate(total_qty: int) -> float:
    """discounts.volume_discount_rate — spec: order-pricing-e3.md AC-2."""
    raise NotImplementedError


def membership_discount_rate(tier: str) -> float:
    """discounts.membership_discount_rate — spec: order-pricing-e3.md AC-3."""
    raise NotImplementedError


def apply_coupon(amount: float, code: str) -> float:
    """discounts.apply_coupon — spec: order-pricing-e3.md AC-4."""
    raise NotImplementedError


def stack_discounts(subtotal: float, total_qty: int, tier: str, coupon_code: str = None) -> float:
    """discounts.stack_discounts — spec: order-pricing-e3.md AC-5."""
    raise NotImplementedError


def validate_order(order: dict) -> None:
    """validation.validate_order — spec: order-pricing-e3.md AC-6."""
    raise NotImplementedError


def convert(amount_usd: float, to_currency: str) -> float:
    """currency.convert — spec: order-pricing-e3.md AC-7."""
    raise NotImplementedError


def format_currency(amount: float, currency: str) -> str:
    """currency.format_currency — spec: order-pricing-e3.md AC-7."""
    raise NotImplementedError


def shipping_cost(weight_kg: float, distance_km: float, express: bool) -> float:
    """shipping.shipping_cost — spec: order-pricing-e3.md AC-8."""
    raise NotImplementedError


def build_invoice(order: dict) -> dict:
    """engine.build_invoice — spec: order-pricing-e3.md AC-9."""
    raise NotImplementedError


def low_stock_alert(catalog: dict, threshold: int) -> list:
    """notifications.low_stock_alert — spec: order-pricing-e3.md AC-10."""
    raise NotImplementedError
