# spec: MODULES.md::catalog.py::AC-1
import pytest

from catalog import CATALOG, build_line_items


def test_catalog_contents():
    assert CATALOG["widget"] == {"unit_price": 9.99, "stock": 100}
    assert CATALOG["gadget"] == {"unit_price": 24.50, "stock": 5}
    assert CATALOG["gizmo"] == {"unit_price": 3.25, "stock": 0}


def test_build_line_items_happy_path():
    per_sku, subtotal, total_qty = build_line_items([
        {"sku": "widget", "qty": 2},
        {"sku": "gadget", "qty": 1},
    ])
    assert per_sku == {"widget": 19.98, "gadget": 24.50}
    assert subtotal == 44.48
    assert total_qty == 3


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        build_line_items([{"sku": "nonexistent", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        build_line_items([{"sku": "gadget", "qty": 999}])
