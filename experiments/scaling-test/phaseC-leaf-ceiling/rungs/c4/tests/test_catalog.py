import pytest
from catalog import CATALOG, build_line_items, order_tax_exempt


def test_catalog_has_required_entries():
    assert CATALOG["widget"]["unit_price"] == 9.99
    assert CATALOG["widget"]["stock"] == 100
    assert CATALOG["widget"]["tax_exempt"] is False
    assert CATALOG["gadget"]["unit_price"] == 24.50
    assert CATALOG["gadget"]["stock"] == 5
    assert CATALOG["book"]["unit_price"] == 14.00
    assert CATALOG["book"]["tax_exempt"] is True


def test_build_line_items_basic():
    items = [{"sku": "widget", "qty": 2}, {"sku": "book", "qty": 1}]
    line_items, subtotal, total_qty = build_line_items(items)
    assert line_items["widget"]["qty"] == 2
    assert line_items["widget"]["line_subtotal"] == round(9.99 * 2, 2)
    assert line_items["book"]["qty"] == 1
    assert total_qty == 3
    assert subtotal == round(9.99 * 2 + 14.00, 2)


def test_build_line_items_unknown_sku_raises():
    with pytest.raises(KeyError):
        build_line_items([{"sku": "nonexistent", "qty": 1}])


def test_build_line_items_insufficient_stock_raises():
    with pytest.raises(ValueError):
        build_line_items([{"sku": "gadget", "qty": 999}])


def test_order_tax_exempt_all_exempt_items():
    # Every item in the order is tax-exempt in the catalog -> whole order exempt.
    assert order_tax_exempt([{"sku": "book", "qty": 2}]) is True


def test_order_tax_exempt_mixed_items_not_exempt():
    # Order mixes exempt and non-exempt items -> order is NOT treated as exempt,
    # since at least one line item is taxable.
    assert order_tax_exempt([{"sku": "book", "qty": 1}, {"sku": "widget", "qty": 1}]) is False


def test_order_tax_exempt_no_exempt_items():
    assert order_tax_exempt([{"sku": "widget", "qty": 1}]) is False
