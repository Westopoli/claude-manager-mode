# spec: /Users/westley/Projects/claude-swarm/experiments/scaling-test/phaseE-leaf-ceiling-v2/MODULES.md::catalog.py::AC-1
import pytest

import catalog


def test_catalog_contents():
    assert catalog.CATALOG["widget"]["unit_price"] == 9.99
    assert catalog.CATALOG["gadget"]["stock"] == 5
    assert catalog.CATALOG["gizmo"]["stock"] == 0


def test_build_line_items_single_sku():
    per_sku, subtotal, total_qty = catalog.build_line_items(
        [{"sku": "widget", "qty": 2}]
    )
    assert per_sku == {"widget": 19.98}
    assert subtotal == 19.98
    assert total_qty == 2


def test_build_line_items_multi_sku():
    per_sku, subtotal, total_qty = catalog.build_line_items(
        [{"sku": "widget", "qty": 2}, {"sku": "gadget", "qty": 1}]
    )
    assert per_sku == {"widget": 19.98, "gadget": 24.50}
    assert subtotal == 44.48
    assert total_qty == 3


def test_build_line_items_unknown_sku_raises_keyerror():
    with pytest.raises(KeyError):
        catalog.build_line_items([{"sku": "doohickey", "qty": 1}])


def test_build_line_items_over_stock_raises_valueerror():
    with pytest.raises(ValueError):
        catalog.build_line_items([{"sku": "gadget", "qty": 6}])


def test_build_line_items_zero_stock_sku_raises_valueerror():
    with pytest.raises(ValueError):
        catalog.build_line_items([{"sku": "gizmo", "qty": 1}])
