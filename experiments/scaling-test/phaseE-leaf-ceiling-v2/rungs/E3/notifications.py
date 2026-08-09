"""notifications.py — spec: specs/order-pricing-e3.md::Acceptance criteria::AC-10

Deliberately standalone: not part of engine.build_invoice's chain. See the
rung-E3 brief and spec AC-10 for why this module exists on its own.
"""


def low_stock_alert(catalog, threshold):
    return sorted(sku for sku, entry in catalog.items() if entry["stock"] < threshold)
