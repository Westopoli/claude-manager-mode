# spec: specs/order-pricing-e3.md::Acceptance criteria::AC-1
"""
Written by the shard-test-writer role (Phase 2.5), before any impl exists.
State-check tests for catalog.py only.
"""
import pytest


def test_catalog_seed_data():
    import catalog

    assert catalog.CATALOG == {
        "widget": {"unit_price": 9.99, "stock": 100},
        "gadget": {"unit_price": 24.50, "stock": 5},
        "gizmo": {"unit_price": 3.25, "stock": 0},
    }


def test_build_line_items_happy_path():
    import catalog

    per_sku, subtotal, total_qty = catalog.build_line_items(
        [{"sku": "widget", "qty": 2}, {"sku": "gadget", "qty": 1}]
    )
    assert per_sku == {"widget": 19.98, "gadget": 24.50}
    assert subtotal == 44.48
    assert total_qty == 3


def test_build_line_items_unknown_sku_raises_keyerror():
    import catalog

    with pytest.raises(KeyError):
        catalog.build_line_items([{"sku": "doohickey", "qty": 1}])


def test_build_line_items_qty_exceeds_stock_raises_valueerror():
    import catalog

    with pytest.raises(ValueError):
        catalog.build_line_items([{"sku": "gadget", "qty": 6}])


def test_build_line_items_zero_stock_sku_any_qty_raises():
    import catalog

    with pytest.raises(ValueError):
        catalog.build_line_items([{"sku": "gizmo", "qty": 1}])
