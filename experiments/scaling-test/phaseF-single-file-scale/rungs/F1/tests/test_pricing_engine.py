# spec: MODULES.md::catalog.py/discounts.py/engine.py (all rungs)::AC-1
# merged into src/pricing_engine.py per phaseF-single-file-scale/rungs/F1 brief.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pricing_engine
from pricing_engine import (
    CATALOG,
    COUPONS,
    apply_coupon,
    build_invoice,
    build_line_items,
    membership_discount_rate,
    stack_discounts,
    volume_discount_rate,
)


# ---------------------------------------------------------------------------
# catalog section
# ---------------------------------------------------------------------------


def test_catalog_shape():
    assert CATALOG["widget"] == {"unit_price": 9.99, "stock": 100}
    assert CATALOG["gadget"] == {"unit_price": 24.50, "stock": 5}
    assert CATALOG["gizmo"] == {"unit_price": 3.25, "stock": 0}


def test_build_line_items_single_sku():
    per_sku, order_subtotal, total_qty = build_line_items(
        [{"sku": "widget", "qty": 3}]
    )
    assert per_sku == {"widget": 29.97}
    assert order_subtotal == 29.97
    assert total_qty == 3


def test_build_line_items_multiple_skus():
    per_sku, order_subtotal, total_qty = build_line_items(
        [{"sku": "widget", "qty": 3}, {"sku": "gadget", "qty": 2}]
    )
    assert per_sku == {"widget": 29.97, "gadget": 49.0}
    assert order_subtotal == 78.97
    assert total_qty == 5


def test_build_line_items_unknown_sku_raises_key_error():
    with pytest.raises(KeyError):
        build_line_items([{"sku": "doohickey", "qty": 1}])


def test_build_line_items_qty_over_stock_raises_value_error():
    with pytest.raises(ValueError):
        build_line_items([{"sku": "gadget", "qty": 6}])


def test_build_line_items_qty_over_zero_stock_raises_value_error():
    with pytest.raises(ValueError):
        build_line_items([{"sku": "gizmo", "qty": 1}])


# ---------------------------------------------------------------------------
# discounts section
# ---------------------------------------------------------------------------


def test_volume_discount_rate_tiers():
    assert volume_discount_rate(0) == 0.0
    assert volume_discount_rate(9) == 0.0
    assert volume_discount_rate(10) == 0.05
    assert volume_discount_rate(49) == 0.05
    assert volume_discount_rate(50) == 0.10
    assert volume_discount_rate(500) == 0.10


def test_membership_discount_rate_tiers():
    assert membership_discount_rate("none") == 0.0
    assert membership_discount_rate("silver") == 0.03
    assert membership_discount_rate("gold") == 0.07
    assert membership_discount_rate("platinum") == 0.12


def test_membership_discount_rate_unknown_raises_value_error():
    with pytest.raises(ValueError):
        membership_discount_rate("bronze")


def test_coupons_table_shape():
    assert COUPONS["SAVE10"] == {"rate": 0.10, "min_spend": 50.0, "expired": False}


def test_apply_coupon_valid():
    assert apply_coupon(100.0, "SAVE10") == 90.0


def test_apply_coupon_unknown_code_raises_value_error():
    with pytest.raises(ValueError):
        apply_coupon(100.0, "NOPE")


def test_apply_coupon_below_min_spend_raises_value_error():
    with pytest.raises(ValueError):
        apply_coupon(10.0, "SAVE10")


def test_stack_discounts_no_coupon():
    # qty=10 -> volume 0.05, tier=gold -> membership 0.07, applied in that
    # order per the intra-file contradiction resolution documented in
    # pricing_engine.py (volume, then membership, then coupon-last).
    result = stack_discounts(100.0, 10, "gold", coupon_code=None)
    assert result == 88.35


def test_stack_discounts_with_coupon_applied_last():
    # coupon applied to the post-membership amount, per the recorded
    # resolution (volume, membership, coupon-last).
    result = stack_discounts(100.0, 10, "gold", coupon_code="SAVE10")
    assert result == 79.52


# ---------------------------------------------------------------------------
# engine (build_invoice) section
# ---------------------------------------------------------------------------


def test_build_invoice_calls_build_line_items_and_stack_discounts_collaborators(
    monkeypatch,
):
    """Interaction assertion (composition rule): build_invoice must actually
    call build_line_items and stack_discounts, not reimplement their logic
    inline. Spies wrap the real functions so behavior is unchanged but the
    call is observed."""
    calls = {"build_line_items": 0, "stack_discounts": 0}
    real_build_line_items = pricing_engine.build_line_items
    real_stack_discounts = pricing_engine.stack_discounts

    def spy_build_line_items(items):
        calls["build_line_items"] += 1
        return real_build_line_items(items)

    def spy_stack_discounts(subtotal, total_qty, tier, coupon_code=None):
        calls["stack_discounts"] += 1
        return real_stack_discounts(subtotal, total_qty, tier, coupon_code=coupon_code)

    monkeypatch.setattr(pricing_engine, "build_line_items", spy_build_line_items)
    monkeypatch.setattr(pricing_engine, "stack_discounts", spy_stack_discounts)

    order = {
        "items": [{"sku": "widget", "qty": 10}],
        "membership_tier": "gold",
        "coupon_code": "SAVE10",
    }
    pricing_engine.build_invoice(order)

    assert calls["build_line_items"] == 1
    assert calls["stack_discounts"] == 1


def test_build_invoice_return_shape_and_math_with_coupon():
    order = {
        "items": [{"sku": "widget", "qty": 10}],
        "membership_tier": "gold",
        "coupon_code": "SAVE10",
    }
    result = build_invoice(order)

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
    result = build_invoice(order)

    assert result["subtotal"] == 9.99
    assert result["post_discount_amount"] == 9.99
    assert result["total"] == 9.99


def test_build_invoice_default_membership_tier_when_absent():
    order = {"items": [{"sku": "widget", "qty": 1}]}
    result = build_invoice(order)

    assert result["total"] == 9.99
