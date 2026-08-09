# spec: MODULES.md::catalog.py (all rungs)::AC-1
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from catalog import CATALOG, build_line_items


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
