# spec: MODULES.md::catalog.py::AC-1
import pytest

from catalog import CATALOG, build_line_items


def test_catalog_contents():
    assert CATALOG["widget"]["unit_price"] == 9.99
    assert CATALOG["widget"]["stock"] == 100
    assert CATALOG["gadget"]["unit_price"] == 24.50
    assert CATALOG["gadget"]["stock"] == 5
    assert CATALOG["gizmo"]["unit_price"] == 3.25
    assert CATALOG["gizmo"]["stock"] == 0


def test_build_line_items_happy_path():
    items = [{"sku": "widget", "qty": 3}, {"sku": "gadget", "qty": 2}]
    per_sku, subtotal, total_qty = build_line_items(items)
    assert per_sku == {"widget": round(9.99 * 3, 2), "gadget": round(24.50 * 2, 2)}
    assert subtotal == round(9.99 * 3 + 24.50 * 2, 2)
    assert total_qty == 5


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        build_line_items([{"sku": "doohickey", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        build_line_items([{"sku": "gadget", "qty": 6}])
