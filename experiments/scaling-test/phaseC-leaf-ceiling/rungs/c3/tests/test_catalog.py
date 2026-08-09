import pytest

import catalog


def test_catalog_has_expected_entries():
    assert catalog.CATALOG["widget"] == {"unit_price": 9.99, "stock": 100}
    assert catalog.CATALOG["gadget"] == {"unit_price": 24.50, "stock": 5}
    assert catalog.CATALOG["gizmo"] == {"unit_price": 3.25, "stock": 0}


def test_lookup_price_known_sku():
    assert catalog.lookup_price("widget") == 9.99
    assert catalog.lookup_price("gadget") == 24.50


def test_lookup_price_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        catalog.lookup_price("nonexistent")


def test_check_availability_ok():
    assert catalog.check_availability("widget", 5) is None
    assert catalog.check_availability("widget", 100) is None


def test_check_availability_exceeds_stock_raises_valueerror():
    with pytest.raises(ValueError):
        catalog.check_availability("gadget", 6)


def test_check_availability_zero_stock_raises_valueerror():
    with pytest.raises(ValueError):
        catalog.check_availability("gizmo", 1)


def test_check_availability_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        catalog.check_availability("nonexistent", 1)


def test_build_line_items_single_item():
    per_sku, order_subtotal, total_qty = catalog.build_line_items(
        [{"sku": "widget", "qty": 3}]
    )
    assert per_sku == {"widget": round(9.99 * 3, 2)}
    assert order_subtotal == round(9.99 * 3, 2)
    assert total_qty == 3


def test_build_line_items_multiple_items():
    per_sku, order_subtotal, total_qty = catalog.build_line_items(
        [{"sku": "widget", "qty": 2}, {"sku": "gadget", "qty": 4}]
    )
    expected_widget = round(9.99 * 2, 2)
    expected_gadget = round(24.50 * 4, 2)
    assert per_sku == {"widget": expected_widget, "gadget": expected_gadget}
    assert order_subtotal == round(expected_widget + expected_gadget, 2)
    assert total_qty == 6


def test_build_line_items_insufficient_stock_raises():
    with pytest.raises(ValueError):
        catalog.build_line_items([{"sku": "gadget", "qty": 10}])


def test_build_line_items_empty_list():
    per_sku, order_subtotal, total_qty = catalog.build_line_items([])
    assert per_sku == {}
    assert order_subtotal == 0.0
    assert total_qty == 0
