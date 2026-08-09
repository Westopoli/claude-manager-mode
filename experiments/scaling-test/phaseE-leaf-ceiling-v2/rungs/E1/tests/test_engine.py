# spec: MODULES.md::engine.py (all rungs)::AC-3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import catalog
import discounts
import engine


def test_build_invoice_calls_catalog_and_discounts_collaborators(monkeypatch):
    """Interaction assertion (composition rule): engine.build_invoice must
    actually call catalog.build_line_items and discounts.stack_discounts,
    not reimplement their logic inline. Spies wrap the real functions so
    behavior is unchanged but the call is observed."""
    calls = {"catalog.build_line_items": 0, "discounts.stack_discounts": 0}
    real_build_line_items = catalog.build_line_items
    real_stack_discounts = discounts.stack_discounts

    def spy_build_line_items(items):
        calls["catalog.build_line_items"] += 1
        return real_build_line_items(items)

    def spy_stack_discounts(subtotal, total_qty, tier, coupon_code=None):
        calls["discounts.stack_discounts"] += 1
        return real_stack_discounts(subtotal, total_qty, tier, coupon_code=coupon_code)

    monkeypatch.setattr(engine.catalog, "build_line_items", spy_build_line_items)
    monkeypatch.setattr(engine.discounts, "stack_discounts", spy_stack_discounts)

    order = {
        "items": [{"sku": "widget", "qty": 10}],
        "membership_tier": "gold",
        "coupon_code": "SAVE10",
    }
    engine.build_invoice(order)

    assert calls["catalog.build_line_items"] == 1
    assert calls["discounts.stack_discounts"] == 1


def test_build_invoice_return_shape_and_math_with_coupon():
    order = {
        "items": [{"sku": "widget", "qty": 10}],
        "membership_tier": "gold",
        "coupon_code": "SAVE10",
    }
    result = engine.build_invoice(order)

    assert result["line_items"] == {"widget": 99.9}
    assert result["subtotal"] == 99.9
    assert result["post_discount_amount"] == 79.44
    assert result["total"] == 79.44


def test_build_invoice_no_membership_no_coupon():
    order = {
        "items": [{"sku": "widget", "qty": 1}],
        "membership_tier": "none",
        "coupon_code": None,
    }
    result = engine.build_invoice(order)

    assert result["subtotal"] == 9.99
    assert result["post_discount_amount"] == 9.99
    assert result["total"] == 9.99


def test_build_invoice_default_membership_tier_when_absent():
    order = {"items": [{"sku": "widget", "qty": 1}]}
    result = engine.build_invoice(order)

    assert result["total"] == 9.99
